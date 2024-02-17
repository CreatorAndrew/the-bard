import psycopg2
import subprocess
import yaml

variables = yaml.safe_load(open("Variables.yaml", "r"))

data = yaml.safe_load(open("Guilds.yaml", "r"))

subprocess.run(["psql",
                "-c",
                f"create database \"{variables['postgresql_credentials']['database']}\"",
                f"""user={variables["postgresql_credentials"]["user"]}
                    dbname={variables["postgresql_credentials"]["user"]}
                    password={variables["postgresql_credentials"]["password"]}"""],
               stdout=subprocess.DEVNULL,
               stderr=subprocess.STDOUT)
connection = psycopg2.connect(database=variables["postgresql_credentials"]["database"],
                              user=variables["postgresql_credentials"]["user"],
                              password=variables["postgresql_credentials"]["password"],
                              host=variables["postgresql_credentials"]["host"],
                              port=variables["postgresql_credentials"]["port"])
connection.autocommit = True
cursor = connection.cursor()
try:
    cursor.execute("""create table guilds(guild_id bigint not null,
                                          guild_lang text not null,
                                          working_thread_id bigint null,
                                          keep_in_voice boolean not null,
                                          repeat_queue boolean not null,
                                          primary key (guild_id))""")
    cursor.execute("""create table playlists(pl_id bigint not null,
                                             pl_name text not null,
                                             guild_id bigint not null,
                                             guild_pl_id bigint not null,
                                             primary key (pl_id),
                                             foreign key (guild_id) references guilds(guild_id))""")
    cursor.execute("""create table songs(song_id bigint not null,
                                         song_name text not null,
                                         song_url text not null,
                                         song_duration float not null,
                                         pl_id bigint not null,
                                         pl_song_id bigint not null,
                                         primary key (song_id),
                                         foreign key (pl_id) references playlists(pl_id))""")
    cursor.execute("create table users(user_id bigint not null, primary key (user_id))")
    cursor.execute("""create table guild_users(guild_id bigint not null,
                                               user_id bigint not null,
                                               primary key (guild_id, user_id),
                                               foreign key (guild_id) references guilds(guild_id),
                                               foreign key (user_id) references users(user_id))""")
except: pass

for guild in data["guilds"]:
    try: working_thread_id = guild["working_thread_id"]
    except: working_thread_id = None
    cursor.execute("insert into guilds values(%s, %s, %s, %s, %s)",
                   (guild["id"], guild["language"], working_thread_id, guild["keep"], guild["repeat"]))
    for playlist in guild["playlists"]:
        cursor.execute("""insert into playlists values((select count(pl_id) from playlists),
                                                       %s,
                                                       %s,
                                                       (select count(pl_id) from playlists where guild_id = %s))""",
                       (playlist["name"], guild["id"], guild["id"]))
        for song in playlist["songs"]:
            cursor.execute("""insert into songs values((select count(song_id) from songs),
                                                       %s,
                                                       %s,
                                                       %s,
                                                       (select pl_id from playlists where guild_id = %s and guild_pl_id = %s),
                                                       (select count(songs.pl_id) from playlists
                                                        left outer join songs on songs.pl_id = playlists.pl_id
                                                        where guild_id = %s and guild_pl_id = %s))""",
                           (song["name"],
                            song["file"],
                            song["duration"],
                            guild["id"],
                            guild["playlists"].index(playlist),
                            guild["id"],
                            guild["playlists"].index(playlist)))
    for user in guild["users"]:
        try: cursor.execute("insert into users values(%s)", (user["id"],))
        except: pass
        cursor.execute("insert into guild_users values(%s, %s)", (guild["id"], user["id"]))

connection.close()
