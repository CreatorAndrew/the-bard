from sys import path
from os.path import dirname

path.insert(0, dirname(path[0]))
from subprocess import DEVNULL, run, STDOUT
from psycopg import connect
from yaml import safe_load as load
from utils import CREDENTIALS, VARIABLES

data = load(open(f"{VARIABLES["name"]}.yaml", "r"))

run(
    [
        "psql",
        "-c",
        f"create database \"{VARIABLES['postgresql_credentials']['database']}\"",
        CREDENTIALS.replace(
            f"dbname={VARIABLES['postgresql_credentials']['database']}",
            f"dbname={VARIABLES['postgresql_credentials']['user']}",
        ),
    ],
    stdout=DEVNULL,
    stderr=STDOUT,
)
connection = connect(CREDENTIALS, autocommit=True)
cursor = connection.cursor()
try:
    cursor.execute(
        """
        create table guilds(
            guild_id bigint not null,
            guild_lang text not null,
            primary key (guild_id)
        )
        """
    )
    cursor.execute("create table users(user_id bigint not null, primary key (user_id))")
    cursor.execute(
        """
        create table guild_users(
            guild_id bigint not null,
            user_id bigint not null,
            primary key (guild_id, user_id),
            foreign key (guild_id) references guilds(guild_id) on delete cascade,
            foreign key (user_id) references users(user_id) on delete cascade
        )
        """
    )
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
