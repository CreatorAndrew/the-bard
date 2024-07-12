from sys import path
from os.path import dirname

path.insert(0, dirname(path[0]))
import subprocess
import psycopg
from yaml import safe_load as load
from utils import credentials, variables

data = load(open("Bard.yaml", "r"))

subprocess.run(
    [
        "psql",
        "-c",
        f"create database \"{variables['postgresql_credentials']['database']}\"",
        credentials,
    ],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.STDOUT,
)
CONNECTION = psycopg.connect(
    credentials.replace(
        f"dbname={variables['postgresql_credentials']['user']}",
        f"dbname={variables['postgresql_credentials']['database']}",
    ),
    autocommit=True,
)
cursor = CONNECTION.cursor()
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

CONNECTION.close()
