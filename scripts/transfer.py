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
    "mysql_to_postgresql",
    "mysql_to_sqlite",
    "mysql_to_yaml",
    "postgresql_to_mysql",
    "postgresql_to_sqlite",
    "postgresql_to_yaml",
    "sqlite_to_mysql",
    "sqlite_to_postgresql",
    "sqlite_to_yaml",
    "yaml_to_mysql",
    "yaml_to_postgresql",
    "yaml_to_sqlite",
]

print(
    "\n".join(
        [
            " 0. MySQL to PostgreSQL",
            " 1. MySQL to SQLite",
            " 2. MySQL to YAML",
            " 3. PostgreSQL to MySQL",
            " 4. PostgreSQL to SQLite",
            " 5. PostgreSQL to YAML",
            " 6. SQLite to MySQL",
            " 7. SQLite to PostgreSQL",
            " 8. SQLite to YAML",
            " 9. YAML to MySQL",
            "10. YAML to PostgreSQL",
            "11. YAML to SQLite",
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
