import struct
from datetime import datetime

from compteur.iphone import (APP_ONLY, ATTR_APP, ATTR_DATE, ATTR_MESSAGE, ATTR_NEGATIVE, ATTR_POSITIVE, ATTR_SUBTITLE,
                             ATTR_TITLE, FLAG_NEGATIVE, FLAG_POSITIVE, FLAG_PRE_EXISTING, PLAYER, PLAYER_NAME,
                             PLAYER_PLAYBACK, PLAYER_VOLUME, REMOVED, TRACK, TRACK_DURATION, TRACK_TITLE,
                             AttributesReader, Music, PhoneState, action_request, apply_update, attributes_request,
                             notification, parse_entity_update, parse_source)


def answer(uid: int, values: dict[int, str]) -> bytes:
    """Réponse de la Data Source, attributs dans l'ordre demandé."""
    out = struct.pack("<BI", 0, uid)
    for attribute in (ATTR_APP, ATTR_TITLE, ATTR_SUBTITLE, ATTR_MESSAGE, ATTR_DATE, ATTR_POSITIVE, ATTR_NEGATIVE):
        data = values.get(attribute, "").encode()
        out += struct.pack("<BH", attribute, len(data)) + data
    return out


def test_source():
    event = parse_source(bytes([0, FLAG_POSITIVE | FLAG_NEGATIVE, 1, 1]) + struct.pack("<I", 42))
    assert (event.event, event.category, event.uid) == (0, "incoming_call", 42)
    assert parse_source(bytes([REMOVED, 0, 4, 1]) + struct.pack("<I", 7)).event == REMOVED
    assert parse_source(b"\x00\x00") is None


def test_demandes():
    request = attributes_request(0x01020304)
    assert request[:5] == bytes([0, 4, 3, 2, 1])
    assert request[5:] == bytes([0, 1, 64, 0, 2, 64, 0, 3, 144, 1, 5, 6, 7])  # message : 400 octets au plus
    assert action_request(9, True) == bytes([2, 9, 0, 0, 0, 0])
    assert action_request(9, False)[-1] == 1


def test_reponse_en_morceaux():
    data = answer(5, {ATTR_APP: "com.apple.MobileSMS", ATTR_TITLE: "Léa", ATTR_MESSAGE: "On se retrouve où ?",
                      ATTR_DATE: "20260927T104215"})
    reader = AttributesReader()
    assert reader.feed(data[:4]) is None
    assert reader.feed(data[4:20]) is None
    uid, values = reader.feed(data[20:])
    assert uid == 5 and values[ATTR_TITLE] == "Léa" and values[ATTR_MESSAGE] == "On se retrouve où ?"
    assert reader.buffer == b""


def test_notification():
    event = parse_source(bytes([0, FLAG_POSITIVE | FLAG_NEGATIVE | FLAG_PRE_EXISTING, 1, 1]) + struct.pack("<I", 3))
    item = notification(event, {ATTR_APP: "com.apple.mobilephone", ATTR_TITLE: "Paul", ATTR_POSITIVE: "Accepter",
                                ATTR_NEGATIVE: "Refuser", ATTR_DATE: "20260927T104215"})
    assert item.kind == "phone" and item.category == "incoming_call" and item.pre_existing
    assert (item.positive, item.negative) == ("Accepter", "Refuser")
    assert item.date == datetime(2026, 9, 27, 10, 42, 15)
    # Sans le drapeau, le libellé de l'action n'est pas gardé
    event = parse_source(bytes([0, 0, 4, 1]) + struct.pack("<I", 4))
    item = notification(event, {ATTR_APP: "com.example", ATTR_POSITIVE: "Ouvrir"})
    assert item.kind == "other" and item.positive == "" and item.date is None


def test_musique():
    update = parse_entity_update(bytes([TRACK, TRACK_TITLE, 1]) + "Titre coupé".encode())
    assert update.truncated and update.value == "Titre coupé"
    music = Music()
    music = apply_update(music, PLAYER, PLAYER_NAME, "Musique", 0)
    music = apply_update(music, TRACK, TRACK_DURATION, "200.5", 0)
    music = apply_update(music, PLAYER, PLAYER_PLAYBACK, "1,1.0,30.0", 10.0)
    music = apply_update(music, PLAYER, PLAYER_VOLUME, "0.5", 10.0)
    assert music.playing and music.player == "Musique" and music.volume == 0.5
    assert music.position(15.0) == 35.0
    assert music.position(1000.0) == 200.5  # jamais au-delà de la fin
    music = apply_update(music, PLAYER, PLAYER_PLAYBACK, "0,0.0,40.0", 20.0)
    assert not music.playing and music.position(99.0) == 40.0
    assert apply_update(music, PLAYER, PLAYER_PLAYBACK, "abîmé", 0) == music


def test_etat():
    events = []
    phone = PhoneState(listener=lambda kind, data: events.append(kind))
    phone.connection(True, "iPhone")
    event = parse_source(bytes([0, 0, 4, 1]) + struct.pack("<I", 1))
    phone.notification(notification(event, {ATTR_APP: "com.apple.MobileSMS"}))
    phone.notification(notification(event, {ATTR_APP: "com.apple.MobileSMS", ATTR_MESSAGE: "suite"}))
    phone.removed(1)
    phone.removed(1)  # déjà partie : rien
    phone.music_update(TRACK, TRACK_TITLE, "Titre")
    assert phone.snapshot().music.title == "Titre"
    phone.connection(False)
    assert events == ["connected", "added", "modified", "removed", "music", "disconnected"]
    assert phone.snapshot().notifications == {} and phone.snapshot().music == Music()


def test_appli_seule():
    assert attributes_request(1, APP_ONLY) == bytes([0, 1, 0, 0, 0, 0])
    data = struct.pack("<BIBH", 0, 1, ATTR_APP, 5) + b"a.b.c"
    assert AttributesReader(APP_ONLY).feed(data) == (1, {ATTR_APP: "a.b.c"})


def test_ecrans():
    """Ce que montre la page CarPlay : conversations regroupées, heure au-dessus des bulles après une heure de silence,
    Récents sans la sonnerie d'un appel manqué, pastilles des non-lus."""
    from compteur.iphone import Notification, conversations, recents, unread

    now = datetime(2026, 9, 27, 16, 0)
    phone = PhoneState(clock=lambda: 0.0)
    items = [
        (1, "messages", "social", "Papa", "", "Bien rentré ?", datetime(2026, 9, 26, 9, 0), True),
        (2, "messages", "social", "Léa", "", "Tu rentres ?", datetime(2026, 9, 27, 14, 0), False),
        (3, "messages", "social", "Léa", "", "On dîne dehors", datetime(2026, 9, 27, 14, 20), False),
        (4, "messages", "social", "Léa", "", "À tout !", datetime(2026, 9, 27, 15, 30), False),
        (5, "whatsapp", "social", "Groupe", "Thomas", "Départ 8 h 30", datetime(2026, 9, 27, 15, 0), False),
        (6, "phone", "incoming_call", "Maman", "", "", datetime(2026, 9, 27, 15, 40), False),
        (7, "phone", "missed_call", "Maman", "", "", datetime(2026, 9, 27, 15, 40, 30), False),
        (8, "phone", "missed_call", "Maman", "", "", datetime(2026, 9, 27, 15, 45), False),
    ]
    for uid, kind, category, title, subtitle, message, date, old in items:
        phone.notification(Notification(uid, "", kind, category, title, subtitle, message, date, "", "", old))
    state = phone.snapshot()

    lea, papa = conversations(state, "messages", now)
    assert (lea["name"], lea["text"], lea["time"], lea["unread"], lea["initials"]) == \
        ("Léa", "À tout !", "15:30", 3, "L")
    assert [m["stamp"] for m in lea["messages"]] == ["Aujourd'hui 14:00", "", "Aujourd'hui 15:30"]
    assert (papa["time"], papa["unread"], papa["messages"][0]["day"]) == ("Hier", 0, "Hier")
    group, = conversations(state, "whatsapp", now)
    assert (group["sender"], group["messages"][0]["initials"]) == ("Thomas", "T")

    assert recents(state, now) == [{"name": "Maman", "initials": "M", "category": "missed_call",
                                    "label": "Appel manqué", "app": "phone", "time": "15:45", "count": 2}]
    assert unread(state) == {"phone": 2, "messages": 3, "whatsapp": 1}
    phone.mark_read("messages")
    assert unread(phone.snapshot())["messages"] == 0


def test_aleatoire_repetition_et_batterie():
    """Modes de la file (AMS) et charge de l'iPhone (service Batterie), gardés dans l'état partagé."""
    from compteur.iphone import QUEUE, QUEUE_REPEAT, QUEUE_SHUFFLE

    phone = PhoneState(clock=lambda: 0.0)
    phone.music_update(QUEUE, QUEUE_SHUFFLE, "2")
    phone.music_update(QUEUE, QUEUE_REPEAT, "1")
    phone.battery(42)
    state = phone.snapshot()
    assert (state.music.shuffle, state.music.repeat, state.battery) == (2, 1, 42)
    phone.connection(False)
    assert phone.snapshot().battery == -1


def test_liaison_hors_d_usage():
    """Sans Bluetooth (ici : pas de BlueZ sur le Mac), le fil s'arrête proprement et les commandes sont ignorées."""
    from compteur.iphone import Link
    logs = []
    link = Link(PhoneState(), log=logs.append)
    link._main = lambda: (_ for _ in ()).throw(OSError("pas d'adaptateur"))  # échoue dès le départ
    link.start().thread.join(5)
    assert link.failed and link.loop is None and logs
    link.music_command("toggle")  # ne lève rien
    link.notification_action(1, True)


def test_listes_relues_a_minuit(monkeypatch):
    """« 10:42 » devient « Hier » le lendemain, même si l'iPhone n'a rien envoyé."""
    import compteur.model.phone as model
    from compteur.iphone import Notification

    days = iter([datetime(2026, 9, 27, 23, 59), datetime(2026, 9, 28, 0, 1)])

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(days)

    phone = PhoneState()
    phone.connection(True, "iPhone")
    phone.notification(Notification(1, "com.apple.MobileSMS", "messages", "social", "Léa", "", "Coucou",
                                    datetime(2026, 9, 27, 10, 42)))
    monkeypatch.setattr(model, "datetime", Clock)
    phone_model = model.PhoneModel(phone)
    assert phone_model.messages[0]["time"] == "10:42"
    phone_model.refresh()
    assert phone_model.messages[0]["time"] == "Hier"
