from setuptools import setup


setup(
    name='helloworld',
    install_requires=[
        'raven',
    ],
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
)
