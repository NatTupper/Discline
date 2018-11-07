# -*- coding: utf-8 -*-

from setuptools import setup

with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

requirements = [
    "asyncio",
    "blessings",
    "pyyaml",
    "mistletoe==0.6.2",
    "discord.py==1.0.0a"
]

setup(
    name='dline',
    version='2.4.1',
    description='A feature-rich terminal discord client',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='Nat Osaka',
    author_email='natthetupper@gmail.com',
    url='https://github.com/NatTupper/dline',
    license='gpl-3.0',
    keywords=['discord', 'discord.py', 'chat client', 'ncurses'],
    packages=[
        'dline', 'dline.client', 'dline.commands',
        'dline.input', 'dline.ui', 'dline.utils'
    ],
    install_requires=requirements,
    dependency_links=['https://github.com/Rapptz/discord.py/archive/rewrite.zip#egg=discord.py-1.0.0a'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Communications :: Chat'
    ],
    entry_points={
        'console_scripts': ['dline=dline.__main__:main']
    },
    include_package_data=True,
    zip_safe=False
)
