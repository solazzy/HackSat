#!/usr/bin/env python3
import sys
from setuptools import setup
from os import path


requirements = [
    'colorama',
    "asciimatics",
    'LatLon',
]
if sys.version_info < (3, 7):
    requirements.append("dataclasses")

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="rbs_tui_dom",
    version="1.0.1",
    description="The RBS Terminal User Interface(TUI) framework",
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=[
        "rbs_tui_dom",
        "rbs_tui_dom.dom",
        "rbs_tui_dom.extra",
    ],
    ext_modules=[],
    install_requires=requirements,
    extras_require={
        "frontend": [

        ],
    }
)
