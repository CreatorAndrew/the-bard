#!/usr/bin/env python

from sys import path
from os.path import dirname

path.insert(0, dirname(path[0]))
from yaml import safe_load as load
from utils import LOAD_ORDER

VARIABLES_FILE = f"{path[0]}/variables.yaml"

try:
    lines = open(VARIABLES_FILE, "r").readlines()
except:
    lines = []

try:
    variables_data = load(open(VARIABLES_FILE, "r"))
    variables = variables_data if variables_data.items() else {}
except:
    variables = {}

for plugin in LOAD_ORDER:
    append_variables = True
    for key, value in load(open(f"variables/{plugin}.yaml", "r")).items():
        if key in map(lambda item: item[0], variables.items()):
            print(f'Variables for "{plugin}" were already added.')
            append_variables = False
            break
    if append_variables:
        lines += open(f"variables/{plugin}.yaml", "r").readlines()

open(VARIABLES_FILE, "w").writelines(lines)
