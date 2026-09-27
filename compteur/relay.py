"""Relais entre un fil de travail et le fil de l'interface."""

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot


class Relay(QObject):
    """Fait passer des fonctions d'un autre fil au fil de l'interface (résultats du fil d'écriture)."""

    _call = Signal(object)

    def __init__(self):
        super().__init__()
        self._call.connect(self._run)

    @Slot(object)
    def _run(self, function: Callable[[], None]) -> None:
        function()

    def post(self, function: Callable[[], None]) -> None:
        self._call.emit(function)
