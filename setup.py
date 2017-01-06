from setuptools import setup


setup(
    name='helloworld',
    install_requires=[
        'aiohttp',
        'raven',
        'setuptools_scm',
    ],
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
)
