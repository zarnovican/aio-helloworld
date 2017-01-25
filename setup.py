from setuptools import setup


setup(
    name='helloworld',
    install_requires=[
        'aiohttp',
        'em_tools',
        'prometheus_async',
        'prometheus_client',
        'setuptools_scm',
    ],
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
)
