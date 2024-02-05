import os
import sqlite3
import yaml

flat_file = "Guilds.yaml"
if not os.path.exists(flat_file): yaml.safe_dump({"guilds": []}, open(flat_file, "w"), indent=4)
data = yaml.safe_load(open(flat_file, "r"))

connection = sqlite3.connect("Guilds.db")
cursor = connection.cursor()

for guild in cursor.execute("select * from guilds").fetchall():
    playlists = []
    for playlist in cursor.execute("select guild_pl_id, pl_name from playlists where guild_id = ? order by guild_pl_id", (guild[0],)).fetchall():
        songs = []
        for song in (cursor.execute("""select song_name, song_url, song_duration from songs
                                       left outer join playlists on playlists.pl_id = songs.pl_id
                                       where playlists.guild_id = ? and playlists.guild_pl_id = ?
                                       order by songs.pl_song_id""",
                                    (guild[0], playlist[0]))
                           .fetchall()):
            songs.append({"name": song[0], "file": song[1], "duration": song[2]})
        playlists.append({"name": playlist[1], "songs": songs})
    users = []
    for user in cursor.execute("select user_id from guild_users where guild_id = ?", (guild[0],)).fetchall(): users.append({"id": user[0]})
    data["guilds"].append({"id": guild[0],
                           "language": guild[1],
                           "keep": bool(guild[3]),
                           "repeat": bool(guild[4]),
                           "playlists": playlists,
                           "users": users})
    if guild[2] is not None: data["guilds"][len(data["guilds"]) - 1]["working_thread_id"] = guild[2]

connection.close()

yaml.safe_dump(data, open(flat_file, "w"), indent=4)
