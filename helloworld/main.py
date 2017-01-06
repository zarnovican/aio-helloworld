"""
Template for aio http service

Here is a long description.
Multi-lined, etc..
"""
import argparse
import asyncio
import logging
import logging.handlers
import os
import socket
import sys

from aiohttp import web
from prometheus_client import CollectorRegistry, Counter, generate_latest, Summary
from prometheus_async.aio import time
from raven.handlers.logging import SentryHandler
from raven.conf import setup_logging as setup_sentry
from setuptools_scm import get_version

from . import SERVICE_NAME

registry = CollectorRegistry()
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request', registry=registry)
REQUEST_COUNT = Counter('request_total', 'Number of requests', registry=registry)


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


async def prometheus_pusher(app):
    try:
        while True:
            await asyncio.sleep(10)
            data = generate_latest(registry)
            logging.debug(data)
    except asyncio.CancelledError:
        pass


async def start_prometheus_pusher(app):
    app['prometheus_pusher'] = app.loop.create_task(prometheus_pusher(app))


async def stop_prometheus_pusher(app):
    app['prometheus_pusher'].cancel()
    await app['prometheus_pusher']


@time(REQUEST_TIME)
async def index(request):
    REQUEST_COUNT.inc()
    return web.Response(text='Hello!')


@time(REQUEST_TIME)
async def get_info(request):
    REQUEST_COUNT.inc()
    peername = request.transport.get_extra_info('peername')
    clientip = 'unknown'
    if peername is not None:
        clientip, port = peername
    return web.Response(text='{} ({}) on {}: your IP {}'.format(
        SERVICE_NAME, request.app['service_version'], socket.gethostname(), clientip))


def main():
    parser = argparse.ArgumentParser(
                prog=SERVICE_NAME, description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter,
             )
    parser.add_argument('-P', '--port', default=8080,
        help='port to listen on (default: %(default)s)')
    parser.add_argument('--log', default='auto', metavar='auto|console',
        help='"auto" will use journal if available. '\
            'Otherwise, we will use console (default: %(default)s)')
    parser.add_argument('--sentry', metavar='dsn',
        help='Sentry dsn (eg. "http://xxx:xxx@sentry.example.com/nnn")')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
        help='increase output verbosity (-v for INFO, -vv for DEBUG)')
    args = parser.parse_args()

    setup_logging(args)

    loop = asyncio.get_event_loop()
    app = web.Application(loop=loop)
    app['service_version'] = get_version()
    app.router.add_get('/', index)
    app.router.add_get('/info', get_info)

    app.on_startup.append(start_prometheus_pusher)
    app.on_cleanup.append(stop_prometheus_pusher)

    web.run_app(app, host='0.0.0.0', port=args.port)
