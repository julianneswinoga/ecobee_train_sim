#!/usr/bin/env python3

import argparse
import logging
import sys
from typing import Dict

from PySide6.QtWidgets import QApplication
import networkx as nx

from graphics_visualization import GraphWidget
from simulation_model import Train, Signal, Junction

parser = argparse.ArgumentParser(
    # TODO: program description
    description=""""""
)
parser.add_argument(
    '-l',
    '--log_level',
    metavar='LEVEL',
    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    type=str.upper,
    default='WARNING',
    help='Set the logging level, one of %(choices)s (default %(default)s)',
)


def main():
    log.debug('Creating QApplication')
    app = QApplication()

    G = nx.Graph()
    junctions = [Junction() for _ in range(6)]
    G.add_edge(junctions[0], junctions[1])
    G.add_edge(junctions[1], junctions[2])
    G.add_edge(junctions[1], junctions[3])
    G.add_edge(junctions[3], junctions[4])
    G.add_edge(junctions[3], junctions[5])

    # Figure out what properties each junction has
    for base_junction in junctions:
        adj_junctions: Dict[Junction, Dict] = G.adj[base_junction]
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

    log.debug('Creating GraphWidget')
    widget = GraphWidget(nx.to_dict_of_dicts(G))
    widget.show()

    log.debug('Executing QApplication')
    sys.exit(app.exec())


if __name__ == '__main__':
    args = parser.parse_args()
    logging.basicConfig(
        format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S%p',
        level=args.log_level,
    )
    log = logging.getLogger('main')
    main()
