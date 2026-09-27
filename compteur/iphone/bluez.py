"""Les objets que le compteur publie sur D-Bus pour BlueZ : l'agent d'appairage et l'annonce Bluetooth.

dbus-fast n'est importé qu'à l'appel (Linux seul)."""

from .ancs import ANCS_SERVICE

LOCAL_NAME = "Compteur"  # 8 lettres au plus : l'annonce (31 octets) porte déjà la demande d'ANCS


def services() -> tuple[object, object]:
    """(agent, annonce), prêts à publier."""
    from dbus_fast.service import ServiceInterface, dbus_property, method, PropertyAccess

    class Agent(ServiceInterface):
        """Appairage sans code (« Just Works ») : l'iPhone affiche seulement « Associer »."""

        def __init__(self):
            super().__init__("org.bluez.Agent1")

        @method()
        def Release(self): pass

        @method()
        def RequestConfirmation(self, device: "o", passkey: "u"): pass

        @method()
        def RequestAuthorization(self, device: "o"): pass

        @method()
        def AuthorizeService(self, device: "o", uuid: "s"): pass

        @method()
        def Cancel(self): pass

    class Advertisement(ServiceInterface):
        def __init__(self):
            super().__init__("org.bluez.LEAdvertisement1")

        @method()
        def Release(self): pass

        @dbus_property(access=PropertyAccess.READ)
        def Type(self) -> "s":
            return "peripheral"

        @dbus_property(access=PropertyAccess.READ)
        def SolicitUUIDs(self) -> "as":
            return [ANCS_SERVICE]

        @dbus_property(access=PropertyAccess.READ)
        def LocalName(self) -> "s":
            return LOCAL_NAME

        @dbus_property(access=PropertyAccess.READ)
        def Discoverable(self) -> "b":
            return True

    return Agent(), Advertisement()
