"""La trace de la sortie, allégée pour la carte."""

import math

from PySide6.QtCore import QPointF

# La trace part vers la carte par tronçons de 50 points (500 m) : un tronçon fini n'est plus jamais redessiné, et seuls
# ceux qui touchent l'écran sont tracés, en entier, à chaque image. Un tronçon fini perd aussi les points dont l'écart ne
# se voit pas (moins d'un pixel au zoom le plus fort) : environ 4 points sur 5 sur les routes de la région. C'est ce qui
# garde la carte légère quand une longue sortie libre repasse plusieurs fois au même endroit.
TRACK_CHUNK = 50
TRACK_TOLERANCE = 1.0  # en coordonnées carte, soit en pixels au zoom 16


def simplified(points: list[QPointF], tolerance: float) -> list[QPointF]:
    """Le tracé sans les points qui s'écartent de moins de `tolerance` du segment entre leurs voisins gardés
    (Douglas-Peucker). Le premier et le dernier restent, pour que les tronçons se raccordent ; un demi-tour aussi, même
    au bout d'une ligne droite."""
    if tolerance <= 0 or len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    spans = [(0, len(points) - 1)]
    while spans:
        first, last = spans.pop()
        ax, ay, bx, by = points[first].x(), points[first].y(), points[last].x(), points[last].y()
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        worst, index = tolerance, None
        for i in range(first + 1, last):
            px, py = points[i].x(), points[i].y()
            t = min(1.0, max(0.0, ((px - ax) * dx + (py - ay) * dy) / length2)) if length2 else 0.0
            distance = math.hypot(px - ax - t * dx, py - ay - t * dy)
            if distance > worst:
                worst, index = distance, i
        if index is not None:
            keep[index] = True
            spans += [(first, index), (index, last)]
    return [point for point, kept in zip(points, keep) if kept]
