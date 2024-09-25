#!/usr/bin/env python

from sys import path
from os.path import dirname, exists
from os import remove

path.insert(0, dirname(path[0]))
from subprocess import DEVNULL, run, STDOUT
from utils import LOAD_ORDER, VARIABLES

YAML_PATH = f"{path[0]}/{VARIABLES['name']}.yaml"
YAML_PREEXISTENT = exists(YAML_PATH)

if YAML_PREEXISTENT:
    remove(YAML_PATH)

choices = [
    "postgresql_to_sqlite",
    "postgresql_to_yaml",
    "sqlite_to_postgresql",
    "sqlite_to_yaml",
    "yaml_to_postgresql",
    "yaml_to_sqlite",
]

print(
    "\n".join(
        [
            "0. PostgreSQL to SQLite",
            "1. PostgreSQL to YAML",
            "2. SQLite to PostgreSQL",
            "3. SQLite to YAML",
            "4. YAML to PostgreSQL",
            "5. YAML to SQLite",
            "",
            "Specify a transfer procedure by its option number: ",
        ]
    ),
    end="",
)

choice = choices[int(input())]

for plugin in LOAD_ORDER:
    run(
        ["python3", f"{path[0]}/transfers/{choice}_{plugin}.py"],
        stdout=DEVNULL,
        stderr=STDOUT,
    )

if not ("yaml" in choice or YAML_PREEXISTENT):
    remove(YAML_PATH)
