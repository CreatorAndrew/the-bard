from sys import path
from os.path import dirname, exists

path.insert(0, dirname(path[0]))
from psycopg import connect
from yaml import safe_dump as dump, safe_load as load
from utils import CREDENTIALS, VARIABLES

FLAT_FILE = f"{VARIABLES['name']}.yaml"
if not exists(FLAT_FILE):
    dump({"guilds": []}, open(FLAT_FILE, "w"), indent=4)
data = load(open(FLAT_FILE, "r"))

overall_songs = []


def omit_keys(*keys, dict: dict):
    temp_dict = dict.copy()
    for key in keys:
        del temp_dict[key]
    return temp_dict


connection = connect(CREDENTIALS)
cursor = connection.cursor()

cursor.execute("select * from guilds_music")
for guild in cursor.fetchall():
    playlists = []
    cursor.execute(
        "select guild_pl_id, pl_name from playlists where guild_id = %s order by guild_pl_id",
        (guild[0],),
    )
    for playlist in cursor.fetchall():
        songs = []
        cursor.execute(
            """
            select pl_songs.song_name, song_url, song_duration, songs.guild_id, channel_id, message_id, attachment_index from pl_songs
            left outer join songs on songs.song_id = pl_songs.song_id
            left outer join playlists on playlists.pl_id = pl_songs.pl_id
            where playlists.guild_id = %s and guild_pl_id = %s
            order by pl_song_id
            """,
            (guild[0], playlist[0]),
        )
        for song in cursor.fetchall():
            song_dict = {
                "id": len(overall_songs),
                "name": song[0],
                "file": song[1],
                "duration": song[2],
                "guild_id": song[3],
                "channel_id": song[4],
                "message_id": song[5],
                "attachment_index": song[6],
            }
            overall_songs.append(song_dict)
            overall_songs_mapped = list(
                map(lambda song: omit_keys("id", dict=song), overall_songs)
            )
            songs.append(
                overall_songs[
                    overall_songs_mapped.index(omit_keys("id", dict=song_dict))
                ]
            )
        playlists.append({"name": playlist[1], "songs": songs})
    _guild = next(
        guild_searched
        for guild_searched in data["guilds"]
        if guild_searched["id"] == guild[0]
    )
    if guild[1] is not None:
        _guild["working_thread_id"] = guild[1]
    _guild["keep"] = bool(guild[2])
    _guild["repeat"] = bool(guild[3])
    _guild["playlists"] = playlists

connection.close()

dump(data, open(FLAT_FILE, "w"), indent=4)
