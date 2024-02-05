import sqlite3

connection = sqlite3.connect("Guilds.db")
cursor = connection.cursor()

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

connection.close()
