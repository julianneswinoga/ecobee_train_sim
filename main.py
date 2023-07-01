#!/usr/bin/env python3

import argparse
import logging
import colorama
import sys

import networkx as nx

from graphics_visualization import MainApp
from simulation_model import Train, TrainSignal, Track, Junction, Simulation

log = logging.getLogger('main')

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


class ColouredFormatter(logging.Formatter):
    def format(self, record):
        level_to_colour_code = {
            logging.DEBUG: colorama.Style.DIM + colorama.Fore.BLUE,
            logging.INFO: colorama.Style.DIM + colorama.Fore.GREEN,
            logging.WARNING: colorama.Fore.YELLOW,
            logging.ERROR: colorama.Fore.RED,
            logging.CRITICAL: colorama.Style.BRIGHT + colorama.Fore.RED,
        }
        colour_code = level_to_colour_code.get(record.levelno)
        if not colour_code:
            raise IndexError(f'No colour defined for log level:{record.levelno}')
        record_str = super().format(record)
        coloured_record_str = colour_code + record_str + colorama.Style.RESET_ALL
        return coloured_record_str


def main():
    # Create the graph representation
    log.debug('Creating graph')
    graph = nx.Graph()
    junctions = [Junction() for _ in range(10)]
    graph.add_edge(
        junctions[8], junctions[0], object=Track(train=Train(dest_junction=junctions[6], facing_junction=junctions[0]))
    )
    graph.add_edge(junctions[0], junctions[1], object=Track(signals=[TrainSignal(junctions[1])]))
    graph.add_edge(junctions[1], junctions[9], object=Track(signals=[TrainSignal(junctions[1])]))
    graph.add_edge(junctions[9], junctions[2], object=Track())
    graph.add_edge(junctions[1], junctions[3], object=Track())
    graph.add_edge(junctions[3], junctions[7], object=Track())
    graph.add_edge(junctions[7], junctions[5], object=Track())
    graph.add_edge(junctions[3], junctions[4], object=Track())
    graph.add_edge(junctions[4], junctions[6], object=Track())
    graph.add_edge(
        junctions[2], junctions[4], object=Track(train=Train(dest_junction=junctions[5], facing_junction=junctions[2]))
    )

    log.debug('Creating simulation')
    sim = Simulation(graph)

    log.debug('Creating MainApp')
    main_app = MainApp('Train Simulation', sim)
    log.debug('Running app')
    sys.exit(main_app.run())


if __name__ == '__main__':
    args = parser.parse_args()

    # Set up coloured console handler
    ch = logging.StreamHandler()
    ch.setFormatter(
        ColouredFormatter(
            fmt='[%(asctime)s][%(name)s][%(levelname)s] %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S%p',
        )
    )
    # Configure log level and handler for all loggers
    for logger in logging.root.manager.loggerDict.values():
        if isinstance(logger, logging.PlaceHolder):
            print(f'Not configuring {logger}')
            continue  # Support debugging?
        logger.addHandler(ch)
        logger.setLevel(args.log_level)

    main()
