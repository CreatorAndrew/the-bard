from sys import path
from os.path import dirname, exists

path.insert(0, dirname(path[0]))
from pymysql import connect
from yaml import safe_load as load
from utils import VARIABLES

data = load(open(f"{VARIABLES['name']}.yaml", "r"))

connection = connect(
    host=(
        "localhost"
        if VARIABLES["database_credentials"]["host"] is None
        else VARIABLES["database_credentials"]["host"]
    ),
    port=(
        3306
        if VARIABLES["database_credentials"]["port"] is None
        else VARIABLES["database_credentials"]["port"]
    ),
    user=VARIABLES["database_credentials"]["user"],
    password=VARIABLES["database_credentials"]["password"],
    autocommit=True,
)
cursor = connection.cursor()
try:
    cursor.execute(f"create database `{VARIABLES['database_credentials']['database']}`")
except:
    pass
cursor.execute(f"use `{VARIABLES['database_credentials']['database']}`")
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
