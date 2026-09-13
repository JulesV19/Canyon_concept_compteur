"""Écritures sur la carte SD : fichiers écrits d'un coup et forcés sur la carte, et un fil d'écriture qui ne fait jamais
attendre l'écran.

Sur ext4, un fichier écrit puis renommé peut, après une coupure de courant, apparaître vide : le renommage atteint la
carte avant les données. Chaque fichier est donc forcé sur la carte (fsync) avant d'être renommé, puis son dossier.

Forcer une écriture prend quelques millisecondes sur le Pi, parfois bien plus quand la carte range ses blocs. Tout ce qui
touche aux fichiers des sorties passe donc par un seul fil, dans l'ordre où on le lui confie : le fichier de reprise pendant
la sortie, puis l'enregistrement, puis l'effacement du fichier de reprise.
"""

import errno
import functools
import os
import queue
import sys
import threading
from collections.abc import Callable
from pathlib import Path


def sync_dir(folder: Path) -> None:
    """Force sur la carte le contenu d'un dossier : fichier créé, renommé ou effacé."""
    descriptor = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_atomic(path: Path, data: bytes) -> None:
    """Écrit un fichier d'un coup : un fichier temporaire forcé sur la carte, puis renommé. Même si le courant est coupé,
    on trouve l'ancien fichier ou le nouveau, jamais un fichier vide ou à moitié écrit. En cas d'échec (carte pleine...),
    le fichier temporaire est effacé et l'erreur remonte."""
    temporary = path.with_name(path.name + ".tmp")
    try:
        with open(temporary, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass  # carte en lecture seule : l'erreur d'origine compte davantage
        raise
    sync_dir(path.parent)


def describe(error: BaseException) -> str:
    """Une erreur d'écriture en quelques mots, pour l'écran."""
    if isinstance(error, OSError):
        if error.errno == errno.ENOSPC:
            return "carte SD pleine"
        if error.errno == errno.EROFS:
            return "carte SD en lecture seule"
        if error.errno in (errno.EACCES, errno.EPERM):
            return "écriture refusée"
        return "erreur d'écriture"
    return "erreur inattendue"


class Writer:
    """Fil d'écriture : les tâches passent une à une, dans l'ordre où on les confie. Une tâche qui échoue n'arrête pas
    le fil. `post(fonction)` doit faire appeler la fonction sur le fil de l'interface (voir app.py) : c'est là qu'arrive
    le résultat de chaque tâche."""

    def __init__(self, post: Callable[[Callable[[], None]], None]):
        self._post = post
        self._tasks: queue.SimpleQueue = queue.SimpleQueue()
        self._thread = threading.Thread(target=self._run, name="ecriture", daemon=True)
        self._thread.start()

    def submit(self, task: Callable[[], object],
               done: Callable[[object, Exception | None], None] | None = None) -> None:
        """Confie une tâche. `done(résultat, erreur)` suit sur le fil de l'interface, avec l'erreur ou None. Sans `done`,
        une erreur est seulement signalée dans la console."""
        self._tasks.put((task, done))

    def close(self, timeout: float = 10.0) -> bool:
        """Finit les tâches en attente, puis arrête le fil. Faux si elles n'ont pas fini à temps."""
        self._tasks.put(None)
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _run(self) -> None:
        while (item := self._tasks.get()) is not None:
            task, done = item
            try:
                result, error = task(), None
            except Exception as exc:
                result, error = None, exc
                if done is None:
                    print(f"Écriture impossible : {exc!r}", file=sys.stderr, flush=True)
            if done is not None:
                self._post(functools.partial(done, result, error))
