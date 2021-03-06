"""
All configuration is done via environment variables

SERVICE_NAME                name of the service (default: "aio-helloworld")
TASK_SLOT                   numeric id of a container within service (default: 1)
LOG_TARGET                  where to send logs (console/syslog) (default: "console")
LOG_LEVEL                   logging verbosity (default: "info")
LOG_ACCESS_ENABLED          log http requests true/false (default: "false")
PORT                        server listening port (default: 80)
STARTUP_DELAY               delay before serving requests in seconds [float] (default: 0)
SELFDESTRUCT_DELAY          stop app after N seconds [float] (default: 0, disabled)
SERVICE1_URL                base url to another service used by /call endpoint
                            (example: "http://hostname:port/", default: "")
SERVICE2_URL                base url to another service used by /call endpoint
                            (example: "http://hostname:port/", default: "")
"""
import argparse
import asyncio
import logging
import logging.handlers
import os
import signal
import socket
import sys
import time

import aiohttp
from aiohttp import web
from prometheus_client import CollectorRegistry, Counter, Summary
import prometheus_async.aio

registry = CollectorRegistry()
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request', ['url'], registry=registry)
REQUEST_COUNT = Counter('request_total', 'Number of requests', registry=registry)


class Config:

    def __init__(self):
        self.SERVICE_NAME = os.environ.get('SERVICE_NAME', 'aio-helloworld')
        self.VERSION = os.environ.get('VERSION', 'devel')
        self.TASK_SLOT = int(os.environ.get('TASK_SLOT', '1'))
        self.LOG_TARGET = os.environ.get('LOG_TARGET', 'console')
        self.LOG_LEVEL = os.environ.get('LOG_LEVEL', 'info')
        self.LOG_ACCESS_ENABLED = os.environ.get('LOG_ACCESS_ENABLED', 'false')
        self.PORT = int(os.environ.get('PORT', '80'))
        self.STARTUP_DELAY = float(os.environ.get('STARTUP_DELAY', '0'))
        self.SELFDESTRUCT_DELAY = float(os.environ.get('SELFDESTRUCT_DELAY', '0'))
        self.SERVICE1_URL = os.environ.get('SERVICE1_URL', '')
        self.SERVICE2_URL = os.environ.get('SERVICE2_URL', '')


def setup_logging(conf):

    if conf.LOG_TARGET == 'syslog':
        if not os.path.exists('/dev/log'):
            print('Unable to find /dev/log. Is syslog present ?')
            raise IOError(2, 'No such file or directory', '/dev/log')
        handler = logging.handlers.SysLogHandler(address='/dev/log')
        formatter = logging.Formatter('{}: %(name)s %(message)s'.format(conf.SERVICE_NAME))
    else:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(handler)
    log_level = logging.getLevelName(conf.LOG_LEVEL.upper())
    logger.setLevel(log_level)

    if conf.LOG_ACCESS_ENABLED.lower() == 'false':
        logging.getLogger('aiohttp.access').setLevel(logging.WARNING)


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
    logging.debug('starting background tasks')

    selfdestruct_delay = app['config'].SELFDESTRUCT_DELAY
    if selfdestruct_delay > 0:
        app.loop.create_task(selfdestruct(selfdestruct_delay))

    startup_delay = app['config'].STARTUP_DELAY
    if startup_delay > 0:
        logging.info('Delaying startup for %.02f seconds', startup_delay)
        await asyncio.sleep(startup_delay)

    app['log_stats'] = app.loop.create_task(log_stats(app))
    app['http_client'] = aiohttp.ClientSession()

    logging.debug('startup finished')


async def stop_background_tasks(app):
    logging.debug('stopping background tasks')
    app['log_stats'].cancel()
    await app['log_stats']
    await app['http_client'].close()


@prometheus_async.aio.time(REQUEST_TIME.labels(url='index'))
async def index(request):
    REQUEST_COUNT.inc()
    return web.Response(text='Hello!\n')


@prometheus_async.aio.time(REQUEST_TIME.labels(url='ping'))
async def get_ping(request):
    REQUEST_COUNT.inc()
    return web.Response(text='pong')


@prometheus_async.aio.time(REQUEST_TIME.labels(url='info'))
async def get_info(request):
    REQUEST_COUNT.inc()
    peername = request.transport.get_extra_info('peername')
    clientip = 'unknown'
    if peername is not None:
        clientip, port = peername
    return web.Response(text='AIO Python {} ({}) on {}: your IP {}\n'.format(
        request.app['iam'], request.app['config'].VERSION, socket.gethostname(), clientip))


@prometheus_async.aio.time(REQUEST_TIME.labels(url='slow'))
async def get_slow(request):
    REQUEST_COUNT.inc()
    try:
        await asyncio.sleep(float(request.match_info['time_in_ms']) / 1000.0)
        return web.Response(text='Slow response.\n')
    except asyncio.CancelledError:
        # when the client closes session prematurely
        return web.Response(text='Cancelled.\n')


@prometheus_async.aio.time(REQUEST_TIME.labels(url='call'))
async def get_call(request):
    REQUEST_COUNT.inc()
    try:
        service = request.match_info['service']
        if service == 'service1':
            url = request.app['config'].SERVICE1_URL
        elif service == 'service2':
            url = request.app['config'].SERVICE2_URL
        else:
            logging.warning('Unknown service %s', service)
            raise aiohttp.web.HTTPNotFound()

        if not url:
            logging.error('URL for service %s not defined', service)
            raise aiohttp.web.HTTPNotFound()

        uri = request.match_info['uri']
        http_client = request.app['http_client']
        try:
            async with http_client.get(url.strip('/')+'/'+uri) as resp:
                if resp.status != 200:
                    return web.Response(text='status {}\n'.format(resp.status))
                upstream_resp = (await resp.text()).strip()
                return web.Response(text='{} via {}\n'.format(upstream_resp, request.app['iam']))
        except aiohttp.ClientError as e:
            logging.warning('Service call failed: %s', e)
            raise aiohttp.web.HTTPBadGateway()

        return web.Response(text='Eeeehm\n')
    except asyncio.CancelledError:
        # when the client closes session prematurely
        return web.Response(text='Cancelled.\n')


@prometheus_async.aio.time(REQUEST_TIME.labels(url='log_sample'))
async def log_sample(request):
    REQUEST_COUNT.inc()
    level = request.match_info['level']
    logging.debug('called /log/<foo> endpoint')
    if level == 'info':
        logging.info('sample Info message')
    elif level == 'warning':
        logging.warning('sample Warning message')
    elif level == 'error':
        logging.error('sample Error message\nfoo\n    bar\nfoo2\n    bar2')
    elif level == 'exception':
        try:
            1/0
        except ZeroDivisionError:
            logging.exception('Exception caugth during request handling')
    else:
        logging.error('unrecognized log level: {}'.format(level))
        return web.Response(text='not found\n')
    return web.Response(text='ok\n')


@prometheus_async.aio.time(REQUEST_TIME.labels(url='exception'))
async def exception(request):
    REQUEST_COUNT.inc()
    1/0


async def terminate(request):
    logging.info('Sending myself SIGTERM')
    os.kill(os.getpid(), signal.SIGTERM)
    return web.Response(text='ok\n')


async def selfdestruct(delay):
    logging.info('Scheduling self-destruct in %.02f seconds', delay)
    await asyncio.sleep(delay)
    logging.info('Sending myself SIGTERM')
    os.kill(os.getpid(), signal.SIGTERM)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _, args = parser.parse_known_args()

    if args == ['help', ]:
        parser.print_help()
        parser.exit()

    config = Config()

    setup_logging(config)

    logging.info('Starting %s (%s)', config.SERVICE_NAME, config.VERSION)
    logging.info('  PORT=%s', config.PORT)
    logging.info('  SELFDESTRUCT_DELAY=%f', config.SELFDESTRUCT_DELAY)
    logging.info('  SERVICE1_URL=%s', config.SERVICE1_URL)
    logging.info('  SERVICE2_URL=%s', config.SERVICE2_URL)
    logging.info('  STARTUP_DELAY=%f', config.STARTUP_DELAY)

    app = web.Application()
    app['config'] = config
    app['iam'] = '{}.{}'.format(config.SERVICE_NAME, config.TASK_SLOT)
    app.add_routes([
        web.get('/', index),
        web.get('/ping', get_ping),
        web.get('/info', get_info),
        web.get(r'/slow/{time_in_ms:\d+}', get_slow),
        web.get(r'/call/{service}/{uri:.*}', get_call),
        web.get(r'/log/{level}', log_sample),
        web.get(r'/exception', exception),
        web.get(r'/terminate', terminate),
    ])

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(stop_background_tasks)

    logging.info('starting http server on 0.0.0.0:%s', config.PORT)
    web.run_app(app, port=config.PORT, print=None)
    logging.info('clean shutdown')


if __name__ == '__main__':
    main()
