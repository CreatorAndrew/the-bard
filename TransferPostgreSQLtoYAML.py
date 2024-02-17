import os
import psycopg2
import yaml

variables = yaml.safe_load(open("Variables.yaml", "r"))

flat_file = "Guilds.yaml"
if not os.path.exists(flat_file): yaml.safe_dump({"guilds": []}, open(flat_file, "w"), indent=4)
data = yaml.safe_load(open(flat_file, "r"))

connection = psycopg2.connect(database=variables["postgresql_credentials"]["database"],
                              user=variables["postgresql_credentials"]["user"],
                              password=variables["postgresql_credentials"]["password"],
                              host=variables["postgresql_credentials"]["host"],
                              port=variables["postgresql_credentials"]["port"])
cursor = connection.cursor()

cursor.execute("select * from guilds")
for guild in cursor.fetchall():
    playlists = []
    cursor.execute("select guild_pl_id, pl_name from playlists where guild_id = %s order by guild_pl_id", (guild[0],))
    for playlist in cursor.fetchall():
        songs = []
        cursor.execute("""select song_name, song_url, song_duration from songs
                          left outer join playlists on playlists.pl_id = songs.pl_id
                          where guild_id = %s and guild_pl_id = %s
                          order by pl_song_id""",
                       (guild[0], playlist[0]))
        for song in cursor.fetchall(): songs.append({"name": song[0], "file": song[1], "duration": song[2]})
        playlists.append({"name": playlist[1], "songs": songs})
    users = []
    cursor.execute("select user_id from guild_users where guild_id = %s", (guild[0],))
    for user in cursor.fetchall(): users.append({"id": user[1]})
    data["guilds"].append({"id": guild[0],
                           "language": guild[1],
                           "keep": bool(guild[3]),
                           "repeat": bool(guild[4]),
                           "playlists": playlists,
                           "users": users})
    if guild[2] is not None: data["guilds"][len(data["guilds"]) - 1]["working_thread_id"] = guild[2]

connection.close()

yaml.safe_dump(data, open(flat_file, "w"), indent=4)
