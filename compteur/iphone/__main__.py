"""Essai en ligne de commande, sur le Pi : `python -m compteur.iphone`."""

from .ams import Music
from .ancs import Notification
from .link import Link
from .state import PhoneState

HELP = ("p lecture/pause · n suivant · b précédent · + / - volume · "
        "o UID accepter · x UID refuser · l liste · q quitter")


def describe(kind: str, data: object) -> str:
    if isinstance(data, Notification):
        actions = f" [{data.positive} / {data.negative}]" if data.positive or data.negative else ""
        return (f"{kind} #{data.uid} {data.app} {data.category} : {data.title!r} {data.subtitle!r} "
                f"{data.message!r}{actions}")
    if isinstance(data, Music):
        state = "▶" if data.playing else "⏸"
        return (f"musique {state} {data.title!r} — {data.artist!r} ({data.album!r}) "
                f"{data.elapsed:.0f}/{data.duration:.0f} s, volume {data.volume:.2f}, {data.player!r}")
    return f"{kind} {data}"


def main() -> None:
    phone = PhoneState(listener=lambda kind, data: print(describe(kind, data), flush=True))
    link = Link(phone, log=lambda text: print(f"· {text}", flush=True)).start()
    print(HELP, flush=True)
    keys = {"p": "toggle", "n": "next", "b": "previous", "+": "volume_up", "-": "volume_down"}
    while True:
        try:
            words = input().split()
        except EOFError:
            break
        if not words:
            continue
        if words[0] == "q":
            break
        if words[0] in keys:
            link.music_command(keys[words[0]])
        elif words[0] in ("o", "x") and len(words) == 2 and words[1].isdigit():
            link.notification_action(int(words[1]), words[0] == "o")
        elif words[0] == "l":
            for item in phone.snapshot().notifications.values():
                print(describe("·", item))
        else:
            print(HELP)


if __name__ == "__main__":
    main()
