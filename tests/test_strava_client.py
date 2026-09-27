"""Jetons Strava : renouvelés à l'expiration ou au refus, accès retiré."""

import json
import stat

import pytest

from compteur.strava import CACHE_FILE, TOKENS_FILE, SyncError, sync
from strava_fake import NOW, connect, favorite, publish


def test_jeton_expire_renouvele_et_garde(tmp_path, fake):
    publish(fake, [favorite(1, "A")])
    sync(connect(tmp_path, fake, expires_at=NOW - 60), tmp_path / CACHE_FILE)

    renewal = fake.requests[0]
    assert renewal["path"] == "/oauth/token"
    assert renewal["form"] == {"client_id": ["1"], "client_secret": ["s"], "grant_type": ["refresh_token"],
                               "refresh_token": ["r1"]}
    assert {request["auth"] for request in fake.requests[1:]} == {"Bearer a2"}
    saved = json.loads((tmp_path / TOKENS_FILE).read_text())
    assert (saved["refresh_token"], saved["expires_at"], saved["client_secret"]) == ("r2", NOW + 21600, "s")
    assert stat.S_IMODE((tmp_path / TOKENS_FILE).stat().st_mode) == 0o600


def test_jeton_refuse_renouvele_une_fois(tmp_path, fake):
    """Le Pi sans horloge croit son jeton encore bon : Strava le refuse, il est renouvelé, et la lecture repart."""
    publish(fake, [favorite(1, "A")])
    starred = fake.routes["/api/v3/segments/starred"]
    fake.routes["/api/v3/segments/starred"] = \
        lambda request: starred if request["auth"] == "Bearer a2" else (401, {"message": "Authorization Error"})
    sync(connect(tmp_path, fake), tmp_path / CACHE_FILE)
    assert fake.paths()[:3] == ["/api/v3/segments/starred", "/oauth/token", "/api/v3/segments/starred"]


def test_acces_retire(tmp_path, fake):
    publish(fake, [favorite(1, "A")])
    fake.routes["/api/v3/segments/starred"] = (401, {"message": "Authorization Error"})
    fake.routes["/oauth/token"] = (400, {"message": "Bad Request"})
    with pytest.raises(SyncError, match="connecter.py"):
        sync(connect(tmp_path, fake), tmp_path / CACHE_FILE)
    assert not (tmp_path / CACHE_FILE).exists()
