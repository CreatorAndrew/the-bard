from sys import path
from os.path import dirname, exists

path.insert(0, dirname(path[0]))
from sqlite3 import connect
from yaml import safe_load as load
from utils import VARIABLES

data = load(open(f"{VARIABLES['name']}.yaml", "r"))

connection = connect(f"{VARIABLES['name']}.db")
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
        "insert into guilds values(?, ?)",
        (
            guild["id"],
            guild["language"],
        ),
    )
    for user in guild["users"]:
        try:
            cursor.execute("insert into users values(?)", (user["id"],))
        except:
            pass
        cursor.execute(
            "insert into guild_users values(?, ?)", (guild["id"], user["id"])
        )

connection.commit()
connection.close()
