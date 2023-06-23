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

    def __hash__(self):
        return self.ident

    def __repr__(self):
        return f'{self.__class__.__name__}({self.ident})'

    def __str__(self):
        return self.__repr__()


class Train(SimObject):
    def __init__(self, length: int):
        super().__init__()
        self.length = length


class Signal(SimObject):
    def __init__(self):
        super().__init__()


class Junction(SimObject):
    def __init__(self):
        super().__init__()
        self.fork_connections: Optional[Tuple[int, int]] = None

    def set_forks(self, fork1: int, fork2: int):
        self.fork_connections = (fork1, fork2)


class Simulation:
    def __init__(self, graph: nx.Graph):
        self.graph = graph

        self._initial_property_setup()

    def _initial_property_setup(self):
        # Figure out what properties each junction has
        for base_junction in self.graph.nodes:
            adj_junctions: Dict[Junction, Dict] = self.graph.adj[base_junction]
            log.debug(f'Junction {base_junction.ident} connected to {adj_junctions}')
            if len(adj_junctions) == 0:
                log.warning(f'Junction {base_junction.ident} is not connected to anything!')
            if len(adj_junctions) == 1:
                pass  # terminator
            elif len(adj_junctions) == 2:
                pass  # passthrough
            else:
                pass  # fork
                # Default to the 2 lowest junction identifiers
                adj_junction_idents = sorted([j.ident for j in adj_junctions])
                fork1, fork2 = adj_junction_idents[0], adj_junction_idents[1]
                log.debug(f'Setting fork @ {base_junction}: {fork1}, {fork2}')
                base_junction.set_forks(fork1, fork2)
