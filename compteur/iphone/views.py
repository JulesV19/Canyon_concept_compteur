"""Listes pour l'écran : conversations, appels récents, pastilles, appel qui sonne."""

from datetime import datetime

from .ancs import Notification
from .state import State

CALLS = ("incoming_call", "missed_call", "voicemail")
CALL_LABELS = {"incoming_call": "Appel entrant", "missed_call": "Appel manqué", "voicemail": "Messagerie vocale"}
WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
ANSWERED_S = 120  # un appel entrant suivi d'un « appel manqué » du même nom dans les 2 min n'a pas été pris
STAMP_GAP_S = 3600  # dans une conversation, l'heure revient au-dessus d'un message après une heure de silence


def time_label(date: datetime | None, now: datetime) -> str:
    """Comme les listes d'iOS : « 10:42 » aujourd'hui, « Hier », le jour de la semaine, puis la date."""
    if date is None:
        return ""
    days = (now.date() - date.date()).days
    if days <= 0:
        return f"{date:%H:%M}"
    if days == 1:
        return "Hier"
    if days < 7:
        return WEEKDAYS[date.weekday()]
    return f"{date:%d/%m/%Y}"


def day_label(date: datetime, now: datetime) -> str:
    """Jour d'un message : « Aujourd'hui », « Hier », « lundi », puis la date."""
    days = (now.date() - date.date()).days
    return "Aujourd'hui" if days <= 0 else "Hier" if days == 1 else WEEKDAYS[date.weekday()] if days < 7 \
        else f"{date:%d/%m/%Y}"


def initials(name: str) -> str:
    """« Léa Martin » → « LM » ; un numéro n'a pas d'initiales (la pastille montre alors une silhouette)."""
    words = [word for word in name.split() if word[:1].isalpha()]
    return "".join(word[0] for word in words[:2]).upper()


def conversations(state: State, kind: str, now: datetime) -> list[dict]:
    """Messages de cette appli regroupés par expéditeur, la conversation la plus récente en premier."""
    groups: dict[str, list[Notification]] = {}
    for item in state.history.values():
        if item.kind == kind and item.category not in CALLS:
            groups.setdefault(item.title, []).append(item)
    out = []
    for name, items in groups.items():
        last = items[-1]
        messages = []
        previous = None
        for item in items:
            gap = item.date and (previous is None or (item.date - previous).total_seconds() > STAMP_GAP_S)
            # « stamp » : l'heure au-dessus des bulles de Messages (« Aujourd'hui 16:12 »), après une heure de silence ;
            # « day » : le jour, que WhatsApp montre à chaque changement
            messages.append({"text": item.message, "sender": item.subtitle, "initials": initials(item.subtitle),
                             "time": f"{item.date:%H:%M}" if item.date else "",
                             "day": day_label(item.date, now) if item.date else "",
                             "stamp": f"{day_label(item.date, now)} {item.date:%H:%M}" if gap else ""})
            previous = item.date or previous
        out.append({
            "name": name,
            "initials": initials(name),
            "text": last.message,
            "sender": last.subtitle,  # dans un groupe : qui a écrit le dernier message
            "time": time_label(last.date, now),
            "unread": sum(1 for item in items if item.uid not in state.read and not item.pre_existing),
            "messages": messages,
            "sortKey": last.date.timestamp() if last.date else 0.0,  # pour comparer Messages et WhatsApp
        })
    out.sort(key=lambda conversation: conversation["sortKey"], reverse=True)
    return out


def recents(state: State, now: datetime) -> list[dict]:
    """Appels, du plus récent au plus ancien ; plusieurs appels de suite du même nom n'en font qu'une ligne (« (2) »)."""
    calls = [item for item in state.history.values() if item.category in CALLS]
    shown = []
    for i, item in enumerate(calls):
        if item.category == "incoming_call" and item.date and any(
                later.category == "missed_call" and later.title == item.title and later.date
                and 0 <= (later.date - item.date).total_seconds() <= ANSWERED_S for later in calls[i + 1:]):
            continue  # la sonnerie d'un appel manqué : l'appel manqué suffit
        shown.append(item)
    shown.sort(key=lambda item: item.date or datetime.min, reverse=True)
    out: list[dict] = []
    for item in shown:
        if out and out[-1]["name"] == item.title and out[-1]["category"] == item.category:
            out[-1]["count"] += 1
            continue
        out.append({"name": item.title, "initials": initials(item.title), "category": item.category,
                    "label": CALL_LABELS[item.category], "app": item.kind, "time": time_label(item.date, now), "count": 1})
    return out


def unread(state: State) -> dict[str, int]:
    """Pastilles des icônes : messages pas vus sur le compteur, et appels manqués pour Téléphone."""
    counts = {"phone": 0, "messages": 0, "whatsapp": 0}
    for uid, item in state.history.items():
        if uid in state.read or item.pre_existing:
            continue
        if item.category == "missed_call":
            counts["phone"] += 1
        elif item.category not in CALLS and item.kind in counts:
            counts[item.kind] += 1
    return counts


def ringing(state: State) -> Notification | None:
    """L'appel qui sonne en ce moment, s'il y en a un (sa notification est encore sur l'iPhone)."""
    calls = [item for item in state.notifications.values() if item.category == "incoming_call"]
    return calls[-1] if calls else None
