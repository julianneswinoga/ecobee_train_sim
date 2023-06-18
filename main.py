#!/usr/bin/env python3

import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication
import networkx as nx

from graphics_visualization import GraphWidget

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

    G = nx.lollipop_graph(5, 3)

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
