#!/bin/bash
cd "${0%/*}"
source .venv/bin/activate
python FixPyPy.py
python Main.py
