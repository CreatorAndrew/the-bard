from sys import path
from os.path import dirname, exists

path.insert(0, dirname(path[0]))
from pymysql import connect
from yaml import safe_dump as dump, safe_load as load
from utils import VARIABLES

FLAT_FILE = f"{VARIABLES['name']}.yaml"
if not exists(FLAT_FILE):
    dump({"guilds": []}, open(FLAT_FILE, "w"), indent=4)
data = load(open(FLAT_FILE, "r"))

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
    database=VARIABLES["database_credentials"]["database"],
)
cursor = connection.cursor()

cursor.execute("select * from guilds")
for guild in cursor.fetchall():
    users = []
    cursor.execute("select user_id from guild_users where guild_id = %s", (guild[0],))
    for user in cursor.fetchall():
        users.append({"id": user[0]})
    data["guilds"].append(
        {
            "id": guild[0],
            "language": guild[1],
            "users": users,
        }
    )

connection.close()

dump(data, open(FLAT_FILE, "w"), indent=4)
