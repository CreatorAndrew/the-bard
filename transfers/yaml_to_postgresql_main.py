from sys import path
from os.path import dirname, exists

path.insert(0, dirname(path[0]))
from subprocess import DEVNULL, run, STDOUT
from psycopg import connect
from yaml import safe_load as load
from utils import CREDENTIALS, VARIABLES

data = load(open(f"{VARIABLES['name']}.yaml", "r"))

run(
    [
        "psql",
        "-c",
        f"create database \"{VARIABLES['database_credentials']['database']}\"",
        CREDENTIALS.replace(
            f"dbname={VARIABLES['database_credentials']['database']}",
            f"dbname={VARIABLES['database_credentials']['user']}",
        ),
    ],
    stdout=DEVNULL,
    stderr=STDOUT,
)
connection = connect(CREDENTIALS, autocommit=True)
cursor = connection.cursor()
try:
    sql_file = f"{path[0]}/tables/main.sql"
    if exists(sql_file):
        for statement in filter(
            lambda statement: statement not in ["", "\n", "\r\n"],
            open(sql_file, "r").read().split(";"),
        ):
            cursor.execute(statement)
except:
    pass

for guild in data["guilds"]:
    cursor.execute(
        "insert into guilds values(%s, %s)",
        (
            guild["id"],
            guild["language"],
        ),
    )
    for user in guild["users"]:
        try:
            cursor.execute("insert into users values(%s)", (user["id"],))
        except:
            pass
        cursor.execute(
            "insert into guild_users values(%s, %s)", (guild["id"], user["id"])
        )

connection.close()
