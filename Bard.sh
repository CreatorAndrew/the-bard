#!/bin/bash
cd "${0%/*}"
source .venv/bin/activate
pypy3 Main.py
