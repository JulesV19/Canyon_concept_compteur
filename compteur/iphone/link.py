"""Liaison BlueZ sur D-Bus (dbus-fast, Linux seul), dans un fil à part."""

import asyncio
import threading
from collections.abc import Callable

from .ams import AMS_ENTITY_ATTRIBUTE, AMS_ENTITY_UPDATE, AMS_REMOTE_COMMAND, BATTERY_LEVEL, COMMANDS, SUBSCRIPTIONS, \
    EntityUpdate, parse_entity_update
from .ancs import ANCS_CONTROL_POINT, ANCS_DATA_SOURCE, ANCS_NOTIFICATION_SOURCE, ANCS_SERVICE, APP_ONLY, APPS, \
    ATTR_APP, REMOVED, REQUESTED, AttributesReader, action_request, attributes_request, notification, parse_source
from .bluez import LOCAL_NAME, services
from .state import PhoneState

BLUEZ = "org.bluez"
ADAPTER_PATH = "/org/bluez/hci0"
AGENT_PATH = "/compteur/agent"
ADVERTISEMENT_PATH = "/compteur/advertisement"
SCAN_S = 2.0             # recherche d'un iPhone connecté toutes les 2 s
ANSWER_S = 5.0           # attente maximale d'une réponse d'ANCS


def _value(variant):
    return getattr(variant, "value", variant)


def _on_value(handler: Callable[[bytes], None]):
    """Écoute de PropertiesChanged : dbus-fast veut une fonction à trois paramètres exactement."""
    def changed(interface, values, invalidated):
        if "Value" in values:
            handler(bytes(_value(values["Value"])))
    return changed


class Link:
    """Tient la liaison avec l'iPhone dans un fil à part, avec sa propre boucle asyncio."""

    def __init__(self, phone: PhoneState, log: Callable[[str], None] = lambda text: None):
        self.phone = phone
        self.log = log
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.bus = None
        self.device: str | None = None       # chemin D-Bus de l'iPhone suivi
        self.chars: dict[str, object] = {}   # uuid → interface GattCharacteristic1
        self.watched: list = []              # interfaces Properties écoutées, à lâcher à la déconnexion
        self.requests: asyncio.Queue | None = None
        self.answer: asyncio.Future | None = None
        self.reader = AttributesReader()
        self.ignored: set[int] = set()       # notifications d'autres applis, déjà écartées
        self.tasks: set[asyncio.Task] = set()  # tâches en cours : asyncio n'en garde qu'une référence faible
        self.failed = False                  # Bluetooth hors d'usage (adaptateur absent, BlueZ arrêté…)

    # Depuis n'importe quel fil

    def start(self) -> "Link":
        self.thread = threading.Thread(target=self._run, name="iphone", daemon=True)
        self.thread.start()
        return self

    def _run(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception as error:
            self.log(f"Bluetooth hors d'usage : {error!r}")
        finally:
            self.failed = True
            self.loop = None  # boucle fermée : les commandes sont ignorées au lieu d'échouer

    def music_command(self, name: str) -> None:
        self._call(self._write(AMS_REMOTE_COMMAND, bytes([COMMANDS[name]])))

    def notification_action(self, uid: int, positive: bool) -> None:
        self._call(self._write(ANCS_CONTROL_POINT, action_request(uid, positive)))

    def _call(self, coroutine) -> None:
        loop = self.loop
        try:
            if loop is None:
                raise RuntimeError("pas de boucle")
            asyncio.run_coroutine_threadsafe(coroutine, loop)
        except RuntimeError:  # liaison arrêtée, ou boucle fermée à l'instant
            coroutine.close()

    # Dans le fil Bluetooth

    async def _main(self) -> None:
        from dbus_fast import BusType
        from dbus_fast.aio import MessageBus
        self.loop = asyncio.get_running_loop()
        self.requests = asyncio.Queue()
        self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        await self._setup_adapter()
        self._spawn(self._serve_requests())
        manager = await self._interface("/", "org.freedesktop.DBus.ObjectManager")
        while True:
            try:
                await self._scan(await manager.call_get_managed_objects())
            except Exception as error:  # iPhone parti au milieu d'un échange : on reprend au tour suivant
                self.log(f"liaison : {error!r}")
                await self._drop()
            await asyncio.sleep(SCAN_S)

    def _spawn(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _interface(self, path: str, name: str):
        introspection = await self.bus.introspect(BLUEZ, path)
        return self.bus.get_proxy_object(BLUEZ, path, introspection).get_interface(name)

    async def _setup_adapter(self) -> None:
        agent, advertisement = services()
        adapter = await self._interface(ADAPTER_PATH, "org.bluez.Adapter1")
        await adapter.set_powered(True)
        await adapter.set_alias(LOCAL_NAME)
        await adapter.set_pairable(True)
        self.bus.export(AGENT_PATH, agent)
        agents = await self._interface("/org/bluez", "org.bluez.AgentManager1")
        await agents.call_register_agent(AGENT_PATH, "NoInputNoOutput")
        await agents.call_request_default_agent(AGENT_PATH)
        self.bus.export(ADVERTISEMENT_PATH, advertisement)
        advertising = await self._interface(ADAPTER_PATH, "org.bluez.LEAdvertisingManager1")
        await advertising.call_register_advertisement(ADVERTISEMENT_PATH, {})
        self.log("annonce en cours : iPhone > Réglages > Bluetooth > « Compteur »")

    async def _scan(self, objects: dict) -> None:
        """Repère l'iPhone connecté qui offre ANCS, s'y abonne ; lâche tout quand il s'en va."""
        if self.device:
            device = objects.get(self.device, {}).get("org.bluez.Device1")
            if not device or not _value(device["Connected"]):
                await self._drop()
            return
        for path, interfaces in objects.items():
            device = interfaces.get("org.bluez.Device1")
            if not device or not _value(device["Connected"]):
                continue
            services = {_value(ifs["org.bluez.GattService1"]["UUID"]) for p, ifs in objects.items()
                        if p.startswith(path + "/") and "org.bluez.GattService1" in ifs}
            if ANCS_SERVICE not in services:
                if not _value(device["Paired"]) and _value(device.get("ServicesResolved", False)):
                    # ANCS n'apparaît qu'une fois le lien chiffré : on demande l'appairage
                    self.log(f"appairage avec {path}")
                    await (await self._interface(path, "org.bluez.Device1")).call_pair()
                continue
            chars = {_value(ifs["org.bluez.GattCharacteristic1"]["UUID"]): p for p, ifs in objects.items()
                     if p.startswith(path + "/") and "org.bluez.GattCharacteristic1" in ifs}
            self.device = path
            await self._subscribe(chars)
            name = _value(device.get("Alias", "")) or _value(device.get("Name", ""))
            self.phone.connection(True, name)
            self.log(f"connecté à {name}")
            return

    async def _subscribe(self, paths: dict[str, str]) -> None:
        for uuid in (ANCS_CONTROL_POINT, ANCS_DATA_SOURCE, ANCS_NOTIFICATION_SOURCE, AMS_REMOTE_COMMAND,
                     AMS_ENTITY_UPDATE, AMS_ENTITY_ATTRIBUTE):
            if uuid in paths:
                self.chars[uuid] = await self._interface(paths[uuid], "org.bluez.GattCharacteristic1")
        # Data Source avant Notification Source : sinon on perdrait les réponses aux premières notifications
        for uuid, handler in ((ANCS_DATA_SOURCE, self._on_data), (ANCS_NOTIFICATION_SOURCE, self._on_source),
                              (AMS_ENTITY_UPDATE, self._on_entity)):
            if uuid not in paths:
                continue
            properties = await self._interface(paths[uuid], "org.freedesktop.DBus.Properties")
            changed = _on_value(handler)
            properties.on_properties_changed(changed)
            self.watched.append((properties, changed))
            await self.chars[uuid].call_start_notify()
        if AMS_ENTITY_UPDATE in self.chars:
            for subscription in SUBSCRIPTIONS:
                await self._write(AMS_ENTITY_UPDATE, subscription)
        if BATTERY_LEVEL in paths:
            battery = await self._interface(paths[BATTERY_LEVEL], "org.bluez.GattCharacteristic1")
            level = bytes(await battery.call_read_value({}))
            if level:
                self.phone.battery(level[0])
            properties = await self._interface(paths[BATTERY_LEVEL], "org.freedesktop.DBus.Properties")
            changed = _on_value(lambda data: data and self.phone.battery(data[0]))
            properties.on_properties_changed(changed)
            self.watched.append((properties, changed))
            await battery.call_start_notify()

    async def _drop(self) -> None:
        if self.phone.snapshot().connected:
            self.log("iPhone déconnecté")
            self.phone.connection(False)
        for properties, changed in self.watched:
            properties.off_properties_changed(changed)
        self.device, self.chars, self.watched = None, {}, []
        self.ignored.clear()

    async def _write(self, uuid: str, data: bytes) -> None:
        from dbus_fast import Variant
        char = self.chars.get(uuid)
        if char:
            await char.call_write_value(data, {"type": Variant("s", "request")})

    def _on_source(self, data: bytes) -> None:
        event = parse_source(data)
        if not event:
            return
        if event.event == REMOVED:
            self.phone.removed(event.uid)
            self.ignored.discard(event.uid)
        else:
            self.requests.put_nowait(event)

    def _on_data(self, data: bytes) -> None:
        answer = self.reader.feed(data)
        if answer and self.answer and not self.answer.done():
            self.answer.set_result(answer)

    def _on_entity(self, data: bytes) -> None:
        update = parse_entity_update(data)
        if not update:
            return
        if update.truncated:
            self._spawn(self._full_attribute(update))
        self.phone.music_update(update.entity, update.attribute, update.value)

    async def _full_attribute(self, update: EntityUpdate) -> None:
        """Valeur coupée (titre long) : on la relit en entier ; faute de mieux, la valeur coupée reste."""
        char = self.chars.get(AMS_ENTITY_ATTRIBUTE)
        if char is None:
            return
        try:
            await self._write(AMS_ENTITY_ATTRIBUTE, bytes([update.entity, update.attribute]))
            value = bytes(await char.call_read_value({})).decode("utf-8", "replace")
        except Exception as error:
            self.log(f"attribut {update.entity}/{update.attribute} illisible : {error!r}")
            return
        self.phone.music_update(update.entity, update.attribute, value)

    async def _serve_requests(self) -> None:
        """Une demande d'attributs à la fois : les réponses de la Data Source ne disent pas à quoi elles répondent."""
        while True:
            event = await self.requests.get()
            if not self.device or event.uid in self.ignored:
                continue
            try:
                if event.uid not in self.phone.snapshot().notifications:
                    app = (await self._ask(event.uid, APP_ONLY)).get(ATTR_APP, "")
                    if app not in APPS:
                        self.ignored.add(event.uid)
                        continue
                values = await self._ask(event.uid, REQUESTED)
            except Exception as error:
                self.log(f"notification {event.uid} illisible : {error!r}")
                continue
            self.phone.notification(notification(event, values))

    async def _ask(self, uid: int, requested) -> dict[int, str]:
        self.reader = AttributesReader(requested)
        self.answer = self.loop.create_future()
        await self._write(ANCS_CONTROL_POINT, attributes_request(uid, requested))
        answered, values = await asyncio.wait_for(self.answer, ANSWER_S)
        if answered != uid:
            raise ValueError(f"réponse pour {answered}")
        return values
