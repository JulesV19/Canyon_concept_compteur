"""Lectures sur l'API de Strava, avec renouvellement du jeton d'accès."""

import http.client
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

from .files import save_tokens

API_URL = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/oauth/token"
TIMEOUT_S = 20
REFRESH_BEFORE_S = 600        # jeton d'accès renouvelé 10 min avant son expiration
RECONNECT = "accès refusé, relancer tools/strava/connecter.py"


class SyncError(Exception):
    """Synchro impossible ; `str(erreur)` le dit en quelques mots, pour l'écran. `offline` : pas de réseau, ou Strava
    injoignable, un nouvel essai peut marcher. `status` : code HTTP de la réponse, s'il y en a une."""

    def __init__(self, message: str, offline: bool = False, status: int | None = None):
        super().__init__(message)
        self.offline = offline
        self.status = status


def http_error(status: int) -> SyncError:
    if status in (401, 403):
        return SyncError(RECONNECT, status=status)
    if status == 429:
        return SyncError("limite de Strava atteinte, réessayer dans 15 min", status=status)
    if status >= 500:
        return SyncError("Strava ne répond pas", offline=True, status=status)
    return SyncError(f"erreur Strava ({status})", status=status)


def call(request: urllib.request.Request) -> object:
    """Envoie la requête et renvoie sa réponse JSON ; SyncError si elle échoue."""
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise http_error(error.code) from error
    except urllib.error.URLError as error:
        raise SyncError("pas de réseau", offline=True) from error
    except (OSError, http.client.HTTPException) as error:  # délai dépassé, connexion coupée en route
        raise SyncError("Strava ne répond pas", offline=True) from error
    except ValueError as error:
        raise SyncError("réponse de Strava illisible") from error


class Client:
    """Lectures sur l'API de Strava, avec le jeton d'accès du fichier, renouvelé quand il expire."""

    def __init__(self, tokens_file: Path, api_url: str | None = None, token_url: str | None = None,
                 clock: Callable[[], float] = time.time):
        self.tokens_file = tokens_file
        self.api_url = api_url or API_URL
        self.token_url = token_url or TOKEN_URL
        self.clock = clock
        try:
            self.tokens = json.loads(tokens_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise SyncError("pas relié à Strava") from error
        if not isinstance(self.tokens, dict) or not self.tokens.get("refresh_token"):
            raise SyncError("pas relié à Strava")

    def get(self, path: str, **params) -> object:
        """Lecture sur l'API. Un jeton refusé est renouvelé une fois : sans réseau au démarrage, l'horloge du Pi peut se
        tromper sur son expiration."""
        try:
            expires_at = float(self.tokens.get("expires_at", 0))
        except (TypeError, ValueError):
            expires_at = 0.0
        if expires_at - REFRESH_BEFORE_S <= self.clock():
            self.refresh()
        url = self.api_url + path + ("?" + urllib.parse.urlencode(params) if params else "")
        try:
            return self._get(url)
        except SyncError as error:
            if error.status != 401:
                raise
        self.refresh()
        return self._get(url)

    def _get(self, url: str) -> object:
        token = self.tokens.get("access_token", "")
        return call(urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}))

    def refresh(self) -> None:
        """Nouveau jeton d'accès. Strava peut aussi remplacer le jeton de renouvellement, et l'ancien ne vaut alors
        plus : les deux sont écrits tout de suite."""
        form = urllib.parse.urlencode({
            "client_id": self.tokens.get("client_id", ""),
            "client_secret": self.tokens.get("client_secret", ""),
            "grant_type": "refresh_token",
            "refresh_token": self.tokens["refresh_token"],
        }).encode()
        try:
            answer = call(urllib.request.Request(self.token_url, data=form, method="POST"))
        except SyncError as error:
            if error.status in (400, 401, 403):  # accès retiré, ou jeton remplacé depuis un autre appareil
                raise SyncError(RECONNECT, status=401) from error
            raise
        try:
            renewed = {"access_token": str(answer["access_token"]), "refresh_token": str(answer["refresh_token"]),
                       "expires_at": float(answer["expires_at"])}
        except (TypeError, KeyError, ValueError) as error:
            raise SyncError("réponse de Strava illisible") from error
        self.tokens |= renewed
        try:
            save_tokens(self.tokens_file, self.tokens)
        except OSError as error:  # ils valent jusqu'à l'arrêt ; au prochain démarrage, il faudra peut-être relier
            print(f"Jetons Strava pas enregistrés : {error}", file=sys.stderr)
