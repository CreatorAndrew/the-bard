#!/bin/bash
cd "${0%/*}"
source .venv/bin/activate
python fix_pypy.py
python main.py
