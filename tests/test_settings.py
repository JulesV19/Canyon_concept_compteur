import errno
import json

import pytest

from compteur.settings import Settings, SettingsModel, apply_brightness


def test_reglages_par_defaut_sans_fichier(tmp_path):
    assert Settings.load(tmp_path / "absent.json") == Settings()


def test_enregistrement_et_relecture(tmp_path):
    path = tmp_path / "config" / "reglages.json"
    Settings(max_hr=182, auto_pause=False, brightness=55).save(path)
    assert Settings.load(path) == Settings(max_hr=182, auto_pause=False, brightness=55)


@pytest.mark.parametrize("content", ["{pas du json", "[1, 2]", '{"max_hr": "beaucoup"}'])
def test_fichier_illisible(tmp_path, content):
    path = tmp_path / "reglages.json"
    path.write_text(content, encoding="utf-8")
    assert Settings.load(path) == Settings()


def test_valeurs_ramenees_dans_les_limites(tmp_path):
    path = tmp_path / "reglages.json"
    path.write_text(json.dumps({"max_hr": 300, "brightness": 0, "inconnu": 1}), encoding="utf-8")
    settings = Settings.load(path)
    assert settings.max_hr == 220
    assert settings.brightness == 10
    assert settings.auto_pause


def test_apercu_puis_enregistrement(tmp_path):
    path = tmp_path / "reglages.json"
    model = SettingsModel(path)
    model.preview("brightness", 40)
    assert model.values["brightness"] == 40
    assert not path.exists()  # un aperçu n'enregistre rien
    model.set("maxHr", 180)
    assert Settings.load(path) == Settings(max_hr=180, brightness=40)
    assert model.values["zoneBounds"] == [108, 126, 144, 162]


def test_retroeclairage(tmp_path):
    screen = tmp_path / "ecran"
    screen.mkdir()
    (screen / "max_brightness").write_text("255")
    (screen / "brightness").write_text("0")
    assert apply_brightness(80, tmp_path)
    assert (screen / "brightness").read_text() == "204"
    assert not apply_brightness(80, tmp_path / "sans-ecran")


def test_valeur_infinie(tmp_path):
    """Fichier modifié à la main : int(inf) lèverait OverflowError."""
    path = tmp_path / "reglages.json"
    path.write_text('{"max_hr": Infinity}', encoding="utf-8")
    assert Settings.load(path) == Settings()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "beaucoup"])
def test_apercu_d_une_valeur_illisible_ignore(tmp_path, value):
    model = SettingsModel(tmp_path / "reglages.json")
    model.preview("maxHr", value)
    assert model.values["maxHr"] == Settings().max_hr


def test_carte_qui_refuse_les_reglages(tmp_path, monkeypatch, capsys):
    """Carte pleine ou en lecture seule : le réglage vaut jusqu'à l'arrêt, sans erreur dans l'interface."""
    model = SettingsModel(tmp_path / "reglages.json")

    def refuse(settings, path):
        raise OSError(errno.EROFS, "Read-only file system")

    monkeypatch.setattr(Settings, "save", refuse)
    model.set("maxHr", 180)
    assert model.values["maxHr"] == 180
    assert "Réglages non enregistrés" in capsys.readouterr().err
