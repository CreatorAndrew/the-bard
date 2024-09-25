from sys import path
from os.path import dirname, exists

path.insert(0, dirname(path[0]))
from sqlite3 import connect
from yaml import safe_load as load
from utils import VARIABLES

data = load(open(f"{VARIABLES['name']}.yaml", "r"))

DATABASE = f"{VARIABLES['name']}.db"
connection = connect(DATABASE)
cursor = connection.cursor()
try:
    sql_file = f"{path[0]}/tables/music.sql"
    if exists(sql_file):
        for statement in open(sql_file, "r").read().split(";"):
            cursor.execute(statement)
except:
    pass

for guild in data["guilds"]:
    cursor.execute(
        "insert into guilds_music values(?, ?, ?, ?)",
        (
            guild["id"],
            guild.get("working_thread_id"),
            guild["keep"],
            guild["repeat"],
        ),
    )
    for playlist in guild["playlists"]:
        cursor.execute(
            """
            insert into playlists values(
                (select count(pl_id) from playlists),
                ?,
                ?,
                (select count(pl_id) from playlists where guild_id = ?)
            )
            """,
            (playlist["name"], guild["id"], guild["id"]),
        )
        for song in playlist["songs"]:
            try:
                cursor.execute(
                    "insert into songs values(?, ?, ?, ?, ?, ?, ?)",
                    (
                        song["id"],
                        song["name"],
                        song["duration"],
                        song["guild_id"],
                        song["channel_id"],
                        song["message_id"],
                        song["attachment_index"],
                    ),
                )
            except:
                pass
            cursor.execute(
                """
                insert into pl_songs values(
                    ?,
                    ?,
                    ?,
                    (select pl_id from playlists where guild_id = ? and guild_pl_id = ?),
                    (
                        select count(pl_songs.pl_id) from playlists
                        left outer join pl_songs on pl_songs.pl_id = playlists.pl_id
                        where guild_id = ? and guild_pl_id = ?)
                    )
                    """,
                (
                    song["id"],
                    song["name"],
                    song["file"],
                    guild["id"],
                    guild["playlists"].index(playlist),
                    guild["id"],
                    guild["playlists"].index(playlist),
                ),
            )

connection.commit()
connection.close()
