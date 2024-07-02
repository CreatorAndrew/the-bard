import platform

if platform.python_implementation() == "PyPy":
    import requests
    from os.path import abspath, dirname

    module_path = f"{dirname(abspath(requests.__file__))}/../pomice"
    files = ["pool", "applemusic/client", "spotify/client"]
    for file in files:
        to_read = open(f"{module_path}/{file}.py", "r")
        contents = to_read.read().replace("orjson", "json")
        to_write = open(f"{module_path}/{file}.py", "w")
        to_write.write(contents)
