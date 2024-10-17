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
    sql_file = f"{path[0]}/tables/music.sql"
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
        "insert into guilds_music values(%s, %s, %s, %s)",
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
                %s,
                %s,
                (select count(pl_id) from playlists where guild_id = %s)
            )
            """,
            (playlist["name"], guild["id"], guild["id"]),
        )
        for song in playlist["songs"]:
            try:
                cursor.execute(
                    "insert into songs values(%s, %s, %s, %s, %s, %s, %s)",
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
                    %s,
                    %s,
                    %s,
                    (select pl_id from playlists where guild_id = %s and guild_pl_id = %s),
                    (
                        select count(pl_songs.pl_id) from playlists
                        left outer join pl_songs on pl_songs.pl_id = playlists.pl_id
                        where guild_id = %s and guild_pl_id = %s)
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

connection.close()
