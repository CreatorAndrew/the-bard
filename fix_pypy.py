import platform

if platform.python_implementation() == "PyPy":
    from importlib.util import find_spec
    from os.path import dirname

    module_path = dirname(find_spec("pomice").origin)
    for file in ["pool", "applemusic/client", "spotify/client"]:
        contents = (
            open(f"{module_path}/{file}.py", "r").read().replace("orjson", "json")
        )
        open(f"{module_path}/{file}.py", "w").write(contents)
