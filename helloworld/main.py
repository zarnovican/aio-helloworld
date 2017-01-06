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
import time

import aiohttp
from aiohttp import web
from prometheus_client import CollectorRegistry, Counter, generate_latest, Summary
import prometheus_async.aio
from raven.handlers.logging import SentryHandler
from raven.conf import setup_logging as setup_sentry
from setuptools_scm import get_version

from . import SERVICE_NAME

registry = CollectorRegistry()
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request', ['url'], registry=registry)
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

    if args.verbosity < 2:
        logging.getLogger('aiohttp.access').setLevel(logging.WARNING)


async def prometheus_pusher(url, interval):
    try:
        pushgateway_uri = '{}/metrics/job/{}'.format(url.rstrip('/'), SERVICE_NAME)
        logging.info('Starting prometheus_pusher loop, url={}, interval={}s'.format(pushgateway_uri, interval))
        async with aiohttp.ClientSession() as session:
            while True:
                await asyncio.sleep(interval)
                data = generate_latest(registry)
                try:
                    async with session.put(pushgateway_uri, data=data) as resp:
                        if resp.status != 202:
                            logging.warning('Prometheus pushgateway response was {}'.format(resp.status))
                except aiohttp.errors.ClientError as e:
                    logging.warning('Prometheus push failed: {}'.format(str(e)))
    except asyncio.CancelledError:
        pass


async def log_stats(app):
    try:
        last_time = time.time()
        last_count = REQUEST_COUNT._value.get()
        while True:
            await asyncio.sleep(10)
            current_time = time.time()
            current_count = REQUEST_COUNT._value.get()
            rate = (current_count-last_count) / (current_time-last_time)
            logging.info('Request rate {:.2f} req/s'.format(rate))
            last_time = current_time
            last_count = current_count
    except asyncio.CancelledError:
        pass


async def start_background_tasks(app):
    if app['args'].prometheus:
        app['prometheus_pusher'] = app.loop.create_task(
            prometheus_pusher(url=app['args'].prometheus, interval=10))
    app['log_stats'] = app.loop.create_task(log_stats(app))


async def stop_background_tasks(app):
    if 'prometheus_pusher' in app:
        app['prometheus_pusher'].cancel()
        await app['prometheus_pusher']
    app['log_stats'].cancel()
    await app['log_stats']


@prometheus_async.aio.time(REQUEST_TIME.labels(url='index'))
async def index(request):
    REQUEST_COUNT.inc()
    return web.Response(text='Hello!')


@prometheus_async.aio.time(REQUEST_TIME.labels(url='info'))
async def get_info(request):
    REQUEST_COUNT.inc()
    peername = request.transport.get_extra_info('peername')
    clientip = 'unknown'
    if peername is not None:
        clientip, port = peername
    return web.Response(text='{} ({}) on {}: your IP {}'.format(
        SERVICE_NAME, request.app['service_version'], socket.gethostname(), clientip))


@prometheus_async.aio.time(REQUEST_TIME.labels(url='slow'))
async def get_slow(request):
    REQUEST_COUNT.inc()
    try:
        await asyncio.sleep(float(request.match_info['time_in_ms']) / 1000.0)
        return web.Response(text='Slow response.')
    except asyncio.CancelledError:
        # when the client closes settion prematurely
        return web.Response(text='Cancelled.')


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
    parser.add_argument('--prometheus', metavar='url',
        help='Prometheus pushgateway (eg. "http://localhost:9091/")')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
        help='increase output verbosity (-v for INFO, -vv for DEBUG)')
    args = parser.parse_args()

    setup_logging(args)

    loop = asyncio.get_event_loop()
    app = web.Application(loop=loop)
    app['service_version'] = get_version()
    app['args'] = args
    app.router.add_get('/', index)
    app.router.add_get('/info', get_info)
    app.router.add_get(r'/slow/{time_in_ms:\d+}', get_slow)

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(stop_background_tasks)

    web.run_app(app, host='0.0.0.0', port=args.port)
