from setuptools import setup

setup(
    name='beets-subsonic',
    version='0.1',
    description='beets plugin to sync with Subsonic servers',
    long_description=open('README.md').read(),
    author='Alok Saboo',
    author_email='',
    url='https://github.com/arsaboo/beets-subsonic',
    license='MIT',
    platforms='ALL',
    packages=['beetsplug'],
    install_requires=[
        'beets>=1.6.0',
        'requests',
    ],
)
