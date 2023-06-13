#!/usr/bin/env python3

import argparse
import logging

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
    log.info('main()')


if __name__ == '__main__':
    args = parser.parse_args()
    logging.basicConfig(
        format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S%p',
        level=args.log_level,
    )
    log = logging.getLogger('pkgStats')
    main()
