from subprocess import DEVNULL, run, STDOUT
from utils import LOAD_ORDER

choices = [
    "postgresql_to_yaml",
    "sqlite_to_yaml",
    "yaml_to_postgresql",
    "yaml_to_sqlite",
]

print(
    "\n".join(
        [
            "0. PostgreSQL to YAML",
            "1. SQLite to YAML",
            "2. YAML to PostgreSQL",
            "3. YAML to SQLite",
            "",
            "Specify a transfer procedure by its option number: ",
        ]
    ),
    end="",
)

choice = choices[int(input())]

for plugin in LOAD_ORDER:
    run(
        ["python3", f"transfers/{choice}_{plugin}.py"],
        stdout=DEVNULL,
        stderr=STDOUT,
    )
