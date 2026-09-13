from compteur.route import Point, Route
from compteur.sim import GPS_FIX_S, SimulatedRider


def test_le_gps_cherche_puis_capte():
    rider = SimulatedRider(Route("Test", [Point(48.70, 2.0, 100), Point(48.71, 2.0, 110)]))
    at_start = rider.device_status(0)
    assert at_start["gpsBars"] == 0
    assert not at_start["gpsFix"]
    fixed = rider.device_status(GPS_FIX_S)
    assert fixed["gpsBars"] == 4
    assert fixed["gpsFix"]
