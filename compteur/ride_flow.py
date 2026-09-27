"""Déroulé d'une sortie : départ, fin, enregistrement ou suppression, et reprise après une coupure.

`RideFlow` est une partie de `Compteur` (app.py) : ses méthodes s'appuient sur l'appli entière (modèle, écriture,
historique, fichier de reprise)."""

import sys
import time
from collections.abc import Callable
from datetime import datetime

from . import gps, history, journal
from .journal import Header
from .ride import Ride, State
from .route import Route
from .sim import SimulatedRider, demo_segments
from .storage import describe
from .summary import ride_summary

FREE_RIDE_NAME = "Sortie libre"
# Sortie reprise : la coupure compte comme une pause, de 12 h au plus (au-delà, l'horloge du système est douteuse)
MAX_RESUME_GAP_S = 12 * 3600


class RideFlow:
    def follow_segments(self, route: Route) -> None:
        """Segments suivis pendant la sortie : les favoris Strava, et la côte d'essai tant que le cycliste est simulé."""
        starred = self.strava.starred()
        self.model.segments = starred + demo_segments(route, starred)
        self.model.kom_label = self.strava.kom_label

    def start_ride(self, route: Route | None) -> None:
        """Départ sur ce parcours, ou en sortie libre (faute de vrai GPS, le cycliste simulé roule alors sur le
        premier)."""
        self.rider = self.make_rider(route)
        ride = self.new_ride()
        self.started_at = datetime.now().astimezone()
        self.route_name = route.name if route else FREE_RIDE_NAME
        if self.journal is not None:
            route_file = route.path.name if route is not None and route.path is not None else None
            self.journal.start(Header(self.started_at, route_file, self.route_name, ride.auto_pause, ride.max_hr), ride)
        self.follow_segments(route or self.routes[0])
        self.model.reset(ride, route)
        self.model.update(self.rider.sample(self.t, riding=False))  # des valeurs tout de suite, sans « -- »
        self.model.startPause()

    def finish_ride(self) -> dict:
        """Fin de la sortie : elle est gardée jusqu'au choix Enregistrer ou Supprimer, et le compteur
        revient au repos, sans parcours. Renvoie son résumé."""
        ride = self.model.ride
        summary = ride_summary(ride, self.route_name, self.started_at)
        self.finished = (ride, summary, self.started_at)
        if self.journal is not None:
            self.journal.finish(ride)
        self.model.reset(self.new_ride(), None)
        self.model.update(self.rider.sample(self.t, riding=False))
        self.model.refresh()
        return summary

    def save_ride(self, done: Callable[[str | None], None]) -> None:
        """Enregistre la sortie terminée (fichier FIT et résumé, dans sorties/) sur le fil d'écriture : l'écran ne se
        fige pas, même pour une longue sortie. Une fois les deux fichiers forcés sur la carte, le fichier de reprise
        s'efface. Puis `done(None)`, ou `done(message)` si la carte refuse : la sortie reste alors là, pour réessayer
        ou la supprimer."""
        if self.finished is None:
            done(None)
            return
        ride, summary, started_at = self.finished
        folder, recovery = self.history.folder, self.journal

        def task():
            path = history.save(ride, summary, started_at, folder)
            if recovery is not None:
                try:
                    recovery.delete()
                except OSError as error:  # la sortie est à l'abri : au prochain démarrage, on la verra enregistrée
                    print(f"Fichier de reprise pas effacé : {error}", file=sys.stderr)
            return path, history.load(folder)

        def finished(result, error):
            if error is not None:
                print(f"Sortie non enregistrée : {error!r}", file=sys.stderr, flush=True)
                done(describe(error))
                return
            path, summaries = result
            self.finished = None
            print(f"Sortie enregistrée : {path}", flush=True)
            try:
                self.history.show(summaries)
            finally:
                done(None)  # la sortie est à l'abri : l'écran la quitte, même si Mes sorties n'a pas pu se relire

        self.writer.submit(task, finished)

    def discard_ride(self) -> None:
        """Supprime la sortie terminée : son fichier de reprise, et le fichier FIT qu'un enregistrement raté aurait laissé
        sans son résumé."""
        if self.finished is None:
            return
        started_at, folder = self.finished[2], self.history.folder
        self.finished = None
        self.writer.submit(lambda: history.remove_orphans(started_at, folder))
        if self.journal is not None:
            self.journal.discard()

    def recover(self) -> str:
        """Au démarrage, la sortie laissée dans le fichier de reprise : terminée, son résumé revient ; en cours, elle
        reprend en pause, là où elle en était. Renvoie l'écran où démarrer."""
        path = self.journal.path
        try:
            found = journal.load(path)
        except (OSError, ValueError) as error:
            # Rien de lisible à reprendre : le fichier est mis de côté, jamais effacé
            aside = path.with_name(f"reprise-illisible-{datetime.now():%Y-%m-%d_%H-%M-%S}.jsonl")
            print(f"Fichier de reprise illisible ({error}) : gardé sous {aside.name}", file=sys.stderr)
            try:
                path.replace(aside)
            except OSError:
                pass
            return "home"
        if found is None:
            return "home"
        header, ride = found.header, found.ride
        # Une sortie terminée peut avoir été enregistrée juste avant la coupure : reconnue à son contenu
        summary = ride_summary(ride, header.route_name, header.started_at) if found.finished else None
        if ride.state is State.IDLE or (summary is not None and history.find_saved(summary, self.history.folder)):
            self.journal.discard()  # rien de roulé, ou déjà enregistrée
            return "home"
        self.journal.resume(found)
        self.started_at, self.route_name = header.started_at, header.route_name
        # L'horloge des mesures repart d'où elle s'était arrêtée, plus le temps passé depuis : la sortie garde des
        # heures justes, et la coupure compte comme une pause, dans le temps total comme dans le fichier FIT
        gap = min(max(time.time() - found.written_at, 0.0), MAX_RESUME_GAP_S)
        self.t = self.boot_t = ride.last_t + round(gap)
        print(f"Sortie reprise : {header.route_name}, {ride.total.distance_m / 1000:.1f} km", flush=True)
        if summary is not None:
            self.finished = (ride, summary, header.started_at)
            self.session.show(summary)
            return "summary"
        route = next((r for r in self.routes if r.path is not None and r.path.name == header.route_file), None)
        self.follow_segments(route or self.routes[0])
        self.model.resume(ride, route)
        if ride.state is State.RUNNING:
            self.model.startPause()  # elle attend Start pour repartir
        self.rider = self._rider_after(ride, route)
        self.resumed_at = f"{datetime.fromtimestamp(found.written_at):%H:%M}"  # pour le bandeau « Sortie reprise »
        return "ride"

    def _rider_after(self, ride: Ride, route: Route | None) -> SimulatedRider | gps.GpsRider:
        """Les mesures après une reprise : le vrai GPS reprend de lui-même ; le cycliste simulé, lui, est replacé à
        la dernière position de la sortie reprise."""
        rider = self.make_rider(route)
        if not isinstance(rider, SimulatedRider):
            return rider
        last = ride.current
        if route is not None and self.model.position is not None:
            rider.distance_m = self.model.position.along_m
        elif last is not None and last.lat is not None and last.lon is not None:
            rider.route.rewind()
            rider.distance_m = rider.route.locate(last.lat, last.lon).along_m
            rider.route.rewind()
        return rider
