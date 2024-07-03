from yaml import safe_load as load

load_order = list(
    map(
        lambda line: line.replace("\r\n", "").replace("\n", ""),
        open("load_order.txt", "r").readlines(),
    )
)

try:
    lines = open("variables.yaml", "r").readlines()
except:
    lines = []

try:
    variables_data = load(open("variables.yaml", "r"))
    variables = variables_data if variables_data.items() else {}
except:
    variables = {}

for plugin in load_order:
    append_variables = True
    for key, value in load(open(f"variables/{plugin}.yaml", "r")).items():
        if key in list(map(lambda item: item[0], variables.items())):
            print(f'Variables for "{plugin}" were already added.')
            append_variables = False
            break
    if append_variables:
        lines += open(f"variables/{plugin}.yaml", "r").readlines()

open("variables.yaml", "w").writelines(lines)
