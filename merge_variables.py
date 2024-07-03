from utils import load_order

lines = []

for plugin in load_order:
    lines += open(f"variables/{plugin}.yaml", "r").readlines()

open("variables.yaml", "w").writelines(lines)
