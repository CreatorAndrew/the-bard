from os.path import exists
import sqlite3
from yaml import safe_load as load

data = load(open("Bard.yaml", "r"))

DATABASE = "Bard.db"
DATABASE_EXISTS = exists(DATABASE)
connection = sqlite3.connect(DATABASE)
cursor = connection.cursor()
if not DATABASE_EXISTS:
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

for guild in data["guilds"]:
    WORKING_THREAD_ID = guild.get("working_thread_id")
    cursor.execute(
        "insert into guilds_music values(?, ?, ?, ?)",
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
                ?,
                ?,
                (select count(pl_id) from playlists where guild_id = ?)
            )
            """,
            (playlist["name"], guild["id"], guild["id"]),
        )
        for song in playlist["songs"]:
            cursor.execute(
                "insert into songs values((select count(song_id) from songs), ?, ?, ?, ?, ?, ?)",
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
