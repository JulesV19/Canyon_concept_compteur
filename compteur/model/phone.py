"""PhoneModel : l'iPhone, exposé à la page CarPlay."""

from datetime import datetime

from PySide6.QtCore import Property, QObject, Signal, Slot

from .. import iphone


class PhoneModel(QObject):
    """Expose l'iPhone à la page CarPlay : `phone.values` (connexion, morceau en cours, pastilles, appel qui sonne),
    `phone.messages`, `phone.whatsapp` et `phone.recents` (listes). Comme le reste de l'écran, il ne change qu'au tic de
    chaque seconde (refresh), et les listes seulement quand l'iPhone a envoyé du nouveau. `link` : la liaison
    (`iphone.Link`, ou l'iPhone simulé), None s'il n'y en a pas (Bluetooth absent)."""

    changed = Signal()
    listsChanged = Signal()
    messageArrived = Signal("QVariantMap")  # nouveau message pendant qu'on roule : pour son bandeau

    def __init__(self, phone: iphone.PhoneState, link=None, parent: QObject | None = None):
        super().__init__(parent)
        self.phone = phone
        self.link = link
        self.version = -1
        self.day = None  # les heures des listes (« 10:42 », « Hier ») changent aussi à minuit
        self._values: dict = {}
        self._lists: dict = {"messages": [], "whatsapp": [], "recents": []}
        self.refresh()

    def refresh(self) -> None:
        state = self.phone.snapshot()
        now = datetime.now()
        music = state.music
        call = iphone.ringing(state)
        values = {
            "available": self.link is not None and not getattr(self.link, "failed", False),
            "connected": state.connected,
            "name": state.name,
            "music": {
                "player": music.player, "title": music.title, "artist": music.artist, "album": music.album,
                "durationS": music.duration, "positionS": music.position(self.phone.clock()),
                "playing": music.playing, "volume": music.volume, "shuffle": music.shuffle, "repeat": music.repeat,
            },
            "battery": state.battery,
            "unread": iphone.unread(state),
            "call": {"uid": call.uid, "name": call.title, "initials": iphone.initials(call.title), "app": call.kind}
            if call else None,
        }
        if values != self._values:
            self._values = values
            self.changed.emit()
        if state.version != self.version or now.date() != self.day:
            self.version, self.day = state.version, now.date()
            lists = {"messages": iphone.conversations(state, "messages", now),
                     "whatsapp": iphone.conversations(state, "whatsapp", now),
                     "recents": iphone.recents(state, now)}
            if lists != self._lists:
                self._lists = lists
                self.listsChanged.emit()
        for item in self.phone.take_arrivals():
            if item.category not in iphone.CALLS:
                self.messageArrived.emit({"app": item.kind, "name": item.title, "sender": item.subtitle,
                                          "text": item.message})

    def _command(self, name: str) -> None:
        if self.link is not None:
            self.link.music_command(name)

    @Slot()
    def playPause(self) -> None:
        self._command("toggle")

    @Slot()
    def next(self) -> None:
        self._command("next")

    @Slot()
    def previous(self) -> None:
        self._command("previous")

    @Slot()
    def shuffle(self) -> None:
        self._command("shuffle")

    @Slot()
    def repeat(self) -> None:
        self._command("repeat")

    @Slot()
    def volumeUp(self) -> None:
        self._command("volume_up")

    @Slot()
    def volumeDown(self) -> None:
        self._command("volume_down")

    def _call_action(self, positive: bool) -> None:
        call = self._values.get("call")
        if call and self.link is not None:
            self.link.notification_action(call["uid"], positive)

    @Slot()
    def answer(self) -> None:
        self._call_action(True)

    @Slot()
    def decline(self) -> None:
        self._call_action(False)

    @Slot(str)
    def markRead(self, kind: str) -> None:
        """L'appli est ouverte sur le compteur : ses pastilles s'effacent au tic suivant."""
        self.phone.mark_read(kind)

    def _get_values(self) -> dict:
        return self._values

    def _get_messages(self) -> list:
        return self._lists["messages"]

    def _get_whatsapp(self) -> list:
        return self._lists["whatsapp"]

    def _get_recents(self) -> list:
        return self._lists["recents"]

    values = Property("QVariantMap", _get_values, notify=changed)
    messages = Property("QVariantList", _get_messages, notify=listsChanged)
    whatsapp = Property("QVariantList", _get_whatsapp, notify=listsChanged)
    recents = Property("QVariantList", _get_recents, notify=listsChanged)
