"""ANCS (Apple Notification Center Service) : décodage des notifications de l'iPhone et commandes d'actions."""

import struct
from dataclasses import dataclass
from datetime import datetime


ANCS_SERVICE = "7905f431-b5ce-4e99-a40f-4b1e122d00d0"
ANCS_NOTIFICATION_SOURCE = "9fbf120d-6301-42d9-8c58-25e699a21dbd"
ANCS_CONTROL_POINT = "69d1d8f3-45e1-49a8-9821-9bbdfdaad9d9"
ANCS_DATA_SOURCE = "22eac6e9-24d6-4bb5-be44-b36ace7c7bfb"

ADDED, MODIFIED, REMOVED = 0, 1, 2
FLAG_SILENT, FLAG_IMPORTANT, FLAG_PRE_EXISTING, FLAG_POSITIVE, FLAG_NEGATIVE = 1, 2, 4, 8, 16
CATEGORIES = {0: "other", 1: "incoming_call", 2: "missed_call", 3: "voicemail", 4: "social", 5: "schedule",
              6: "email", 7: "news", 8: "health", 9: "business", 10: "location", 11: "entertainment",
              12: "active_call"}

GET_NOTIFICATION_ATTRIBUTES, PERFORM_ACTION = 0, 2
ACTION_POSITIVE, ACTION_NEGATIVE = 0, 1
# Attributs demandés, avec leur longueur maximale (None : sans longueur). D'abord l'appli seule : l'iPhone en garde
# souvent plus de 100 (actualités, mails…), qu'il serait long de relire en entier à chaque connexion
ATTR_APP, ATTR_TITLE, ATTR_SUBTITLE, ATTR_MESSAGE, ATTR_DATE, ATTR_POSITIVE, ATTR_NEGATIVE = 0, 1, 2, 3, 5, 6, 7
APP_ONLY = [(ATTR_APP, None)]
REQUESTED = [(ATTR_APP, None), (ATTR_TITLE, 64), (ATTR_SUBTITLE, 64), (ATTR_MESSAGE, 400), (ATTR_DATE, None),
             (ATTR_POSITIVE, None), (ATTR_NEGATIVE, None)]

# Applis gardées ; les appels WhatsApp passent par CallKit, donc souvent sous « com.apple.mobilephone »
APPS = {"com.apple.mobilephone": "phone", "com.apple.MobileSMS": "messages", "net.whatsapp.WhatsApp": "whatsapp"}


@dataclass(frozen=True)
class SourceEvent:
    """Un message de la « Notification Source » : une notification arrive, change ou s'en va."""
    event: int
    flags: int
    category: str
    uid: int


def parse_source(data: bytes) -> SourceEvent | None:
    if len(data) < 8:
        return None
    event, flags, category, _count, uid = struct.unpack("<BBBBI", data[:8])
    return SourceEvent(event, flags, CATEGORIES.get(category, "other"), uid)


def attributes_request(uid: int, requested=REQUESTED) -> bytes:
    """Commande « Get Notification Attributes » pour la notification uid."""
    out = struct.pack("<BI", GET_NOTIFICATION_ATTRIBUTES, uid)
    for attribute, size in requested:
        out += bytes([attribute]) if size is None else struct.pack("<BH", attribute, size)
    return out


def action_request(uid: int, positive: bool) -> bytes:
    return struct.pack("<BIB", PERFORM_ACTION, uid, ACTION_POSITIVE if positive else ACTION_NEGATIVE)


class AttributesReader:
    """Recolle la réponse de la « Data Source » : elle arrive en morceaux quand elle dépasse un paquet."""

    def __init__(self, requested=REQUESTED):
        self.buffer = b""
        self.requested = requested

    def feed(self, data: bytes) -> tuple[int, dict[int, str]] | None:
        """(uid, {attribut: texte}) une fois la réponse complète ; None tant qu'il manque des morceaux."""
        self.buffer += data
        if len(self.buffer) < 5:
            return None
        command, uid = struct.unpack("<BI", self.buffer[:5])
        if command != GET_NOTIFICATION_ATTRIBUTES:
            self.buffer = b""  # réponse inattendue : on repart de zéro
            return None
        values, at = {}, 5
        for _ in self.requested:
            if len(self.buffer) < at + 3:
                return None
            attribute, size = struct.unpack("<BH", self.buffer[at:at + 3])
            if len(self.buffer) < at + 3 + size:
                return None
            values[attribute] = self.buffer[at + 3:at + 3 + size].decode("utf-8", "replace")
            at += 3 + size
        self.buffer = self.buffer[at:]
        return uid, values


def parse_date(text: str) -> datetime | None:
    """« 20260927T104215 » (heure locale de l'iPhone)."""
    try:
        return datetime.strptime(text, "%Y%m%dT%H%M%S")
    except ValueError:
        return None


@dataclass(frozen=True)
class Notification:
    uid: int
    app: str             # identifiant de l'appli, ex. « com.apple.MobileSMS »
    kind: str            # « phone », « messages », « whatsapp », « other »
    category: str        # « incoming_call », « missed_call », « social »…
    title: str           # l'expéditeur ou l'appelant
    subtitle: str
    message: str
    date: datetime | None
    positive: str = ""   # libellé de l'action « oui » (« Accepter »), vide s'il n'y en a pas
    negative: str = ""   # libellé de l'action « non » (« Refuser »)
    pre_existing: bool = False  # déjà là quand l'iPhone s'est connecté


def notification(event: SourceEvent, values: dict[int, str]) -> Notification:
    app = values.get(ATTR_APP, "")
    return Notification(
        uid=event.uid, app=app, kind=APPS.get(app, "other"), category=event.category,
        title=values.get(ATTR_TITLE, ""), subtitle=values.get(ATTR_SUBTITLE, ""),
        message=values.get(ATTR_MESSAGE, ""), date=parse_date(values.get(ATTR_DATE, "")),
        positive=values.get(ATTR_POSITIVE, "") if event.flags & FLAG_POSITIVE else "",
        negative=values.get(ATTR_NEGATIVE, "") if event.flags & FLAG_NEGATIVE else "",
        pre_existing=bool(event.flags & FLAG_PRE_EXISTING))
