"""La synchro des segments en favori : ne relit que ce qui manque ou a vieilli."""

import json
from pathlib import Path

from ..storage import describe, write_atomic
from .client import Client, SyncError
from .decode import athlete_fields, ghost_splits, parse_time, personal_record, segment_points
from .files import as_dict, load_cache

DETAIL_MAX_AGE_S = 7 * 86400  # KOM, QOM et record relus une fois par semaine au plus
PAGE_SIZE = 200               # segments par page, dans la liste des favoris


def sync(client: Client, cache_file: Path) -> dict:
    """Met le cache à jour avec les segments vélo en favori : la liste d'abord, puis le tracé de ceux qui n'en ont pas,
    les détails (KOM, QOM, record) de ceux relus il y a plus d'une semaine, et le fantôme de chaque nouveau record. Le
    cache est écrit même si la synchro s'arrête en route (limite de lectures, réseau perdu) : ce qui est arrivé sert
    déjà, et la synchro suivante reprend le reste. Renvoie le cache ; SyncError si la synchro n'est pas allée au
    bout."""
    now = client.clock()
    old = load_cache(cache_file)
    athlete = athlete_fields(as_dict(client.tokens.get("athlete"))) if client.tokens.get("athlete") else {}
    cached_athlete = as_dict(old.get("athlete"))
    known = {entry.get("id"): entry for entry in old.get("segments", []) if isinstance(entry, dict)} \
        if isinstance(old.get("segments"), list) else {}
    if athlete.get("id") is not None and cached_athlete.get("id") not in (None, athlete["id"]):
        known = {}  # relié à un autre compte : ses segments ne sont plus les nôtres
    if not athlete:
        athlete = cached_athlete or athlete_fields(as_dict(client.get("/athlete")))

    starred = []
    page = 1
    while True:
        batch = client.get("/segments/starred", page=page, per_page=PAGE_SIZE)
        if not isinstance(batch, list):
            raise SyncError("réponse de Strava illisible")
        starred += batch
        if len(batch) < PAGE_SIZE:
            break
        page += 1

    entries = []
    for summary in starred:
        if not isinstance(summary, dict) or summary.get("activity_type") != "Ride" \
                or not isinstance(summary.get("id"), int):
            continue  # segments de course à pied, ou mal formés
        entry = dict(known.get(summary["id"], {"id": summary["id"], "detail_at": 0}))
        entry["name"] = str(summary.get("name") or entry.get("name") or "Segment")
        entry["pr"] = personal_record(summary) or entry.get("pr")
        entries.append(entry)

    # Les tracés qui manquent d'abord (sans eux, un segment ne sert à rien), puis les détails les plus vieux
    error = None
    todo = sorted((entry for entry in entries
                   if not entry.get("points") or now - entry.get("detail_at", 0) > DETAIL_MAX_AGE_S),
                  key=lambda entry: (bool(entry.get("points")), entry.get("detail_at", 0)))
    for entry in todo:
        try:
            if not entry.get("points"):
                entry["points"] = segment_points(client.get(f"/segments/{entry['id']}/streams", keys="latlng,altitude",
                                                     key_by_type="true"))
            detail = as_dict(client.get(f"/segments/{entry['id']}"))
        except SyncError as failure:
            if failure.status == 404:  # segment supprimé, ou devenu privé
                entries.remove(entry)
                continue
            error = failure
            break
        xoms = as_dict(detail.get("xoms"))
        entry |= {"name": str(detail.get("name") or entry["name"]), "kom_s": parse_time(xoms.get("kom")),
                  "qom_s": parse_time(xoms.get("qom")), "pr": personal_record(detail) or entry.get("pr"), "detail_at": now}

    # Enfin le fantôme de chaque record : la sortie du record, lue une fois (une lecture par record)
    if error is None:
        for entry in entries:
            activity = as_dict(entry.get("pr")).get("activity_id")
            if not activity or not entry.get("points") or as_dict(entry.get("ghost")).get("activity_id") == activity:
                continue
            try:
                streams = client.get(f"/activities/{activity}/streams", keys="time,latlng", key_by_type="true")
            except SyncError as failure:
                if failure.status != 404:
                    error = failure
                    break
                streams = None  # sortie supprimée : pas de fantôme, l'allure régulière le remplace
            entry["ghost"] = {"activity_id": activity, "splits": ghost_splits(entry, streams)}

    cache ={"athlete": athlete, "synced_at": now if error is None else old.get("synced_at"), "segments": entries}
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(cache_file, json.dumps(cache, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except OSError as failure:
        raise SyncError(f"segments pas enregistrés ({describe(failure)})") from failure
    if error is not None:
        raise error
    return cache
