import errno
import os
import stat
import threading

import pytest

from compteur.storage import Writer, describe, write_atomic


def test_fichier_force_sur_la_carte_avant_d_etre_renomme(tmp_path, monkeypatch):
    """Données forcées sur la carte, renommage, puis dossier forcé : sans quoi une coupure peut laisser un fichier vide."""
    events = []
    real_fsync, real_replace = os.fsync, os.replace

    def fsync(descriptor):
        events.append("dossier" if stat.S_ISDIR(os.fstat(descriptor).st_mode) else "fichier")
        real_fsync(descriptor)

    def replace(source, target):
        events.append("renommage")
        real_replace(source, target)

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "replace", replace)
    path = tmp_path / "sortie.json"
    write_atomic(path, b"{}")
    assert events == ["fichier", "renommage", "dossier"]
    assert path.read_bytes() == b"{}"
    assert list(tmp_path.iterdir()) == [path]


def test_echec_l_ancien_fichier_reste_intact(tmp_path, monkeypatch):
    path = tmp_path / "reglages.json"
    path.write_bytes(b"ancien")

    def full(descriptor):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(os, "fsync", full)
    with pytest.raises(OSError):
        write_atomic(path, b"nouveau")
    assert path.read_bytes() == b"ancien"
    assert list(tmp_path.iterdir()) == [path]  # pas de fichier temporaire laissé derrière


@pytest.mark.parametrize("error, text", [
    (OSError(errno.ENOSPC, "No space left on device"), "carte SD pleine"),
    (OSError(errno.EROFS, "Read-only file system"), "carte SD en lecture seule"),
    (PermissionError(errno.EACCES, "Permission denied"), "écriture refusée"),
    (OSError(errno.EIO, "Input/output error"), "erreur d'écriture"),
    (ValueError("bogue"), "erreur inattendue"),
])
def test_erreur_en_quelques_mots(error, text):
    assert describe(error) == text


def test_fil_d_ecriture_dans_l_ordre(capsys):
    """Les tâches passent une à une, dans l'ordre, hors du fil qui les confie ; leurs résultats reviennent par `post`,
    et une tâche qui échoue n'arrête pas les suivantes."""
    posted = []
    writer = Writer(posted.append)
    caller = threading.get_ident()
    seen = []
    writer.submit(lambda: seen.append(threading.get_ident() != caller) or "fait",
                  lambda result, error: seen.append((result, error)))
    writer.submit(lambda: 1 / 0, lambda result, error: seen.append((result, type(error))))
    writer.submit(lambda: [][1])  # sans suite : l'erreur est seulement signalée
    writer.submit(lambda: seen.append("suivante"))
    assert writer.close()
    assert seen == [True, "suivante"]  # rien n'est rendu avant de passer par `post`
    for call in posted:
        call()
    assert seen == [True, "suivante", ("fait", None), (None, ZeroDivisionError)]
    assert "Écriture impossible : IndexError" in capsys.readouterr().err
