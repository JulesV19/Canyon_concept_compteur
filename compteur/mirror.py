"""Miroir : l'écran du compteur dans un navigateur, et la souris comme un doigt.

python -m compteur --miroir [PORT], puis http://<machine>.local:PORT (8080 par défaut) depuis le Mac. L'appli tourne
normalement. La page reçoit l'écran en JPEG, au plus 25 images par seconde et seulement quand il change ; elle renvoie
clics, glissés et touches, rejoués sur la fenêtre comme de vrais touchers et de vrais boutons. Sans page ouverte, rien
n'est capturé. Pas de mot de passe : à garder sur le réseau de la maison.

Chaque capture fait redessiner la fenêtre : presque rien avec le GPU, un dessin complet quand c'est le processeur qui
dessine (sur le Pi, l'écran DRM ne sait pas se capturer lui-même). Les captures s'espacent alors pour ne pas prendre
plus de 30 % du temps : le miroir ralentit plutôt que l'appli. L'encodage JPEG (environ 30 ms sur le Pi) se fait sur le
fil de chaque page, pas sur celui de l'interface.
"""

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QCoreApplication, QIODevice, QObject, QPoint, Qt, QTimer, Signal, Slot
from PySide6.QtTest import QTest

PAGE = Path(__file__).with_name("mirror.html")
FONTS = Path(__file__).parent / "ui" / "fonts"
FRAME_MS = 40     # au plus 25 images par seconde
GRAB_SHARE = 0.3  # part du temps que les captures peuvent prendre
RESEND_S = 2      # sans nouvelle image, la dernière repart (page qui vient de s'ouvrir, image perdue)
TOUCH = {"down": "press", "move": "move", "up": "release"}
KEYS = {  # touches de la page → touches du simulateur, qui tiennent lieu de boutons physiques
    "Space": Qt.Key.Key_Space, "Enter": Qt.Key.Key_Return, "Escape": Qt.Key.Key_Escape,
    "Backspace": Qt.Key.Key_Backspace, "ArrowLeft": Qt.Key.Key_Left, "ArrowRight": Qt.Key.Key_Right,
    "ArrowUp": Qt.Key.Key_Up, "ArrowDown": Qt.Key.Key_Down, "L": Qt.Key.Key_L, "P": Qt.Key.Key_P,
    "E": Qt.Key.Key_E, "M": Qt.Key.Key_M, "R": Qt.Key.Key_R,
}


def parse_events(body: str) -> list[tuple]:
    """Événements de la page, un par ligne : « down 120 300 », « move … », « up … » (position dans l'écran, en
    points) ou « key Space ». Le reste est ignoré."""
    events = []
    for line in body.splitlines():
        parts = line.split()
        try:
            if len(parts) == 3 and parts[0] in TOUCH:
                events.append((parts[0], round(float(parts[1])), round(float(parts[2]))))
            elif len(parts) == 2 and parts[0] == "key" and parts[1] in KEYS:
                events.append(("key", parts[1]))
        except ValueError:
            continue
    return events


def encode(image) -> bytes:
    """Capture en JPEG."""
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "JPG", 85)
    return bytes(data)


def capture_interval(grab_ms: float) -> int:
    """Attente entre deux captures, en ms, pour qu'elles ne prennent pas plus de GRAB_SHARE du temps."""
    return max(FRAME_MS, round(grab_ms / GRAB_SHARE))


class Mirror(QObject):
    """Captures et touchers sur le fil de l'interface ; le serveur web tourne sur ses propres fils."""

    received = Signal(object)  # événements de la page, à rejouer sur le fil de l'interface

    def __init__(self, window, port: int = 8080):
        super().__init__()
        self.window = window
        self.size = (window.width(), window.height())
        self.url = f"http://{socket.gethostname().removesuffix('.local')}.local:{port}"
        self.device = QTest.createTouchDevice()
        self.viewers = 0        # pages ouvertes
        self._dirty = True      # l'écran a changé depuis la dernière capture
        self._fresh = False     # une page vient de s'ouvrir : sa première capture part même si rien n'a changé
        self._grab_ms = 0.0     # durée d'une capture, moyennée
        self._frame = None      # (numéro, image) : la dernière capture
        self._jpeg = (-1, b"")  # la dernière capture, encodée
        self._lock = threading.Condition()

        self.received.connect(self._replay)
        window.frameSwapped.connect(self._changed)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._capture)
        self._timer.start(FRAME_MS)

        try:
            self._server = ThreadingHTTPServer(("", port), _handler(self))
        except OSError as error:
            raise SystemExit(f"Miroir impossible sur le port {port} : {error.strerror}") from error
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        QCoreApplication.instance().aboutToQuit.connect(self.close)

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    @Slot()
    def _changed(self) -> None:
        self._dirty = True

    def _capture(self) -> None:
        """Nouvelle capture, si une page regarde et que l'écran a changé. Plus elle coûte, plus la suivante attend."""
        if not self.viewers or not self._dirty:
            return
        self._dirty = False
        begin = time.perf_counter()
        image = self.window.grabWindow()
        self._grab_ms = 0.7 * self._grab_ms + 0.3 * (time.perf_counter() - begin) * 1000
        self._timer.setInterval(capture_interval(self._grab_ms))
        with self._lock:
            if self._frame is not None and image == self._frame[1] and not self._fresh:
                return
            self._fresh = False
            self._frame = (self._frame[0] + 1 if self._frame else 0, image)
            self._lock.notify_all()

    @Slot(object)
    def _replay(self, events: list) -> None:
        for event in events:
            if event[0] == "key":
                QTest.keyClick(self.window, KEYS[event[1]])
            else:
                touch = QTest.touchEvent(self.window, self.device, False)
                getattr(touch, TOUCH[event[0]])(0, QPoint(event[1], event[2]), self.window)
                touch.commit(False)

    def next_jpeg(self, after: int) -> tuple[int, bytes]:
        """La capture qui suit le numéro `after`, en JPEG ; au bout de RESEND_S sans nouveauté, la dernière."""
        with self._lock:
            self._lock.wait_for(lambda: self._frame is not None and self._frame[0] > after, RESEND_S)
            if self._frame is None:
                return after, b""
            number, image = self._frame
            cached = self._jpeg
        if cached[0] != number:
            cached = (number, encode(image))
            with self._lock:
                self._jpeg = cached
        return cached

    def watch(self, handler: BaseHTTPRequestHandler) -> None:
        """Flux d'images (MJPEG) vers une page, jusqu'à ce qu'elle se ferme. Chaque image est suivie de sa
        séparation, pour que le navigateur l'affiche sans attendre la suivante."""
        with self._lock:
            self.viewers += 1
            number = self._frame[0] if self._frame else -1  # attendre une capture fraîche, pas la dernière vue
            self._fresh = True
        self._dirty = True  # une capture tout de suite, même si l'écran ne bouge pas
        try:
            handler.wfile.write(b"--image\r\n")
            while True:
                number, jpeg = self.next_jpeg(number)
                if jpeg:
                    handler.wfile.write(b"Content-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n%s\r\n--image\r\n"
                                        % (len(jpeg), jpeg))
                    handler.wfile.flush()
        except OSError:  # page fermée
            pass
        finally:
            with self._lock:
                self.viewers -= 1


def _handler(mirror: Mirror) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):  # pas une ligne par requête dans le terminal
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                width, height = mirror.size
                page = PAGE.read_text(encoding="utf-8").replace("{{largeur}}", str(width))
                self._reply(200, "text/html; charset=utf-8", page.replace("{{hauteur}}", str(height)).encode())
            elif path == "/ecran":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=image")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                mirror.watch(self)
            elif path.startswith("/polices/") and (FONTS / Path(path).name).suffix == ".ttf" \
                    and (FONTS / Path(path).name).is_file():
                self._reply(200, "font/ttf", (FONTS / Path(path).name).read_bytes(), "max-age=86400")
            else:
                self._reply(404, "text/plain; charset=utf-8", "Introuvable".encode())

        def do_POST(self):
            if self.path != "/evenements":
                self._reply(404, "text/plain; charset=utf-8", "Introuvable".encode())
                return
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            events = parse_events(body.decode("utf-8", "replace"))
            if events:
                mirror.received.emit(events)
            self._reply(204, None, b"")

        def _reply(self, code: int, content_type: str | None, body: bytes, cache: str = "no-store") -> None:
            self.send_response(code)
            if content_type:
                self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(body)

    return Handler
