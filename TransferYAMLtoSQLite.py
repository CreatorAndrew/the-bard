import os
import sqlite3
import yaml

data = yaml.safe_load(open("Guilds.yaml", "r"))

database = "Guilds.db"
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
                                         song_url text not null,
                                         song_duration float not null,
                                         pl_id integer not null,
                                         pl_song_id integer not null,
                                         primary key (song_id),
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
        cursor.execute("""insert into playlists values((select count(playlists.pl_id) from playlists),
                                                       ?,
                                                       ?,
                                                       (select count(playlists.guild_id) from guilds
                                                        left outer join playlists on playlists.guild_id = guilds.guild_id
                                                        where guilds.guild_id = ?))""",
                       (playlist["name"], guild["id"], guild["id"]))
        for song in playlist["songs"]:
            cursor.execute("""insert into songs values((select count(songs.song_id) from songs),
                                                       ?,
                                                       ?,
                                                       ?,
                                                       (select playlists.pl_id from playlists where playlists.guild_id = ? and playlists.guild_pl_id = ?),
                                                       (select count(songs.pl_id) from playlists
                                                        left outer join songs on songs.pl_id = playlists.pl_id
                                                        where playlists.guild_id = ? and playlists.guild_pl_id = ?))""",
                           (song["name"], song["file"], song["duration"], guild["id"], guild["playlists"].index(playlist), guild["id"], guild["playlists"].index(playlist)))
    for user in guild["users"]:
        try: cursor.execute("insert into users values(?)", (user["id"],))
        except: pass
        cursor.execute("insert into guild_users values(?, ?)", (guild["id"], user["id"]))

connection.commit()
connection.close()
