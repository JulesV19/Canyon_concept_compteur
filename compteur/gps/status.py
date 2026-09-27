"""État du GPS pour l'écran : réception, barres de la barre d'état."""

from dataclasses import dataclass

from .fix import Fix

ACCURACY_M_PER_HDOP = 3.0  # précision ≈ HDOP × 3 m : l'ordre de grandeur de la puce (3 m à ciel ouvert)

GOOD_HDOP = 2.0          # barres de la barre d'état : 4 au-dessous, 3 jusqu'à POOR_HDOP...
POOR_HDOP = 5.0          # ... et 2 au-delà (position trouvée, mais mauvaise géométrie)


@dataclass(frozen=True)
class Status:
    """État du GPS pour l'écran : le dernier Fix, et ce que le fil sait de la liaison."""

    fix: Fix
    present: bool = False              # le GPS envoie ses lignes
    age_s: float | None = None         # âge de la dernière ligne RMC
    first_fix_s: float | None = None   # première position, tant de secondes après le démarrage du fil
    errors: int = 0                    # échanges ratés sur le bus


def bars(status: Status) -> int:
    """Qualité de la réception, de 0 à 4 barres, pour la barre d'état : rien reçu, des satellites en vue sans
    position, puis la position et sa dispersion horizontale."""
    fix = status.fix
    if not status.present:
        return 0
    if not fix.valid:
        return 1 if fix.in_view else 0
    if fix.fix_type == 2 or fix.hdop is None or fix.hdop > POOR_HDOP:
        return 2
    return 4 if fix.hdop <= GOOD_HDOP else 3
