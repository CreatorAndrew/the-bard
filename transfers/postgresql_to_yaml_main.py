from os.path import exists
import psycopg
from yaml import safe_dump as dump, safe_load as load
from utils import variables

credentials = f"""
    dbname={variables["postgresql_credentials"]["user"]}
    user={variables["postgresql_credentials"]["user"]}
    password={variables["postgresql_credentials"]["password"]}
    {"" if variables["postgresql_credentials"]["host"] is None else f"host={variables['postgresql_credentials']['host']}"}
    {"" if variables["postgresql_credentials"]["port"] is None else f"port={variables['postgresql_credentials']['port']}"}
"""

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
        users.append({"id": user[1]})
    data["guilds"].append(
        {
            "id": guild[0],
            "language": guild[1],
            "users": users,
        }
    )

CONNECTION.close()

dump(data, open(FLAT_FILE, "w"), indent=4)
