"""
Template for aio http service

Here is a long description.
Multi-lined, etc..
"""
import argparse
import asyncio
import logging
import os
import socket
import sys
import time

import aiohttp
from aiohttp import web
from prometheus_client import Counter, Summary
import prometheus_async.aio
from setuptools_scm import get_version

from em_tools import setup_config, setup_logging
from em_tools.metrics import registry
from em_tools.aiometrics import setup_metrics

config_vars = {
    'PORT':         dict(default=8080, type=int, help='listening port (default: %(default)s)'),
    'SERVICE1_URL': dict(help='url to service1'),
    'SERVICE2_URL': dict(help='url to service2'),
}

REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request', ['url'], registry=registry)
REQUEST_COUNT = Counter('request_total', 'Number of requests', registry=registry)


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
    app['log_stats'] = app.loop.create_task(log_stats(app))
    app['http_client'] = aiohttp.ClientSession()


async def stop_background_tasks(app):
    if app['metrics_pusher_task'] is not None:
        app['metrics_pusher_task'].cancel()
        await app['metrics_pusher_task']
    app['log_stats'].cancel()
    await app['log_stats']
    await app['http_client'].close()


@prometheus_async.aio.time(REQUEST_TIME.labels(url='index'))
async def index(request):
    REQUEST_COUNT.inc()
    return web.Response(text='Hello!\n')


@prometheus_async.aio.time(REQUEST_TIME.labels(url='info'))
async def get_info(request):
    REQUEST_COUNT.inc()
    peername = request.transport.get_extra_info('peername')
    clientip = 'unknown'
    if peername is not None:
        clientip, port = peername
    config = request.app['config']
    iam = config.SERVICE_NAME
    if config.DOCKER_TASK_SLOT:
        iam += '.{}'.format(config.DOCKER_TASK_SLOT)
    return web.Response(text='{} ({}) on {}: your IP {}\n'.format(
        iam, request.app['service_version'], socket.gethostname(), clientip))


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
                return web.Response(text=await resp.text())
        except aiohttp.errors.ClientError as e:
            logging.warning('Service call failed: %s', e)
            raise aiohttp.web.HTTPBadGateway()

        return web.Response(text='Eeeehm\n')
    except asyncio.CancelledError:
        # when the client closes session prematurely
        return web.Response(text='Cancelled.\n')


def main():
    parser = argparse.ArgumentParser(
                usage='helloworld [<option>..]', description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter,
             )
    setup_config(parser, config_vars, service_name='helloworld', version=get_version())
    config = parser.parse_args()
    setup_logging(config)

    if config.VERBOSITY < 3:
        logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

    loop = asyncio.get_event_loop()
    app = web.Application(loop=loop)
    app['metrics_pusher_task'] = setup_metrics(loop, config)
    app['service_version'] = get_version()
    app['config'] = config
    app.router.add_get('/', index)
    app.router.add_get('/info', get_info)
    app.router.add_get(r'/slow/{time_in_ms:\d+}', get_slow)
    app.router.add_get(r'/call/{service}/{uri:.*}', get_call)

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(stop_background_tasks)

    web.run_app(app, host='0.0.0.0', port=config.PORT)
