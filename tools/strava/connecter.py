#!/usr/bin/env python3
"""Relie le compteur à ton compte Strava. À lancer sur le Mac, qui a un navigateur.

Avant : crée ton application Strava sur https://www.strava.com/settings/api, avec « localhost » comme domaine de rappel
(Authorization Callback Domain). Le script demande son Client ID et son Client Secret, ouvre la page d'autorisation de
Strava, récupère le code au retour, puis range les jetons, lisibles par toi seul :

    .venv/bin/python tools/strava/connecter.py        # ce Mac (~/.config/canyon-compteur/strava.json), puis une synchro
    .venv/bin/python tools/strava/connecter.py --pi   # le Pi (julesvide@compteur.local, ou --pi autre@machine)

Chaque appareil a son jeton : Strava peut remplacer un jeton de renouvellement quand il s'en sert, et un jeton partagé
couperait l'autre appareil. Le Client ID et le Client Secret ne sont demandés qu'une fois : ils restent dans le fichier
du Mac (--codes pour les changer).
"""

import argparse
import getpass
import http.server
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from compteur.strava import (CACHE_FILE, STRAVA_DIR, TOKEN_URL, TOKENS_FILE, Client, SyncError,  # noqa: E402
                             kom_label, save_tokens, starred_segments, sync)

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
# Segments en favori, même privés (read_all), et tes sorties, pour le fantôme de ton record (activity:read_all)
SCOPES = ("read", "read_all", "activity:read_all")
PI = "julesvide@compteur.local"
WAIT_S = 300  # le temps de cliquer sur Autoriser


def ask_keys() -> tuple[str, str]:
    print("Les codes de ton application Strava (https://www.strava.com/settings/api) :")
    client_id = input("Client ID : ").strip()
    client_secret = getpass.getpass("Client Secret (il ne s'affiche pas) : ").strip()
    if not client_id or not client_secret:
        sys.exit("Il faut les deux codes.")
    return client_id, client_secret


def app_keys() -> tuple[str, str]:
    """Client ID et Client Secret de l'application Strava : ceux déjà rangés sur ce Mac, sinon demandés."""
    try:
        tokens = json.loads((STRAVA_DIR / TOKENS_FILE).read_text(encoding="utf-8"))
        if tokens.get("client_id") and tokens.get("client_secret"):
            return str(tokens["client_id"]), str(tokens["client_secret"])
    except (OSError, ValueError, AttributeError):
        pass
    return ask_keys()


def authorize(client_id: str) -> str:
    """Ouvre la page d'autorisation de Strava, et attend son retour sur un petit serveur local. Renvoie le code."""
    state = secrets.token_urlsafe(16)  # la réponse doit le rapporter : elle vient bien de cette demande
    answer = {}

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" not in query and "error" not in query:
                self.send_error(404)  # favicon...
                return
            answer.update({key: values[0] for key, values in query.items()})
            message = ("C'est fait : tu peux fermer cette page et revenir au terminal." if "code" in query
                       else "Autorisation refusée : rien n'a été relié.")
            page = ("<!doctype html><meta charset=utf-8><title>Canyon compteur</title>"
                    f"<body style='font:18px -apple-system,sans-serif;margin:4em'><p>{message}</p>").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Callback)
    server.timeout = 1
    url = AUTHORIZE_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id,
        # Strava admet 127.0.0.1 avec le domaine localhost ; le port est libre
        "redirect_uri": f"http://127.0.0.1:{server.server_port}/strava",
        "response_type": "code",
        "approval_prompt": "force",
        "scope": ",".join(SCOPES),
        "state": state,
    })
    print(f"\nAutorise le compteur dans ton navigateur. S'il ne s'ouvre pas, va sur :\n{url}\n")
    webbrowser.open(url)
    deadline = time.monotonic() + WAIT_S
    try:
        while not answer and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if not answer:
        sys.exit("Pas de réponse de Strava : relance le script.")
    if answer.get("state") != state:
        sys.exit("Réponse inattendue : relance le script.")
    if "error" in answer:
        sys.exit("Autorisation refusée sur Strava.")
    granted = set(answer.get("scope", "").split(","))
    missing = [scope for scope in SCOPES if scope not in granted]
    if missing:
        sys.exit(f"Il manque des autorisations ({', '.join(missing)}) : relance et laisse toutes les cases cochées.")
    return answer["code"]


def exchange(client_id: str, client_secret: str, code: str) -> dict:
    """Échange le code contre les jetons."""
    form = urllib.parse.urlencode({"client_id": client_id, "client_secret": client_secret, "code": code,
                                   "grant_type": "authorization_code"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=form, method="POST"),
                                    timeout=30) as response:
            answer = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        sys.exit(f"Strava refuse ({error.code}) : {detail}\nVérifie le Client ID et le Client Secret (--codes).")
    except (urllib.error.URLError, OSError, ValueError) as error:
        sys.exit(f"Strava injoignable : {error}")
    athlete = answer.get("athlete") or {}
    return {"client_id": client_id, "client_secret": client_secret, "access_token": answer["access_token"],
            "refresh_token": answer["refresh_token"], "expires_at": answer["expires_at"],
            "athlete": {key: athlete.get(key) for key in ("id", "firstname", "sex")}}


def install_on_pi(host: str, tokens: dict) -> None:
    """Pose les jetons sur le Pi par ssh, sans les écrire sur le Mac, lisibles par le seul compte du Pi."""
    folder = ".config/canyon-compteur"
    command = (f"umask 077 && mkdir -p {folder} && cat > {folder}/{TOKENS_FILE}.tmp"
               f" && mv {folder}/{TOKENS_FILE}.tmp {folder}/{TOKENS_FILE}")
    try:
        result = subprocess.run(["ssh", "-4", host, command], input=json.dumps(tokens, indent=2).encode(),
                                timeout=60)
    except subprocess.TimeoutExpired:
        result = None
    if result is None or result.returncode != 0:
        sys.exit(f"Copie sur le Pi impossible ({host}) : relance quand il est allumé et joignable.")


def first_sync() -> None:
    """Première synchro sur le Mac : ce que Strava donne vraiment (records, KOM), avant d'aller rouler."""
    try:
        cache = sync(Client(STRAVA_DIR / TOKENS_FILE), STRAVA_DIR / CACHE_FILE)
    except SyncError as error:
        print(f"Première synchro inachevée : {error}.")
        return
    segments = starred_segments(cache)
    records = sum(segment.pr is not None for segment in segments)
    ghosts = sum(segment.pr is not None and len(segment.pr.splits) > 1 for segment in segments)
    koms = sum(segment.kom is not None for segment in segments)
    print(f"{len(segments)} segments vélo en favori : {records} avec ton record ({ghosts} avec ses temps de passage),"
          f" {koms} avec le {kom_label(cache)}.")
    for segment in segments:
        pr = segment.pr
        record = f"record {pr.elapsed_s // 60:.0f}:{pr.elapsed_s % 60:02.0f}" if pr else "sans record"
        print(f"  · {segment.name} ({segment.length_m / 1000:.1f} km, {record})")
    if segments and not records:
        print("Aucun record transmis. Si tu as déjà roulé ces segments, l'API de Strava les réserve sans doute aux"
              " abonnés : la page segment montrera alors l'effort en cours, sans l'écart à ton record.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Relie le compteur à ton compte Strava.")
    parser.add_argument("--pi", nargs="?", const=PI, metavar="UTILISATEUR@MACHINE",
                        help=f"relie le Pi ({PI} par défaut) au lieu de ce Mac")
    parser.add_argument("--codes", action="store_true", help="redemande le Client ID et le Client Secret")
    args = parser.parse_args()

    client_id, client_secret = ask_keys() if args.codes else app_keys()
    tokens = exchange(client_id, client_secret, authorize(client_id))
    name = tokens["athlete"].get("firstname") or "ton compte"
    if args.pi:
        install_on_pi(args.pi, tokens)
        print(f"Pi relié au compte de {name}. Il synchronise tes favoris à son démarrage,"
              " ou depuis Menu ≡ → Segments Strava.")
        return
    save_tokens(STRAVA_DIR / TOKENS_FILE, tokens)
    print(f"Mac relié au compte de {name}. Première synchro…")
    first_sync()


if __name__ == "__main__":
    main()
