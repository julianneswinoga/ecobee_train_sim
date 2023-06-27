#!/usr/bin/env python3

import argparse
import logging
import sys

import networkx as nx

from graphics_visualization import MainApp
from simulation_model import Train, Track, Junction, Simulation

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
    # Create the graph representation
    log.debug('Creating graph')
    graph = nx.Graph()
    junctions = [Junction() for _ in range(7)]
    graph.add_edge(
        junctions[0], junctions[1], object=Track(Train(dest_junction=junctions[6], facing_junction=junctions[1]))
    )
    graph.add_edge(junctions[1], junctions[2], object=Track())
    graph.add_edge(junctions[1], junctions[3], object=Track())
    graph.add_edge(junctions[3], junctions[5], object=Track())
    graph.add_edge(junctions[3], junctions[4], object=Track())
    graph.add_edge(
        junctions[4], junctions[6], object=Track(Train(dest_junction=junctions[5], facing_junction=junctions[4]))
    )
    graph.add_edge(junctions[2], junctions[4], object=Track())

    log.debug('Creating simulation')
    sim = Simulation(graph)

    log.debug('Creating MainApp')
    main_app = MainApp('Train Simulation', sim)
    log.debug('Running app')
    sys.exit(main_app.run())


if __name__ == '__main__':
    args = parser.parse_args()
    logging.basicConfig(
        format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S%p',
        level=args.log_level,
    )
    log = logging.getLogger('main')
    main()
