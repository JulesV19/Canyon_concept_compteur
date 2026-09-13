from compteur.benchmark import format_line, phase_result


def releve(t, frames, updates, cpu, threads, temperature=None):
    return {"time": t, "frames": frames, "updates": updates, "cpu": cpu, "threads": threads,
            "memoryMb": 180.0, "temperatureC": temperature}


def test_bilan_d_une_phase():
    avant = releve(10.0, 100, 2, 3.0, {1: ("python3", 1.0), 2: ("QSGRenderThread", 2.0)})
    apres = releve(12.0, 220, 4, 5.4, {1: ("python3", 2.0), 2: ("QSGRenderThread", 3.0),
                                       3: ("QQuickPixmapRea", 0.2)}, temperature=51.5)
    bilan = phase_result("Carte", avant, apres, [9.0, 9.0, 4.0, 6.0], main_tid=1)
    assert bilan["fps"] == 60
    assert bilan["cpu"] == 120  # 2,4 s de processeur en 2 s : plus d'un cœur
    assert bilan["cpuInterface"] == 50
    assert bilan["cpuRender"] == 50
    assert (bilan["updateMsMean"], bilan["updateMsMax"]) == (5, 6)  # seules les mises à jour de la phase
    assert bilan["temperatureC"] == 51.5
    assert format_line(bilan).startswith("Carte")


def test_fil_de_rendu_du_processeur():
    """Dessin par le processeur sur un fil à part : son nom, tronqué par Linux, compte comme le rendu."""
    avant = releve(0.0, 0, 0, 0.0, {1: ("python3", 0.0), 2: ("QSGSoftwareRend", 0.0)})
    apres = releve(1.0, 30, 0, 0.9, {1: ("python3", 0.3), 2: ("QSGSoftwareRend", 0.6)})
    bilan = phase_result("Carte", avant, apres, [], main_tid=1)
    assert (bilan["cpuInterface"], bilan["cpuRender"]) == (30, 60)


def test_bilan_sans_detail_par_fil():
    """Sur le Mac, pas de temps par fil : seulement le total."""
    bilan = phase_result("Accueil", releve(0.0, 0, 0, 0.0, None), releve(1.0, 1, 0, 0.1, None), [], main_tid=1)
    assert bilan["cpuInterface"] is None and bilan["updateMsMean"] is None
    assert "—" in format_line(bilan)
