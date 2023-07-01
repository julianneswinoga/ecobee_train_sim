import logging
import copy
import itertools
from typing import Optional, Tuple, List, Dict, Set

import networkx as nx

log = logging.getLogger('simulation_model')

# Globally unique identifier (just easier to read an integer rather than hex)
_next_ident: int = 0


class SimObject:
    def __init__(self):
        global _next_ident
        self.ident = _next_ident
        _next_ident += 1

    def __repr__(self):
        return f'{self.__class__.__name__}({self.ident})'

    def __str__(self):
        return self.__repr__()


class Train(SimObject):
    def __init__(self, dest_junction: 'Junction', facing_junction: 'Junction'):
        super().__init__()
        self.dest_junction = dest_junction
        self.facing_junction = facing_junction


class TrainSignal(SimObject):
    def __init__(self, attached_junction: 'Junction'):
        super().__init__()
        self.attached_junction: Junction = attached_junction
        self.signal_state: bool = False


class Track(SimObject):
    def __init__(self, train: Optional[Train] = None, signals: Optional[List[TrainSignal]] = None):
        super().__init__()
        self.train: Optional[Train] = train
        self.train_signals: List[TrainSignal] = signals if signals else []
        self.trains_routed_along_track: Set[Train] = set()


class Junction(SimObject):
    def __init__(self):
        super().__init__()
        self.switch_state: Optional[Tuple[Junction, Junction]] = None
        self.connected_junctions: List[Junction] = []

    def get_switch_state(self) -> Tuple['Junction', 'Junction']:
        if self.switch_state is None:
            raise IndexError(f'{self}\'s switch state is not set yet')
        return self.switch_state

    def set_switch_state(self, junct1: 'Junction', junct2: 'Junction'):
        new_switch_state = (junct1, junct2)
        log.info(f'Switching {self} from {self.switch_state} to {new_switch_state}')
        if junct1 not in self.connected_junctions:
            raise IndexError(f'Can\'t set switch state: {junct1} not in {self.connected_junctions}')
        if junct2 not in self.connected_junctions:
            raise IndexError(f'Can\'t set switch state: {junct2} not in {self.connected_junctions}')
        self.switch_state = new_switch_state


class Simulation:
    def __init__(self, graph: nx.Graph):
        self.graph = graph
        self.step = 0

        self._initial_property_setup()

    def _initial_property_setup(self):
        # set initial switch states
        junctions = self.graph.nodes
        for junction in junctions:
            # Sort by lowest first, just for this switch state setup
            adj_junctions: List[Junction] = sorted(
                [k for k, v in self.graph.adj[junction].items()], key=lambda k: k.ident
            )
            junction.connected_junctions = adj_junctions
            if len(adj_junctions) == 0:
                raise EOFError(f'No adjacent junctions for {junction}??')
            elif len(adj_junctions) == 1:  # Terminator, switch points to two of the same junction
                switch_tup = (adj_junctions[0], adj_junctions[0])
            elif len(adj_junctions) == 2:  # Straight
                switch_tup = (adj_junctions[0], adj_junctions[1])
            else:  # Multiple paths, default to first two
                switch_tup = (adj_junctions[0], adj_junctions[1])
            junction.set_switch_state(*switch_tup)

        for train in self.get_all_trains():
            # Find routes for trains
            self.set_track_route_for_train(train)

    def get_junction_behind_train(self, train: Train):
        adj_junctions: Optional[Tuple[Junction, Junction]] = None
        for edge_tup in self.graph.edges:
            track: Track = self.graph.edges[edge_tup]['object']
            if train == track.train:
                adj_junctions = edge_tup
                break
        if not adj_junctions:
            raise IndexError(f'No rear junction to {train}?')

        if adj_junctions[0] == train.facing_junction:
            rear_junction = adj_junctions[1]
        else:
            rear_junction = adj_junctions[0]
        log.debug(f'Junction behind {train} is {rear_junction}')
        return rear_junction

    def get_sorted_junctions_for_route(self, train: Train) -> List[Junction]:
        junctions_on_route: Set[Junction] = set()
        for edge_tup in self.graph.edges:
            track: Track = self.graph.edges[edge_tup]['object']
            edge_has_route = train in track.trains_routed_along_track
            train_on_edge = train == track.train  # The current edge isn't included in the route
            if edge_has_route or train_on_edge:
                junctions_on_route.add(edge_tup[0])
                junctions_on_route.add(edge_tup[1])

        # Sort the junctions in order from the train to the destination
        # The first junction is the junction that isn't the trains currently facing direction
        # i.e. the one behind the train
        next_junction = self.get_junction_behind_train(train)
        sorted_junctions_on_route = []
        while len(junctions_on_route) != 0:
            sorted_junctions_on_route.append(next_junction)
            log.debug(f'Next junction in route is {next_junction}')
            junctions_on_route.remove(next_junction)
            # Find the next junction that is connected to what we just added
            for junction in junctions_on_route:
                if junction in self.graph.adj[next_junction]:
                    next_junction = junction
                    break
        return sorted_junctions_on_route

    def get_tracks_for_junction_path(self, junction_path: List[Junction]) -> List[Track]:
        # Create a copy so we don't modify the callers list
        junction_path_copy = copy.copy(junction_path)
        path_edge_tuples: List[Tuple[Junction, Junction]] = [(junction_path_copy.pop(0), junction_path_copy.pop(0))]
        while True:
            try:
                next_junction = junction_path_copy.pop(0)
            except IndexError:
                break  # No more junctions in the path
            next_edge = (path_edge_tuples[-1][1], next_junction)
            path_edge_tuples.append(next_edge)
        path_tracks: List[Track] = [self.graph.edges[path_edge]['object'] for path_edge in path_edge_tuples]
        return path_tracks

    def set_switches_for_train_route(self, train: Train, exclude_junctions: List[Junction]) -> List[Junction]:
        log.info(f'Setting switches for {train}, exclude={exclude_junctions}')
        junctions_on_route = self.get_sorted_junctions_for_route(train)
        log.debug(f'{train} route has sorted junctions {junctions_on_route}')

        # Go through the Junctions on the trains route,
        # if that junction's switch can be changed (more than 2 adjacent junctions)
        # set that junction's switch to the previous and next junction in the route
        junction_switches_set: List[Junction] = []
        for junction_idx in range(1, len(junctions_on_route) - 1):
            prev_junction = junctions_on_route[junction_idx - 1]
            cur_junction = junctions_on_route[junction_idx]
            next_junction = junctions_on_route[junction_idx + 1]
            if len(cur_junction.connected_junctions) < 3:
                continue  # Junction can't be switched
            if cur_junction in exclude_junctions:
                continue  # Junction is excluded
            cur_junction.set_switch_state(prev_junction, next_junction)
            junction_switches_set.append(cur_junction)
        log.info(f'{train} set switches on: {junction_switches_set}')
        return junction_switches_set

    def set_signals_for_train_route(self, train: Train, exclude_signals: List[TrainSignal]) -> List[TrainSignal]:
        log.info(f'Setting signals for {train}, exclude={exclude_signals}')
        junctions_on_route = self.get_sorted_junctions_for_route(train)
        tracks_on_route = self.get_tracks_for_junction_path(junctions_on_route)
        log.debug(f'{train} route has sorted tracks {tracks_on_route}')

        train_signals_set: Set[TrainSignal] = set()
        # Flip all signals attached to junctions on the route to red to begin with
        # Exclude the junction that is behind the train
        junction_behind_train = self.get_junction_behind_train(train)
        for track in self.get_all_tracks():
            for train_signal in track.train_signals:
                signal_on_route = train_signal.attached_junction in junctions_on_route
                signal_not_excluded = train_signal not in exclude_signals
                signal_not_behind_train = train_signal.attached_junction != junction_behind_train
                if signal_on_route and signal_not_excluded and signal_not_behind_train:
                    train_signal.signal_state = False
                    train_signals_set.add(train_signal)
        # Now go through all the tracks and set their signals to green
        for track_on_route in tracks_on_route:
            for train_signal in track_on_route.train_signals:
                signal_on_route = train_signal.attached_junction in junctions_on_route
                signal_not_excluded = train_signal not in exclude_signals
                signal_not_behind_train = train_signal.attached_junction != junction_behind_train
                if signal_on_route and signal_not_excluded and signal_not_behind_train:
                    train_signal.signal_state = True
                    train_signals_set.add(train_signal)
        log.info(f'{train} set signals: {train_signals_set}')
        return list(train_signals_set)

    def set_track_route_for_train(self, train: Train):
        log.debug(f'Setting route from {train.facing_junction} to {train.dest_junction}')
        if train.facing_junction == train.dest_junction:
            log.info(f'{train} at destination, no routing to be done')
            return
        # Clear the tracks with this train
        for track in self.get_all_tracks():
            if train in track.trains_routed_along_track:
                track.trains_routed_along_track.clear()

        # List of all paths. Prioritize the shortest paths, then just use all simple paths
        train_paths: itertools.chain[List[Junction]] = itertools.chain(
            nx.all_shortest_paths(self.graph, source=train.facing_junction, target=train.dest_junction),
            nx.all_simple_paths(self.graph, source=train.facing_junction, target=train.dest_junction),
        )
        train_path: Optional[List[Junction]] = None
        junction_behind_train = self.get_junction_behind_train(train)
        for potential_train_path in train_paths:
            # Select the first path where the second Junction isn't the Junction behind the trains position
            # else we would need the train to flip around!
            if potential_train_path[1] != junction_behind_train:
                train_path = potential_train_path
                break
        if not train_path:
            log.error(f'Could not find path for {train}!')
            return
        log.info(f'{train}\'s junction path is {train_path}')

        # Find the tracks that lie along the shortest path
        path_tracks = self.get_tracks_for_junction_path(train_path)
        log.info(f'{train}\'s track path is {path_tracks}')

        # Tell the tracks about the route
        for path_track in path_tracks:
            path_track.trains_routed_along_track.add(train)

    def get_all_tracks(self) -> List[Track]:
        all_tracks: List[Track] = []
        for edge_tup in self.graph.edges:
            track: Track = self.graph.edges[edge_tup]['object']
            all_tracks.append(track)
        return all_tracks

    def get_all_trains(self) -> List[Train]:
        all_trains: List[Train] = []
        for edge_tup in self.graph.edges:
            track: Track = self.graph.edges[edge_tup]['object']
            if track.train:
                all_trains.append(track.train)
        return all_trains

    def advance(self) -> bool:
        log.debug(f'Advancing simulation. step={self.step}')

        # Simple routing strategy:
        # - Deterministically sort all the trains that aren't at their destination
        # - Route the first non-terminated train, and keep track of the switches it set
        # - Route the next train, but don't allow it to flip the switches that have already been set
        unfinished_trains_sorted = sorted(
            (t for t in self.get_all_trains() if t.facing_junction != t.dest_junction),
            key=lambda t: t.ident,
        )
        more_updates_required = len(unfinished_trains_sorted) != 0
        if more_updates_required:
            # Update trains
            for train in self.get_all_trains():
                self.update_train(train)
            switches_already_set: List[Junction] = []
            signals_already_set: List[TrainSignal] = []
            for unfinished_train_sorted in unfinished_trains_sorted:
                switches_already_set += self.set_switches_for_train_route(
                    unfinished_train_sorted, exclude_junctions=switches_already_set
                )
                signals_already_set += self.set_signals_for_train_route(
                    unfinished_train_sorted, exclude_signals=signals_already_set
                )
        else:
            log.info('All trains at destination!')
        self.step += 1
        return more_updates_required

    def get_edge_tup_for_train(self, train: Train) -> Tuple[Junction, Junction]:
        train_edge: Optional[Tuple[Junction, Junction]] = None
        for edge_tup in self.graph.edges:
            track: Track = self.graph.edges[edge_tup]['object']
            if track.train == train:
                train_edge = edge_tup
                break
        if not train_edge:
            raise IndexError(f'Couldn\'t find edge for {train}!')
        return train_edge

    @staticmethod
    def get_signal(track: Track, junction: Junction) -> Optional[TrainSignal]:
        for train_signal in track.train_signals:
            if train_signal.attached_junction == junction:
                return train_signal
        return None

    def update_train(self, train: Train):
        current_edge = self.get_edge_tup_for_train(train)
        next_junct1, next_junct2 = train.facing_junction.get_switch_state()
        if next_junct1 == next_junct2:  # Terminator
            log.info(f'{train} at terminator')
        else:
            # Figure out which junction we currently are at, and which one is the next
            if next_junct1 in current_edge:
                next_junct = next_junct2
            elif next_junct2 in current_edge:
                next_junct = next_junct1
            else:
                log.info(f'{train}\'s next junction not switched towards it')
                log.debug(f'({current_edge}, {next_junct1}, {next_junct2})')
                next_junct = None

            # Check if the current facing junction's signal is switched green
            current_track: Track = self.graph.edges[current_edge]['object']
            train_signal = self.get_signal(current_track, train.facing_junction)
            if train_signal and not train_signal.signal_state:
                log.info(f'{train}\'s facing signal not switched green')
                signal_ok = False
            else:
                signal_ok = True

            if next_junct and signal_ok:
                # Move the train
                self.move_train(current_track, next_junct)
        # Set the routes for the train
        self.set_track_route_for_train(train)

    def move_train(self, old_track: Track, new_facing_junction: Junction):
        train = old_track.train
        if train is None:
            raise TypeError(f'{old_track} does not have a train! Cannot move it facing {new_facing_junction}')
        new_track: Track = self.graph.edges[(train.facing_junction, new_facing_junction)]['object']
        log.debug(f'{train} moving from {old_track} to {new_track}, facing {new_facing_junction}')
        if new_track.train is not None:
            log.error(f'Tried to move {train} into already occupied {new_track}')
            return
        # Do the swap
        train.facing_junction = new_facing_junction
        new_track.train = train
        old_track.train = None
