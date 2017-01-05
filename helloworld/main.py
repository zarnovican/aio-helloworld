"""
Template for aio http service

Here is a long description.
Multi-lined, etc..
"""
import argparse
import logging
import logging.handlers
import os
import sys

from raven.handlers.logging import SentryHandler
from raven.conf import setup_logging as setup_sentry

from . import SERVICE_NAME


def setup_logging(args):
    """Configure 'logging' handlers/formatters and log verbosity"""

    if os.path.exists('/dev/log') and args.log == 'auto':
        print('Logging is redirected to systemd journal. Tail with "journalctl -t {} -f"'.format(SERVICE_NAME))
        handler = logging.handlers.SysLogHandler(address='/dev/log')
        formatter = logging.Formatter('{}: %(name)s %(message)s'.format(SERVICE_NAME))
    else:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(handler)

    if args.sentry:
        handler = SentryHandler(args.sentry, level=logging.WARNING)
        setup_sentry(handler)

    if args.verbosity >= 2:
        logger.setLevel(logging.DEBUG)
    elif args.verbosity >= 1:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARN)


def main():
    parser = argparse.ArgumentParser(
                prog=SERVICE_NAME, description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter,
             )
    parser.add_argument('--log', default='auto', metavar='auto|console',
        help='"auto" will use journal if available. '\
            'Otherwise, we will use console (default: %(default)s)')
    parser.add_argument('--sentry', metavar='dsn',
        help='Sentry dsn (eg. "http://xxx:xxx@sentry.example.com/nnn")')
    parser.add_argument('-v', '--verbosity', action='count',
        help='increase output verbosity (-v for INFO, -vv for DEBUG)')
    args = parser.parse_args()

    setup_logging(args)
