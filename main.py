#!/usr/bin/env python3

import argparse
import logging
import colorama
import sys
from pathlib import Path

from graphics_visualization import MainApp

log = logging.getLogger('main')

parser = argparse.ArgumentParser(
    description="""Simulate a network of trains/signals/forks, with a graphical interface"""
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
parser.add_argument(
    'file_to_load',
    metavar='FILE',
    type=Path,
    nargs='?',
    default=Path('default.json').resolve(),
    help='File to load on startup (default %(default)s)',
)


class ColouredFormatter(logging.Formatter):
    """
    Superclass of a logging formatter to colourize the logs according to logging level
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Override the default formatting of a log record to add colour, before
        passing it to the default formatter
        :param record: Log record to format
        :return: Colourized string of a log record
        """
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
    """
    Main script function
    """
    log.debug('Creating MainApp')
    main_app = MainApp('Train Simulation')
    main_app.main_window.load_file(args.file_to_load)

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
