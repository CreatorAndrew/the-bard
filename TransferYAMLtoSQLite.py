import os
import sqlite3
import yaml

data = yaml.safe_load(open("Bard.yaml", "r"))

database = "Bard.db"
database_exists = os.path.exists(database)
connection = sqlite3.connect(database)
cursor = connection.cursor()
if not database_exists:
    cursor.execute("""create table guilds(guild_id integer not null,
                                          guild_lang text not null,
                                          working_thread_id integer null,
                                          keep_in_voice boolean not null,
                                          repeat_queue boolean not null,
                                          primary key (guild_id))""")
    cursor.execute("""create table playlists(pl_id integer not null,
                                             pl_name text not null,
                                             guild_id integer not null,
                                             guild_pl_id integer not null,
                                             primary key (pl_id),
                                             foreign key (guild_id) references guilds(guild_id))""")
    cursor.execute("""create table songs(song_id integer not null,
                                         song_name text not null,
                                         song_duration float not null,
                                         guild_id integer not null,
                                         channel_id integer not null,
                                         message_id integer not null,
                                         attachment_index integer not null,
                                         primary key (song_id))""")
    cursor.execute("""create table pl_songs(song_id integer not null,
                                            song_name text not null,
                                            song_url text null,
                                            pl_id integer not null,
                                            pl_song_id integer not null,
                                            primary key (song_id, pl_id),
                                            foreign key (song_id) references songs(song_id),
                                            foreign key (pl_id) references playlists(pl_id))""")
    cursor.execute("create table users(user_id integer not null, primary key (user_id))")
    cursor.execute("""create table guild_users(guild_id integer not null,
                                               user_id integer not null,
                                               primary key (guild_id, user_id),
                                               foreign key (guild_id) references guilds(guild_id),
                                               foreign key (user_id) references users(user_id))""")

for guild in data["guilds"]:
    try: working_thread_id = guild["working_thread_id"]
    except: working_thread_id = None
    cursor.execute("insert into guilds values(?, ?, ?, ?, ?)", (guild["id"], guild["language"], working_thread_id, guild["keep"], guild["repeat"]))
    for playlist in guild["playlists"]:
        cursor.execute("""insert into playlists values((select count(pl_id) from playlists),
                                                       ?,
                                                       ?,
                                                       (select count(pl_id) from playlists where guild_id = ?))""",
                       (playlist["name"], guild["id"], guild["id"]))
        for song in playlist["songs"]:
            cursor.execute("insert into songs values((select count(song_id) from songs), ?, ?, ?, ?, ?, ?)",
                           (song["name"], song["duration"], song["guild_id"], song["channel_id"], song["message_id"], song["attachment_index"]))
            cursor.execute("""insert into pl_songs values((select max(song_id) from songs),
                                                          ?,
                                                          ?,
                                                          (select pl_id from playlists where guild_id = ? and guild_pl_id = ?),
                                                          (select count(pl_songs.pl_id) from playlists
                                                           left outer join pl_songs on pl_songs.pl_id = playlists.pl_id
                                                           where guild_id = ? and guild_pl_id = ?))""",
                           (song["name"],
                            song["file"],
                            guild["id"],
                            guild["playlists"].index(playlist),
                            guild["id"],
                            guild["playlists"].index(playlist)))
    for user in guild["users"]:
        try: cursor.execute("insert into users values(?)", (user["id"],))
        except: pass
        cursor.execute("insert into guild_users values(?, ?)", (guild["id"], user["id"]))

connection.commit()
connection.close()
