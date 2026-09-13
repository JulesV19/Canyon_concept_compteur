"""Parcours GPX : tracé, profil d'altitude, et position du cycliste le long du tracé."""

import bisect
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .ride import Climb

EARTH_RADIUS_M = 6_371_000.0
MAX_LAT = 85.0511  # limite de la carte (Web Mercator)
OFF_ROUTE_M = 40.0  # au-delà, le cycliste a quitté le parcours
# La position est d'abord cherchée juste après la précédente, et on évite de reculer sur le tracé :
# un parcours qui repasse au même endroit (aller-retour, boucle en huit) n'est pas confondu
# avec l'autre passage.
SEARCH_BEHIND = 5
SEARCH_AHEAD = 200
BACKTRACK_TOLERANCE_M = 20.0


@dataclass(frozen=True)
class Point:
    lat: float
    lon: float
    ele: float | None = None


@dataclass(frozen=True)
class Position:
    """Où en est le cycliste : distance faite le long du tracé, et écart au tracé."""

    along_m: float
    offset_m: float


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


class Route:
    def __init__(self, name: str, points: list[Point], path: Path | None = None):
        """ValueError si le parcours est inutilisable : moins de deux points, point hors de la carte, longueur nulle."""
        if len(points) < 2:
            raise ValueError("un parcours doit contenir au moins deux points")
        for p in points:
            if not (math.isfinite(p.lat) and math.isfinite(p.lon) and abs(p.lat) <= MAX_LAT and abs(p.lon) <= 180):
                raise ValueError(f"point hors de la carte : {p.lat}, {p.lon}")
        self.name = name
        self.path = path  # fichier GPX d'origine
        self.points = points
        # Projection plane locale en mètres, précise sur quelques dizaines de kilomètres
        self._kx = math.radians(1) * EARTH_RADIUS_M * math.cos(math.radians(points[0].lat))
        self._ky = math.radians(1) * EARTH_RADIUS_M
        self._xy = [self._project(p.lat, p.lon) for p in points]
        self.cumulative = [0.0]
        for (x1, y1), (x2, y2) in zip(self._xy, self._xy[1:]):
            self.cumulative.append(self.cumulative[-1] + math.hypot(x2 - x1, y2 - y1))
        self.length_m = self.cumulative[-1]
        if self.length_m <= 0:
            raise ValueError("parcours de longueur nulle : tous ses points sont au même endroit")
        # Dénivelé positif jusqu'à chaque point, avec le même filtre que le compteur
        climb = Climb()
        ascent = 0.0
        self._ascent_to = []
        for p in points:
            if p.ele is not None:
                ascent += climb.add(p.ele)[0]
            self._ascent_to.append(ascent)
        self.ascent_m = ascent
        self._segment = 0
        self._along = 0.0

    @classmethod
    def load(cls, path: str | Path) -> "Route":
        """Lit un fichier GPX (trace ou itinéraire, comme ceux de Komoot ou Strava). OSError si le fichier ne se lit
        pas, ValueError s'il est mal formé ou inutilisable comme parcours."""
        path = Path(path)
        tracks: list[Point] = []
        routes: list[Point] = []
        name = None
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as error:
            raise ValueError(f"GPX mal formé : {error}") from error
        for element in root.iter():
            tag = _local(element.tag)
            if tag in ("trkpt", "rtept"):
                text = next((child.text for child in element if _local(child.tag) == "ele"), None)
                try:
                    lat, lon = float(element.get("lat")), float(element.get("lon"))
                    ele = float(text) if text else None
                except (TypeError, ValueError) as error:
                    raise ValueError(f"point illisible : {error}") from error
                point = Point(lat, lon, ele if ele is not None and math.isfinite(ele) else None)
                (tracks if tag == "trkpt" else routes).append(point)
            elif tag == "name" and name is None and element.text and element.text.strip():
                name = element.text.strip()
        return cls(name or path.stem, tracks or routes, path)

    def _project(self, lat: float, lon: float) -> tuple[float, float]:
        return lon * self._kx, lat * self._ky

    def locate(self, lat: float, lon: float) -> Position:
        """Position du cycliste sur le tracé, en suivant sa progression."""
        x, y = self._project(lat, lon)
        last = len(self._xy) - 1
        near = self._nearest(x, y, max(0, self._segment - SEARCH_BEHIND),
                             min(last, self._segment + SEARCH_AHEAD), forward=True)
        if near[1] > OFF_ROUTE_M:
            anywhere = self._nearest(x, y, 0, last, forward=False)
            if anywhere[1] < near[1]:
                near = anywhere
        segment, offset, along = near
        if offset <= OFF_ROUTE_M:
            self._segment, self._along = segment, along
        return Position(along, offset)

    def _nearest(self, x: float, y: float, first: int, last: int,
                 forward: bool) -> tuple[int, float, float]:
        """Segment le plus proche parmi [first, last[ : (indice, écart, distance le long du tracé).
        `forward` : pénalise les positions qui font reculer sur le tracé."""
        best, best_score = (first, math.inf, 0.0), math.inf
        for i in range(first, last):
            (x1, y1), (x2, y2) = self._xy[i], self._xy[i + 1]
            dx, dy = x2 - x1, y2 - y1
            length2 = dx * dx + dy * dy
            t = 0.0 if length2 == 0 else min(1.0, max(0.0, ((x - x1) * dx + (y - y1) * dy) / length2))
            offset = math.hypot(x - x1 - t * dx, y - y1 - t * dy)
            along = self.cumulative[i] + t * math.sqrt(length2)
            score = offset
            if forward:
                score += max(0.0, self._along - along - BACKTRACK_TOLERANCE_M)
            if score < best_score:
                best, best_score = (i, offset, along), score
        return best

    def point_at(self, distance_m: float) -> Point:
        """Point du tracé à cette distance du départ."""
        d = min(max(distance_m, 0.0), self.length_m)
        i = min(bisect.bisect_right(self.cumulative, d) - 1, len(self.points) - 2)
        a, b = self.points[i], self.points[i + 1]
        span = self.cumulative[i + 1] - self.cumulative[i]
        t = (d - self.cumulative[i]) / span if span else 0.0
        ele = None if a.ele is None or b.ele is None else a.ele + t * (b.ele - a.ele)
        return Point(a.lat + t * (b.lat - a.lat), a.lon + t * (b.lon - a.lon), ele)

    def heading_at(self, distance_m: float, span_m: float = 15.0) -> float:
        """Cap du tracé en degrés (0 = nord), lissé sur quelques mètres."""
        a, b = self.point_at(distance_m - span_m), self.point_at(distance_m + span_m)
        (x1, y1), (x2, y2) = self._project(a.lat, a.lon), self._project(b.lat, b.lon)
        return math.degrees(math.atan2(x2 - x1, y2 - y1)) % 360

    def grade_at(self, distance_m: float, span_m: float = 20.0) -> float:
        """Pente du tracé en %."""
        start, end = max(distance_m - span_m, 0.0), min(distance_m + span_m, self.length_m)
        a, b = self.point_at(start).ele, self.point_at(end).ele
        if a is None or b is None or end <= start:
            return 0.0
        return (b - a) / (end - start) * 100

    def ascent_after(self, distance_m: float) -> float:
        """Dénivelé positif qui reste à grimper après cette distance."""
        i = max(bisect.bisect_right(self.cumulative, distance_m) - 1, 0)
        return self.ascent_m - self._ascent_to[i]

    def profile(self, points: int = 300) -> list[tuple[float, float]]:
        """Profil (distance, altitude) rééchantillonné à pas régulier, pour le graphique."""
        if any(p.ele is None for p in self.points):
            return []
        step = self.length_m / (points - 1)
        return [(i * step, self.point_at(i * step).ele) for i in range(points)]

    def outline(self, points: int = 160) -> list[tuple[float, float]]:
        """Tracé rééchantillonné à pas régulier et ramené entre 0 et 1 en gardant ses proportions,
        nord en haut (y vers le bas, comme à l'écran) : pour dessiner le parcours en petit."""
        step = self.length_m / (points - 1)
        xy = [self._project(p.lat, p.lon) for p in (self.point_at(i * step) for i in range(points))]
        left = min(x for x, _ in xy)
        top = max(y for _, y in xy)
        span = max(max(x for x, _ in xy) - left, top - min(y for _, y in xy)) or 1.0
        return [((x - left) / span, (top - y) / span) for x, y in xy]

    def rewind(self) -> None:
        """Nouvelle sortie : la position est de nouveau cherchée depuis le départ
        (sans quoi, sur une boucle, on serait déjà arrivé)."""
        self._segment = 0
        self._along = 0.0
