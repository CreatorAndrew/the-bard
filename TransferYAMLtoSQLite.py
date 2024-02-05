import sqlite3
import yaml

data = yaml.safe_load(open("Guilds.yaml", "r"))

connection = sqlite3.connect("Guilds.db")
cursor = connection.cursor()

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
        try: cursor.execute("""insert into users values(?)""", (user["id"],))
        except: pass
        cursor.execute("insert into guild_users values(?, ?)", (guild["id"], user["id"]))

connection.commit()
connection.close()
