"""Le format NMEA : lignes du GPS (somme de contrôle, champs, coordonnées) et commandes PMTK."""


KNOT_MPS = 1852 / 3600

MAX_LINE = 120           # une ligne NMEA fait 82 caractères au plus : au-delà, c'est du bruit


def checksum(body: str) -> int:
    """Somme de contrôle NMEA : ou exclusif des caractères entre « $ » et « * »."""
    value = 0
    for char in body.encode("ascii"):
        value ^= char
    return value


def command(body: str) -> bytes:
    """Commande pour le GPS, avec sa somme de contrôle (ex. « PMTK314,… »)."""
    return f"${body}*{checksum(body):02X}\r\n".encode("ascii")


# Messages voulus : position (RMC) et altitude (GGA) chaque seconde ; satellites utilisés et précision (GSA), satellites
# en vue et leur signal (GSV), toutes les 5 s. Par défaut le GPS envoie aussi VTG, et GSA et GSV chaque seconde : trois
# fois plus d'octets sur le bus partagé.
OUTPUT = command("PMTK314,0,1,0,1,5,5,0,0,0,0,0,0,0,0,0,0,0,0,0")
UNWANTED = {"VTG", "GLL"}  # l'un d'eux arrive : le GPS a oublié le réglage (coupure), on le renvoie
QUERY_FIRMWARE = command("PMTK605")  # réponse : PMTK705, version du micrologiciel
# Constellation d'après l'émetteur des lignes GSV ; les satellites SBAS (EGNOS) arrivent avec ceux du GPS, en 33 à 64
SYSTEMS = {"GP": "GPS", "GL": "GLONASS", "GA": "Galileo", "GB": "BeiDou", "BD": "BeiDou", "GQ": "QZSS", "QZ": "QZSS"}


def parse(line: str) -> tuple[str, list[str]] | None:
    """(type, champs) d'une ligne NMEA valide, ex. ("RMC", ["123519.000", "A", …]) ; None si elle est abîmée."""
    line = line.strip()
    if not line.startswith("$") or len(line) < 7 or line[-3] != "*":
        return None
    body = line[1:-3]
    try:
        if int(line[-2:], 16) != checksum(body):
            return None
    except (ValueError, UnicodeEncodeError):
        return None
    address, *fields = body.split(",")
    if address.startswith("P"):
        return address, fields  # message propre au fabricant (PMTK…) : gardé en entier
    return address[2:], fields  # sans l'émetteur (GP, GL, GA, GN…)


def coordinate(value: str, hemisphere: str) -> float | None:
    """« 4851.2345 », « N » → 48,853908 (degrés décimaux ; négatif au sud et à l'ouest)."""
    if not value or "." not in value:
        return None
    try:
        dot = value.index(".")
        degrees = float(value[:dot - 2]) + float(value[dot - 2:]) / 60
    except ValueError:
        return None
    return -degrees if hemisphere in ("S", "W") else degrees


def number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def satellite_system(talker: str, prn: int) -> str:
    if talker == "GP" and 33 <= prn <= 64:
        return "SBAS"
    if talker == "GP" and 193 <= prn <= 202:
        return "QZSS"
    return SYSTEMS.get(talker, talker)
