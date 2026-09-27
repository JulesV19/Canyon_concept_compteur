"""Pour les essais Strava : un faux Strava sur le réseau local, et des segments tout faits."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


from compteur.strava import (TOKENS_FILE, Client, save_tokens)


NOW = 1_789_000_000.0  # heure des essais (septembre 2026)


class FakeStrava:
    """Faux Strava sur un port local. `routes[chemin]` : la réponse (code, corps JSON), ou une fonction qui la donne
    à partir de la requête. Chaque requête reçue est notée dans `requests`."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                url = urlparse(self.path)
                request = {"path": url.path, "query": parse_qs(url.query), "auth": self.headers.get("Authorization"),
                           "form": parse_qs(self.rfile.read(length).decode()) if length else {}}
                fake.requests.append(request)
                route = fake.routes.get(url.path, (404, {"message": "Record Not Found"}))
                status, data = route(request) if callable(route) else route
                payload = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = answer

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def paths(self):
        return [request["path"] for request in self.requests]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def line(offset):
    """Tracé tout droit vers le nord, un point tous les 11 m sur 1,1 km, qui monte de 5 %."""
    return {"latlng": {"data": [[48.6 + i * 0.0001, 1.8 + offset] for i in range(101)]},
            "altitude": {"data": [100 + i * 0.556 for i in range(101)]},
            "distance": {"data": [i * 11.1 for i in range(101)]}}


def record_ride(offset):
    """Flux de la sortie du record sur le tracé de line(offset) : 300 m avant, la première moitié à 5 m/s, la seconde
    à 3,35 m/s (277 s en tout), puis 200 m après. Une mesure par seconde."""
    times, positions, t, d = [], [], 0, -300.0
    while d <= 1312:
        times.append(t)
        positions.append([48.6 + d / 111_195, 1.8 + offset])
        d += 5.0 if d < 556 else 556 / 166
        t += 1
    return {"time": {"data": times}, "latlng": {"data": positions}}


def favorite(segment_id, name, activity="Ride", pr_s=None):
    data = {"id": segment_id, "name": name, "activity_type": activity, "distance": 1112.0, "average_grade": 5.0}
    if pr_s is not None:
        data["athlete_pr_effort"] = {"id": 900 + segment_id, "activity_id": 500 + segment_id, "elapsed_time": pr_s,
                                     "start_date_local": "2026-06-03T07:12:45Z", "distance": 1112.0}
    return data


def publish(fake, favorites, kom="3:12", qom="4:01"):
    """Le faux Strava sert ces favoris, avec leur détail et leur tracé, et renouvelle les jetons."""
    fake.routes["/api/v3/segments/starred"] = (200, favorites)
    for i, segment in enumerate(favorites):
        fake.routes[f"/api/v3/segments/{segment['id']}"] = (200, segment | {"xoms": {"kom": kom, "qom": qom}})
        fake.routes[f"/api/v3/segments/{segment['id']}/streams"] = (200, line(i * 0.01))
    fake.routes["/oauth/token"] = (200, {"access_token": "a2", "refresh_token": "r2", "expires_at": NOW + 21600})


def connect(tmp_path, fake, expires_at=NOW + 30 * 86400, sex="M", clock=None):
    """Appareil relié : ses jetons, et un client qui parle au faux Strava."""
    save_tokens(tmp_path / TOKENS_FILE, {"client_id": "1", "client_secret": "s", "access_token": "a1",
                                         "refresh_token": "r1", "expires_at": expires_at,
                                         "athlete": {"id": 7, "firstname": "Jules", "sex": sex}})
    return Client(tmp_path / TOKENS_FILE, api_url=fake.url + "/api/v3", token_url=fake.url + "/oauth/token",
                  clock=clock or (lambda: NOW))
