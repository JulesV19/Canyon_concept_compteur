from compteur.mirror import FRAME_MS, capture_interval, parse_events


def test_captures_espacees_selon_leur_cout():
    """Capture bon marché (GPU) : 25 images par seconde. Chère (processeur) : au plus 30 % du temps."""
    assert capture_interval(3) == FRAME_MS
    assert capture_interval(36) == 120


def test_evenements_de_la_page():
    assert parse_events("down 120.4 300\nmove 130 310\nup 130 310\nkey Space") == [
        ("down", 120, 300), ("move", 130, 310), ("up", 130, 310), ("key", "Space")]


def test_evenements_mal_formes_ignores():
    """Seuls les touchers et les touches connues atteignent l'interface."""
    assert parse_events("down 1\nkey Q\nclick 3 4\n\nmove a b\nup 5 6 7") == []
