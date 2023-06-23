import logging
from typing import Optional, Tuple, List, Dict

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


class Track(SimObject):
    def __init__(self, train: Optional[Train] = None):
        super().__init__()
        self.train: Optional[Train] = train


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
        if junct1 not in self.connected_junctions:
            raise IndexError(f'Can\'t set switch state: {junct1} not in {self.connected_junctions}')
        if junct2 not in self.connected_junctions:
            raise IndexError(f'Can\'t set switch state: {junct2} not in {self.connected_junctions}')
        self.switch_state = (junct1, junct2)


class Simulation:
    def __init__(self, graph: nx.Graph):
        self.graph = graph
        self.step = 0

        self._initial_property_setup()

    def _initial_property_setup(self):
        # set switch states
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

    def advance(self):
        log.debug(f'Advancing simulation. step={self.step}')

        # Move trains forward
        for edge_tup in self.graph.edges:
            track: Track = self.graph.edges[edge_tup]['object']
            if track.train:
                train: Train = track.train
                log.debug(f'Edge {edge_tup} has {train}')
                next_junct1, next_junct2 = train.facing_junction.get_switch_state()
                if next_junct1 == next_junct2:  # Terminator
                    log.info(f'{train} at terminator')
                else:
                    # Figure out which junction we currently are at, and which one is the next
                    if next_junct1 in edge_tup:
                        next_junct = next_junct2
                    elif next_junct2 in edge_tup:
                        next_junct = next_junct1
                    else:
                        log.info(f'{train}\'s next junction not switched towards it')
                        next_junct = None

                        if edge_tup[0] in train.facing_junction.connected_junctions:
                            prev_junction = edge_tup[0]
                        elif edge_tup[1] in train.facing_junction.connected_junctions:
                            prev_junction = edge_tup[1]
                        else:
                            raise IndexError(f'{train}\'s facing junction doesn\'t contain the edge {edge_tup}??')
                        # Just pick the second one for now
                        new_switch_state = (prev_junction, train.facing_junction.connected_junctions[1])
                        log.info(
                            f'Switching {train.facing_junction}'
                            f'from {train.facing_junction.get_switch_state()}'
                            f'to {new_switch_state}'
                        )
                        train.facing_junction.set_switch_state(*new_switch_state)
                    if next_junct:
                        next_track: Track = self.graph.edges[(train.facing_junction, next_junct)]['object']
                        # Move the train
                        log.debug(f'{train} moving from {track} to {next_track}, facing {next_junct}')
                        train.facing_junction = next_junct
                        next_track.train = track.train
                        track.train = None

        self.step += 1
