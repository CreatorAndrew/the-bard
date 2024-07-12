from sys import path
from os.path import dirname, exists

path.insert(0, dirname(path[0]))
import psycopg
from yaml import safe_dump as dump, safe_load as load
from utils import credentials, variables

FLAT_FILE = "Bard.yaml"
if not exists(FLAT_FILE):
    dump({"guilds": []}, open(FLAT_FILE, "w"), indent=4)
data = load(open(FLAT_FILE, "r"))

CONNECTION = psycopg.connect(
    credentials.replace(
        f"dbname={variables['postgresql_credentials']['user']}",
        f"dbname={variables['postgresql_credentials']['database']}",
    )
)
cursor = CONNECTION.cursor()

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

CONNECTION.close()

dump(data, open(FLAT_FILE, "w"), indent=4)
