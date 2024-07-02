import subprocess
import psycopg
from yaml import safe_load as load
from utils import variables

credentials = f"""
    dbname={variables["postgresql_credentials"]["user"]}
    user={variables["postgresql_credentials"]["user"]}
    password={variables["postgresql_credentials"]["password"]}
    {"" if variables["postgresql_credentials"]["host"] is None else f"host={variables['postgresql_credentials']['host']}"}
    {"" if variables["postgresql_credentials"]["port"] is None else f"port={variables['postgresql_credentials']['port']}"}
"""

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
        create table guilds_music(
            guild_id bigint not null,
            working_thread_id bigint null,
            keep_in_voice boolean not null,
            repeat_queue boolean not null,
            primary key (guild_id),
            foreign key (guild_id) references guilds(guild_id) on delete cascade
        )
        """
    )
    cursor.execute(
        """
        create table playlists(
            pl_id bigint not null,
            pl_name text not null,
            guild_id bigint not null,
            guild_pl_id bigint not null,
            primary key (pl_id),
            foreign key (guild_id) references guilds_music(guild_id) on delete cascade
        )
        """
    )
    cursor.execute(
        """
        create table songs(
            song_id bigint not null,
            song_name text not null,
            song_duration float not null,
            guild_id bigint not null,
            channel_id bigint not null,
            message_id bigint not null,
            attachment_index bigint not null,
            primary key (song_id)
        )
        """
    )
    cursor.execute(
        """
        create table pl_songs(
            song_id bigint not null,
            song_name text not null,
            song_url text null,
            pl_id bigint not null,
            pl_song_id bigint not null,
            primary key (song_id, pl_id),
            foreign key (song_id) references songs(song_id),
            foreign key (pl_id) references playlists(pl_id) on delete cascade
        )
        """
    )
except:
    pass

for guild in data["guilds"]:
    try:
        WORKING_THREAD_ID = guild["working_thread_id"]
    except:
        WORKING_THREAD_ID = None
    cursor.execute(
        "insert into guilds values(%s, %s)",
        (
            guild["id"],
            guild["language"],
        ),
    )
    cursor.execute(
        "insert into guilds_music values(%s, %s, %s, %s)",
        (
            guild["id"],
            WORKING_THREAD_ID,
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
            cursor.execute(
                "insert into songs values((select count(song_id) from songs), %s, %s, %s, %s, %s, %s)",
                (
                    song["name"],
                    song["duration"],
                    song["guild_id"],
                    song["channel_id"],
                    song["message_id"],
                    song["attachment_index"],
                ),
            )
            cursor.execute(
                """
                insert into pl_songs values(
                    (select max(song_id) from songs),
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
                    song["name"],
                    song["file"],
                    guild["id"],
                    guild["playlists"].index(playlist),
                    guild["id"],
                    guild["playlists"].index(playlist),
                ),
            )

CONNECTION.close()
