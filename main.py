#!/usr/bin/env python3

import argparse
import logging
import sys
from typing import Dict

from PySide6.QtWidgets import QApplication
import networkx as nx

from graphics_visualization import GraphWidget
from simulation_model import Train, Signal, Junction, Simulation

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

    graph = nx.Graph()
    junctions = [Junction() for _ in range(6)]
    graph.add_edge(junctions[0], junctions[1])
    graph.add_edge(junctions[1], junctions[2])
    graph.add_edge(junctions[1], junctions[3])
    graph.add_edge(junctions[3], junctions[4])
    graph.add_edge(junctions[3], junctions[5])

    # Create the simulation
    sim = Simulation(graph)

    log.debug('Creating GraphWidget')
    widget = GraphWidget('Train Simulation', nx.to_dict_of_dicts(sim.graph))
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
