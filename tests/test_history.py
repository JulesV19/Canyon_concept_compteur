import json
from datetime import datetime, timedelta, timezone

from compteur import history


def enregistree(folder, stem: str, name: str) -> None:
    (folder / f"{stem}.fit").write_bytes(b"")
    (folder / f"{stem}.json").write_text(json.dumps({"name": name}), encoding="utf-8")


def test_sorties_de_la_plus_recente_a_la_plus_ancienne(tmp_path):
    enregistree(tmp_path, "2026-09-11_15-12-00", "Vexin")
    enregistree(tmp_path, "2026-09-12_08-30-00", "Vallée de Chevreuse")
    (tmp_path / "2026-09-13_07-00-00.json").write_text("{", encoding="utf-8")       # illisible
    (tmp_path / "2026-09-13_09-00-00.json.tmp").write_text("{}", encoding="utf-8")  # écriture pas finie
    rides = history.load(tmp_path)
    assert [(ride["id"], ride["name"]) for ride in rides] == [
        ("2026-09-12_08-30-00", "Vallée de Chevreuse"),
        ("2026-09-11_15-12-00", "Vexin"),
    ]
    assert history.load(tmp_path / "absent") == []


def test_suppression(tmp_path):
    enregistree(tmp_path, "2026-09-11_15-12-00", "Vexin")
    enregistree(tmp_path, "2026-09-12_08-30-00", "Vallée de Chevreuse")
    history.remove("2026-09-11_15-12-00", tmp_path)
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "2026-09-12_08-30-00.fit", "2026-09-12_08-30-00.json"]


def test_fichiers_temporaires_d_une_coupure_effaces(tmp_path):
    enregistree(tmp_path, "2026-09-11_15-12-00", "Vexin")
    (tmp_path / "2026-09-12_08-30-00.fit.tmp").write_bytes(b"a moitie")
    (tmp_path / "2026-09-12_08-30-00.json.tmp").write_bytes(b"{")
    history.clean(tmp_path)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["2026-09-11_15-12-00.fit", "2026-09-11_15-12-00.json"]
    history.clean(tmp_path / "absent")  # pas de dossier : rien à faire


def test_seuls_les_fichiers_fit_orphelins_sont_effaces(tmp_path):
    enregistree(tmp_path, "2026-09-11_15-12-00", "Vexin")      # sortie complète, partie à la même seconde
    (tmp_path / "2026-09-11_15-12-00-2.fit").write_bytes(b"")  # enregistrement raté d'une autre sortie
    history.remove_orphans(datetime(2026, 9, 11, 15, 12, tzinfo=timezone(timedelta(hours=2))), tmp_path)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["2026-09-11_15-12-00.fit", "2026-09-11_15-12-00.json"]
