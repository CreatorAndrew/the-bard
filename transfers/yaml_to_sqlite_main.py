from sys import path
from os.path import dirname, exists

path.insert(0, dirname(path[0]))
from sqlite3 import connect
from yaml import safe_load as load
from utils import VARIABLES

data = load(open(f"{VARIABLES["name"]}.yaml", "r"))

DATABASE = f"{VARIABLES["name"]}.db"
connection = connect(DATABASE)
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
