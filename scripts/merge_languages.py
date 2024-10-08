#!/usr/bin/env python

from sys import path
from os.path import dirname

path.insert(0, dirname(path[0]))
from os import listdir
from yaml import safe_dump as dump, safe_load as load
from utils import LANGUAGE_DIRECTORY, LOAD_ORDER

LANGUAGE_FRAGMENTS_DIRECTORY = f"{path[0]}/languages/fragments"

for language in map(
    lambda language: language[: language.index(f"_{LOAD_ORDER[0]}")],
    filter(
        lambda file: file.endswith(f"_{LOAD_ORDER[0]}.yaml"),
        listdir(LANGUAGE_FRAGMENTS_DIRECTORY),
    ),
):
    strings = []
    string_names = []
    new_data = {"strings": {}, "name": None}

    for plugin in LOAD_ORDER:
        data = load(
            open(f"{LANGUAGE_FRAGMENTS_DIRECTORY}/{language}_{plugin}.yaml", "r")
        )
        if new_data["name"] is None:
            new_data["name"] = data["name"]
        strings += data["strings"].items()

    for key, value in strings:
        new_data["strings"][key] = value

    for key, value in new_data["strings"].items():
        string_names.append(f"{key}\n")

    dump(new_data, open(f"{LANGUAGE_DIRECTORY}/{language}.yaml", "w"), indent=4)

    contents = [
        "# Do not modify the variable names. Only modify their values.\n",
        "# Also do not modify whatever is in %{}. Those are placeholders.\n",
        "\n",
    ] + open(f"{LANGUAGE_DIRECTORY}/{language}.yaml", "r").readlines()

    open(f"{LANGUAGE_DIRECTORY}/{language}.yaml", "w").writelines(contents)

    open("language_string_names.txt", "w").writelines(string_names)
