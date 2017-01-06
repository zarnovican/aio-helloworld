from setuptools import setup


setup(
    name='helloworld',
    install_requires=[
        'aiohttp',
        'prometheus_async',
        'prometheus_client',
        'raven',
        'setuptools_scm',
    ],
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
)
