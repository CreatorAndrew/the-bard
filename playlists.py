from asyncio import sleep
from datetime import datetime
from io import BytesIO
import requests
from yaml import safe_dump as dump, safe_load as load
from discord import File, SelectOption
from discord.app_commands import Choice
from discord.ui import Select, View
from utils import get_filename, page_selector, polished_message, polished_url, VARIABLES

if VARIABLES["storage"] == "yaml":
    SONG_ID_KEY = "id"
    SONG_NAME_KEY = "name"
    GUILD_ID_KEY = "guild_id"
    CHANNEL_ID_KEY = "channel_id"
    MESSAGE_ID_KEY = "message_id"
    ATTACHMENT_INDEX_KEY = "attachment_index"
    SONG_URL_KEY = "file"
    SONG_DURATION_KEY = "duration"
else:
    GET_PLAYLIST_ID_AND_NAME_AND_SONG_COUNT_STATEMENT = """
        select pl_songs.pl_id, pl_name, count(song_id) from pl_songs
        right outer join playlists on playlists.pl_id = pl_songs.pl_id
        where guild_id = ? and guild_pl_id = ?
        group by pl_songs.pl_id, pl_name
    """
    GET_SONGS_STATEMENT_ABRIDGED = """
        select song_id, song_name, song_url from pl_songs
        left outer join playlists on playlists.pl_id = pl_songs.pl_id
        where guild_id = ? and guild_pl_id = ?
        order by pl_song_id
    """
    GET_SONGS_STATEMENT = """
        select pl_songs.song_id, pl_songs.song_name, songs.guild_id, channel_id,
        message_id, attachment_index, song_url, song_duration from pl_songs
        left outer join songs on songs.song_id = pl_songs.song_id
        left outer join playlists on playlists.pl_id = pl_songs.pl_id
        where playlists.guild_id = ? and guild_pl_id = ?
    """
    SONG_ID_KEY = 0
    SONG_NAME_KEY = 1
    GUILD_ID_KEY = 2
    CHANNEL_ID_KEY = 3
    MESSAGE_ID_KEY = 4
    ATTACHMENT_INDEX_KEY = 5
    SONG_URL_KEY = 6
    SONG_DURATION_KEY = 7


def get_next_song_id(data):
    songs = []
    for guild in data["guilds"]:
        for playlist in guild["playlists"]:
            songs += playlist["songs"]
    return sorted(songs, key=lambda song: song["id"], reverse=True)[0]["id"] + 1


async def declare_command_invalid(self, context, strings):
    await context.followup.delete_message(
        (await context.followup.send("...", silent=True)).id
    )
    await context.followup.send(strings["invalid_command"], ephemeral=True)
    self.lock.release()


async def playlists_command(
    self,
    context,
    from_guild,
    transfer,
    add,
    clone,
    into,
    move,
    rename,
    remove,
    load,
    list_songs,
    new_name,
    new_index,
):
    # add a playlist
    if add is not None:
        await add_playlist(self, context, add, new_index)
    # import a playlist
    elif from_guild is not None:
        await import_playlist(self, context, from_guild, transfer, new_name, new_index)
    # clone a playlist or copy its tracks into another playlist
    elif clone is not None:
        await clone_playlist(self, context, clone, into, new_name, new_index)
    # change a playlist's position in the order of playlists
    elif move is not None:
        await move_playlist(self, context, move, new_index)
    # rename a playlist
    elif rename is not None:
        await rename_playlist(self, context, rename, new_name)
    # remove a playlist
    elif remove is not None:
        await remove_playlist(self, context, remove)
    # load a playlist
    elif load is not None:
        await load_playlist(self, context, load)
    # return a list of tracks in the playlist
    elif list_songs is not None:
        await playlist_list_songs(self, context, list_songs)
    # return a list of playlists for the calling guild
    else:
        await list_playlists(self, context)


async def playlist_command(
    self,
    context,
    select,
    file,
    song_url,
    move,
    rename,
    remove,
    load,
    new_name,
    new_index,
):
    # add a track to the playlist
    if file is not None or song_url is not None:
        await playlist_add_song(
            self, context, select, file, song_url, new_name, new_index
        )
    # change the position of a track within the playlist
    elif move is not None:
        await playlist_move_song(self, context, select, move, new_index)
    # rename a track in the playlist
    elif rename is not None:
        await playlist_rename_song(self, context, select, rename, new_name)
    # remove a track from the playlist
    elif remove is not None:
        await playlist_remove_song(self, context, select, remove)
    # load a track into the queue
    elif load is not None:
        await load_playlist(self, context, select, lambda song: song["index"] == load - 1)
    # return a list of tracks in the playlist
    else:
        await playlist_list_songs(self, context, select)


async def add_playlist(self, context, playlist, new_index):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # add a playlist
    if playlist is not None:
        if new_index is None:
            new_index = (playlist_count + 1) if VARIABLES["storage"] == "yaml" else None
        elif new_index < 1 or new_index > playlist_count + 1:
            await declare_command_invalid(self, context, strings)
            return
        if VARIABLES["storage"] == "yaml":
            guild["playlists"].insert(new_index - 1, {"name": playlist, "songs": []})
        else:
            try:
                await self.cursor.execute(
                    """
                    insert into playlists values(
                        (select * from (select max(pl_id) from playlists) as max_pl_id) + 1,
                        ?,
                        ?,
                        (
                            select * from (
                                select count(pl_id) from playlists where guild_id = ?
                            ) as count_pl_id
                        )
                    )
                    """,
                    (playlist, context.guild.id, context.guild.id),
                )
            except:
                await self.cursor.execute(
                    """
                    insert into playlists values(
                        0,
                        ?,
                        ?,
                        (
                            select * from (
                                select count(pl_id) from playlists where guild_id = ?
                            ) as count_pl_id
                        )
                    )
                    """,
                    (playlist, context.guild.id, context.guild.id),
                )
            if new_index is None:
                new_index = playlist_count + 1
            else:
                await self.cursor.execute(
                    """
                    update playlists set guild_pl_id = guild_pl_id + 1
                    where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?
                    """,
                    (new_index - 1, playlist_count, context.guild.id),
                )
                await self.cursor.execute(
                    """
                    update playlists set guild_pl_id = ?
                    where pl_id = (select * from (select max(pl_id) from playlists) as max_pl_id)
                    """,
                    (new_index - 1,),
                )
        await context.followup.send(
            polished_message(
                strings["add_playlist"],
                {"playlist": playlist, "playlist_index": new_index},
            )
        )
    else:
        await declare_command_invalid(self, context, strings)
        return
    if VARIABLES["storage"] == "yaml":
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        await self.connection.commit()
    self.lock.release()


async def import_playlist(self, context, from_guild, playlist, new_name, new_index):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # import a playlist
    if from_guild is not None:
        if VARIABLES["storage"] == "yaml":
            for guild_searched in self.data["guilds"]:
                if guild_searched["id"] == int(from_guild):
                    from_guild_playlists = guild_searched["playlists"]
                    from_guild_playlist_count = len(from_guild_playlists)
                    break
        else:
            from_guild_playlist_count = (
                await self.cursor.execute_fetchone(
                    "select count(pl_id) from playlists where guild_id = ?",
                    (int(from_guild),),
                )
            )[0]
        if playlist is None or playlist < 1 or playlist > from_guild_playlist_count:
            await declare_command_invalid(self, context, strings)
            return
        if self.cursor is not None:
            songs = await self.cursor.execute_fetchall(
                GET_SONGS_STATEMENT_ABRIDGED, (int(from_guild), playlist - 1)
            )
        if new_name is None:
            new_name = (
                from_guild_playlists[playlist - 1]["name"]
                if VARIABLES["storage"] == "yaml"
                else (
                    await self.cursor.execute_fetchone(
                        "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                        (int(from_guild), playlist - 1),
                    )
                )[0]
            )
        if new_index is None:
            new_index = (playlist_count + 1) if VARIABLES["storage"] == "yaml" else None
        elif new_index < 1 or new_index > playlist_count + 1:
            await declare_command_invalid(self, context, strings)
            return
        if VARIABLES["storage"] == "yaml":
            guild["playlists"].insert(
                new_index - 1,
                {
                    "name": new_name,
                    "songs": from_guild_playlists[playlist - 1]["songs"].copy(),
                },
            )
        else:
            await self.cursor.execute(
                """
                insert into playlists values(
                    (select * from (select max(pl_id) from playlists) as max_pl_id) + 1,
                    ?,
                    ?,
                    (
                        select * from (
                            select count(pl_id) from playlists where guild_id = ?
                        ) as count_pl_id
                    )
                )
                """,
                (new_name, context.guild.id, context.guild.id),
            )
            for song in songs:
                await self.cursor.execute(
                    """
                    insert into pl_songs values(
                        ?,
                        ?,
                        ?,
                        (select max(pl_id) from playlists),
                        (
                            select * from (
                                select count(song_id) from pl_songs
                                where pl_id = (select max(pl_id) from playlists)
                            ) as count_song_id
                        )
                    )
                    """,
                    (song[0], song[1], song[2]),
                )
            if new_index is None:
                new_index = playlist_count + 1
            else:
                await self.cursor.execute(
                    """
                    update playlists set guild_pl_id = guild_pl_id + 1
                    where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?
                    """,
                    (new_index - 1, playlist_count, context.guild.id),
                )
                await self.cursor.execute(
                    """
                    update playlists set guild_pl_id = ?
                    where pl_id = (select * from (select max(pl_id) from playlists) as max_pl_id)
                    """,
                    (new_index - 1,),
                )
        await context.followup.send(
            polished_message(
                strings["clone_playlist"],
                {
                    "playlist": (
                        from_guild_playlists[playlist - 1]["name"]
                        if VARIABLES["storage"] == "yaml"
                        else (
                            await self.cursor.execute_fetchone(
                                "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                                (int(from_guild), playlist - 1),
                            )
                        )[0]
                    ),
                    "playlist_index": playlist,
                    "into_playlist": new_name,
                    "into_playlist_index": new_index,
                },
            )
        )
    else:
        await declare_command_invalid(self, context, strings)
        return
    if VARIABLES["storage"] == "yaml":
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        await self.connection.commit()
    self.lock.release()


async def clone_playlist(self, context, playlist, into, new_name, new_index):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # clone a playlist or copy its tracks into another playlist
    if playlist is not None and 0 < playlist <= playlist_count:
        # clone a playlist
        if self.cursor is not None:
            songs = await self.cursor.execute_fetchall(
                GET_SONGS_STATEMENT_ABRIDGED, (context.guild.id, playlist - 1)
            )
        if into is None or into < 1 or into > playlist_count:
            playlist_name = (
                guild["playlists"][playlist - 1]["name"]
                if VARIABLES["storage"] == "yaml"
                else (
                    await self.cursor.execute_fetchone(
                        "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                        (context.guild.id, playlist - 1),
                    )
                )[0]
            )
            if new_name is None:
                new_name = playlist_name
            if new_index is None:
                new_index = (
                    (playlist_count + 1) if VARIABLES["storage"] == "yaml" else None
                )
            elif new_index < 1 or new_index > playlist_count + 1:
                await declare_command_invalid(self, context, strings)
                return
            if VARIABLES["storage"] == "yaml":
                guild["playlists"].insert(
                    new_index - 1,
                    {
                        "name": new_name,
                        "songs": guild["playlists"][playlist - 1]["songs"].copy(),
                    },
                )
            else:
                await self.cursor.execute(
                    """
                    insert into playlists values(
                        (select * from (select max(pl_id) from playlists) as max_pl_id) + 1,
                        ?,
                        ?,
                        (
                            select * from (
                                select count(pl_id) from playlists where guild_id = ?
                            ) as count_pl_id
                        )
                    )
                    """,
                    (new_name, context.guild.id, context.guild.id),
                )
                for song in songs:
                    await self.cursor.execute(
                        """
                        insert into pl_songs values(
                            ?,
                            ?,
                            ?,
                            (select max(pl_id) from playlists),
                            (
                                select * from (
                                    select count(song_id) from pl_songs
                                    where pl_id = (select max(pl_id) from playlists)
                                ) as count_song_id
                            )
                        )
                        """,
                        (song[0], song[1], song[2]),
                    )
                if new_index is None:
                    new_index = playlist_count + 1
                else:
                    await self.cursor.execute(
                        """
                        update playlists set guild_pl_id = guild_pl_id + 1
                        where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?
                        """,
                        (new_index - 1, playlist_count, context.guild.id),
                    )
                    await self.cursor.execute(
                        """
                        update playlists set guild_pl_id = ?
                        where pl_id = (select * from (select max(pl_id) from playlists) as max_pl_id)
                        """,
                        (new_index - 1,),
                    )
            await context.followup.send(
                polished_message(
                    strings["clone_playlist"],
                    {
                        "playlist": playlist_name,
                        "playlist_index": playlist,
                        "into_playlist": new_name,
                        "into_playlist_index": new_index,
                    },
                )
            )
        # copy a playlist's tracks into another playlist
        else:
            if VARIABLES["storage"] == "yaml":
                guild["playlists"][into - 1]["songs"] += guild["playlists"][
                    playlist - 1
                ]["songs"]
                playlist = guild["playlists"][playlist - 1]["name"]
                into_playlist = guild["playlists"][into - 1]["name"]
            else:
                for song in songs:
                    await self.cursor.execute(
                        """
                        insert into pl_songs values(
                            ?,
                            ?,
                            ?,
                            (select pl_id from playlists where guild_id = ? and guild_pl_id = ?),
                            (
                                select * from (
                                    select count(song_id) from pl_songs
                                    left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                    where guild_id = ? and guild_pl_id = ?
                                ) as count_song_id
                            )
                        )
                        """,
                        (
                            song[0],
                            song[1],
                            song[2],
                            context.guild.id,
                            into - 1,
                            context.guild.id,
                            into - 1,
                        ),
                    )

                playlist = (
                    await self.cursor.execute_fetchone(
                        "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                        (context.guild.id, playlist - 1),
                    )
                )[0]
                into_playlist = (
                    await self.cursor.execute_fetchone(
                        "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                        (context.guild.id, into - 1),
                    )
                )[0]
            await context.followup.send(
                polished_message(
                    strings["clone_playlist"],
                    {
                        "playlist": playlist_name,
                        "playlist_index": playlist,
                        "into_playlist": into_playlist,
                        "into_playlist_index": into,
                    },
                )
            )
    else:
        await declare_command_invalid(self, context, strings)
        return
    if VARIABLES["storage"] == "yaml":
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        await self.connection.commit()
    self.lock.release()


async def move_playlist(self, context, playlist, new_index):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # change a playlist's position in the order of playlists
    if playlist is not None and 0 < playlist <= playlist_count:
        if new_index is None or new_index < 1 or new_index > playlist_count:
            await declare_command_invalid(self, context, strings)
            return
        if VARIABLES["storage"] == "yaml":
            playlist_copies = guild["playlists"].copy()
            guild["playlists"].remove(playlist_copies[playlist - 1])
            guild["playlists"].insert(new_index - 1, playlist_copies[playlist - 1])
        else:
            playlist_copies = await self.cursor.execute_fetchall(
                "select pl_id, pl_name from playlists where guild_id = ? order by guild_pl_id",
                (context.guild.id,),
            )
            if new_index > playlist:
                await self.cursor.execute(
                    """
                    update playlists set guild_pl_id = guild_pl_id - 1
                    where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?
                    """,
                    (playlist - 1, new_index - 1, context.guild.id),
                )
            elif new_index < playlist:
                await self.cursor.execute(
                    """
                    update playlists set guild_pl_id = guild_pl_id + 1
                    where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?
                    """,
                    (new_index - 1, playlist - 1, context.guild.id),
                )
            await self.cursor.execute(
                "update playlists set guild_pl_id = ? where pl_id = ?",
                (new_index - 1, playlist_copies[playlist - 1][0]),
            )
        await context.followup.send(
            polished_message(
                strings["move_playlist"],
                {
                    "playlist": playlist_copies[playlist - 1][SONG_NAME_KEY],
                    "playlist_index": new_index,
                },
            )
        )
    else:
        await declare_command_invalid(self, context, strings)
        return
    if VARIABLES["storage"] == "yaml":
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        await self.connection.commit()
    self.lock.release()


async def rename_playlist(self, context, playlist, new_name):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # rename a playlist
    if playlist is not None and 0 < playlist <= playlist_count:
        if new_name is None:
            await declare_command_invalid(self, context, strings)
            return
        if VARIABLES["storage"] == "yaml":
            await context.followup.send(
                polished_message(
                    strings["rename_playlist"],
                    {
                        "playlist": guild["playlists"][playlist - 1]["name"],
                        "playlist_index": playlist,
                        "name": new_name,
                    },
                )
            )
            guild["playlists"][playlist - 1]["name"] = new_name
        else:
            await context.followup.send(
                polished_message(
                    strings["rename_playlist"],
                    {
                        "playlist": (
                            await self.cursor.execute_fetchone(
                                "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                                (context.guild.id, playlist - 1),
                            )
                        )[0],
                        "playlist_index": playlist,
                        "name": new_name,
                    },
                )
            )
            await self.cursor.execute(
                "update playlists set pl_name = ? where guild_id = ? and guild_pl_id = ?",
                (new_name, context.guild.id, playlist - 1),
            )
    else:
        await declare_command_invalid(self, context, strings)
        return
    if VARIABLES["storage"] == "yaml":
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        await self.connection.commit()
    self.lock.release()


async def remove_playlist(self, context, playlist):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # remove a playlist
    if playlist is not None and 0 < playlist <= playlist_count:
        if VARIABLES["storage"] == "yaml":
            await context.followup.send(
                polished_message(
                    strings["remove_playlist"],
                    {
                        "playlist": guild["playlists"][playlist - 1]["name"],
                        "playlist_index": playlist,
                    },
                )
            )
            guild["playlists"].remove(guild["playlists"][playlist - 1])
        else:
            await context.followup.send(
                polished_message(
                    strings["remove_playlist"],
                    {
                        "playlist": (
                            await self.cursor.execute_fetchone(
                                "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                                (context.guild.id, playlist - 1),
                            )
                        )[0],
                        "playlist_index": playlist,
                    },
                )
            )
            await self.cursor.execute(
                """
                delete from pl_songs
                where pl_id = (select pl_id from playlists where guild_id = ? and guild_pl_id = ?)
                """,
                (context.guild.id, playlist - 1),
            )
            await self.cursor.execute(
                "delete from songs where song_id not in (select song_id from pl_songs)"
            )
            await self.cursor.execute(
                "delete from playlists where guild_id = ? and guild_pl_id = ?",
                (context.guild.id, playlist - 1),
            )
            await self.cursor.execute(
                """
                update playlists set guild_pl_id = guild_pl_id - 1
                where guild_pl_id >= ? and guild_id = ?
                """,
                (playlist - 1, context.guild.id),
            )
    else:
        await declare_command_invalid(self, context, strings)
        return
    if VARIABLES["storage"] == "yaml":
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        await self.connection.commit()
    self.lock.release()


async def load_playlist(self, context, playlist, filter_callback=lambda x: True):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # load a playlist
    if playlist is not None and 0 < playlist <= playlist_count:
        songs = (
            guild["playlists"][playlist - 1]["songs"]
            if VARIABLES["storage"] == "yaml"
            else await self.cursor.execute_fetchall(
                f"{GET_SONGS_STATEMENT} order by pl_song_id",
                (context.guild.id, playlist - 1),
            )
        )
        self.lock.release()
        if songs:
            proper_songs = []
            for index, song in enumerate(songs):
                if song[SONG_URL_KEY] is None:
                    try:
                        song_message = self.messages[str(song[MESSAGE_ID_KEY])]
                        if (
                            int(datetime.timestamp(datetime.now()))
                            > song_message["expiration"]
                        ):
                            raise Exception
                    except:
                        song_message = {
                            "message": await self.bot.get_guild(song[GUILD_ID_KEY])
                            .get_channel_or_thread(song[CHANNEL_ID_KEY])
                            .fetch_message(song[MESSAGE_ID_KEY]),
                            "expiration": int(datetime.timestamp(datetime.now()))
                            + 1209600,
                        }
                        self.messages[str(song[MESSAGE_ID_KEY])] = song_message
                    song_file = str(
                        song_message["message"].attachments[song[ATTACHMENT_INDEX_KEY]]
                    )
                else:
                    song_file = song[SONG_URL_KEY]
                proper_songs.append(
                    {
                        "index": index,
                        "name": song[SONG_NAME_KEY],
                        "file": song_file,
                        "duration": song[SONG_DURATION_KEY],
                    }
                )
            if VARIABLES["storage"] == "yaml":
                await context.followup.send(
                    polished_message(
                        strings["load_playlist"],
                        {
                            "playlist": guild["playlists"][playlist - 1]["name"],
                            "playlist_index": playlist,
                        },
                    )
                )
            else:
                try:
                    if context.user.voice.channel is not None:
                        await context.followup.send(
                            polished_message(
                                strings["load_playlist"],
                                {
                                    "playlist": (
                                        await self.cursor.execute_fetchone(
                                            """
                                            select pl_name from playlists
                                            where guild_id = ? and guild_pl_id = ?
                                            """,
                                            (context.guild.id, playlist - 1),
                                        )
                                    )[0],
                                    "playlist_index": playlist,
                                },
                            )
                        )
                except:
                    pass
            await self.play_song(
                context, playlist=list(filter(filter_callback, proper_songs))
            )
        else:
            await context.followup.delete_message(
                (await context.followup.send("...", silent=True)).id
            )
            await context.followup.send(
                polished_message(
                    strings["playlist_no_songs"],
                    {
                        "playlist": (
                            guild["playlists"][playlist - 1]["name"]
                            if VARIABLES["storage"] == "yaml"
                            else (
                                await self.cursor.execute_fetchone(
                                    """
                                    select pl_name from playlists
                                    where guild_id = ? and guild_pl_id = ?
                                    """,
                                    (context.guild.id, playlist - 1),
                                )
                            )[0]
                        ),
                        "playlist_index": playlist,
                    },
                ),
                ephemeral=True,
            )
        return
    else:
        await declare_command_invalid(self, context, strings)
        return


async def list_playlists(self, context):
    await context.response.defer(ephemeral=True)
    guild = self.guilds[str(context.guild.id)]
    if VARIABLES["storage"] == "yaml":
        playlists = []
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                _guild = guild_searched
                break
    else:
        playlists = await self.cursor.execute_fetchall(
            "select pl_name from playlists where guild_id = ? order by guild_pl_id",
            (context.guild.id,),
        )
    message = guild["strings"]["playlists_header"] + "\n"
    if not (playlists or (VARIABLES["storage"] == "yaml" and _guild["playlists"])):
        await context.followup.send(guild["strings"]["no_playlists"])
        return
    pages = []
    for index in range(
        len(_guild["playlists"] if VARIABLES["storage"] == "yaml" else playlists)
    ):
        previous_message = message
        new_message = polished_message(
            guild["strings"]["playlist"] + "\n",
            {
                "playlist": (
                    _guild["playlists"][index]["name"]
                    if VARIABLES["storage"] == "yaml"
                    else playlists[index][0]
                ),
                "playlist_index": index + 1,
            },
        )
        message += new_message
        if len(message) > 2000:
            pages.append(previous_message)
            message = guild["strings"]["playlists_header"] + "\n" + new_message
    pages.append(message)
    await page_selector(context, guild["strings"], pages, 0)


async def playlist_add_song(
    self, context, playlist, file, song_url, new_index, new_name
):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    if playlist is not None and file:
        if file is None and song_url is not None:
            url = song_url
        elif file is not None and song_url is None:
            url = str(file)
        else:
            await context.followup.delete_message(
                (await context.followup.send("...", silent=True)).id
            )
            await context.followup.send(strings["invalid_command"], ephemeral=True)
            return
        response = requests.get(url, stream=True)
        try:
            metadata = self.get_metadata(BytesIO(response.content), url)
        except:
            await context.followup.delete_message(
                (await context.followup.send("...", silent=True)).id
            )
            await context.followup.send(
                polished_message(strings["invalid_url"], {"url": url}),
                ephemeral=True,
            )
            return
        # verify that the URL file is a media container
        if not any(
            content_type in response.headers.get("Content-Type", "")
            for content_type in ["audio", "video"]
        ):
            await context.followup.delete_message(
                (await context.followup.send("...", silent=True)).id
            )
            await context.followup.send(
                polished_message(
                    strings["invalid_song"],
                    {"song": polished_url(url, metadata["name"])},
                ),
                ephemeral=True,
            )
            return
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # select a playlist to modify or show the contents of
    if playlist is None:
        await declare_command_invalid(self, context, strings)
        return
    if 0 < playlist <= playlist_count:
        if VARIABLES["storage"] == "yaml":
            playlist_name = guild["playlists"][playlist - 1]["name"]
            song_count = len(guild["playlists"][playlist - 1]["songs"])
        else:
            global_playlist_id, playlist_name, song_count = (
                await self.cursor.execute_fetchone(
                    GET_PLAYLIST_ID_AND_NAME_AND_SONG_COUNT_STATEMENT,
                    (context.guild.id, playlist - 1),
                )
            )
        # add a track to the playlist
        if file is not None or song_url is not None:
            if new_name is None:
                new_name = metadata["name"]
            if new_index is None:
                new_index = (song_count + 1) if VARIABLES["storage"] == "yaml" else None
            elif new_index < 1 or new_index > song_count + 1:
                await declare_command_invalid(self, context, strings)
                return
            if VARIABLES["storage"] == "yaml":
                song_id = get_next_song_id(self.data)
                song = {
                    "name": new_name,
                    "index": new_index,
                    "duration": metadata["duration"],
                }
                guild["playlists"][playlist - 1]["songs"].insert(
                    song["index"] - 1,
                    {
                        "id": song_id,
                        "name": song["name"],
                        "file": url,
                        "duration": song["duration"],
                        "guild_id": context.guild.id,
                        "channel_id": 0,
                        "message_id": 0,
                        "attachment_index": 0,
                    },
                )
            else:
                try:
                    await self.cursor.execute(
                        """
                        insert into songs values(
                            (select * from (select max(song_id) from songs) as max_song_id) + 1,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?
                        )
                        """,
                        (
                            new_name,
                            metadata["duration"],
                            context.guild.id,
                            0,
                            0,
                            0,
                        ),
                    )
                except:
                    await self.cursor.execute(
                        "insert into songs values(0, ?, ?, ?, ?, ?, ?)",
                        (
                            new_name,
                            metadata["duration"],
                            context.guild.id,
                            0,
                            0,
                            0,
                        ),
                    )
                await self.cursor.execute(
                    """
                    insert into pl_songs values(
                        (select max(song_id) from songs),
                        ?,
                        ?,
                        (select pl_id from playlists where guild_id = ? and guild_pl_id = ?),
                        (
                            select * from (
                                select count(song_id) from pl_songs
                                left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                where guild_id = ? and guild_pl_id = ?
                            ) as count_song_id
                        )
                    )
                    """,
                    (
                        new_name,
                        url if file is None else None,
                        context.guild.id,
                        playlist - 1,
                        context.guild.id,
                        playlist - 1,
                    ),
                )
                if new_index is None:
                    new_index = song_count + 1
                else:
                    await self.cursor.execute(
                        """
                        update pl_songs set pl_song_id = pl_song_id + 1
                        where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?
                        """,
                        (new_index - 1, song_count, global_playlist_id),
                    )
                    await self.cursor.execute(
                        """
                        update pl_songs set pl_song_id = ?
                        where song_id = (select max(song_id) from songs)
                        """,
                        (new_index - 1,),
                    )
            await context.followup.send(
                polished_message(
                    strings["playlist_add_song"],
                    {
                        "playlist": playlist_name,
                        "playlist_index": playlist,
                        "song": polished_url(url, new_name),
                        "index": new_index,
                    },
                )
            )
            if file is not None:
                self.lock.release()
                if self.cursor is not None:
                    song_id = (
                        await self.cursor.execute_fetchone(
                            "select max(song_id) from songs"
                        )
                    )[0]
                await self.renew_attachment(
                    context.guild.id, context.channel.id, url, song_id
                )
                return
    else:
        await context.followup.delete_message(
            (await context.followup.send("...", silent=True)).id
        )
        await context.followup.send(
            polished_message(
                strings["invalid_playlist_number"], {"playlist_index": playlist}
            ),
            ephemeral=True,
        )
        self.lock.release()
        return
    if VARIABLES["storage"] == "yaml":
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        await self.connection.commit()
    self.lock.release()


async def playlist_move_song(self, context, playlist, song_index, new_index):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # select a playlist to modify or show the contents of
    if playlist is None:
        await declare_command_invalid(self, context, strings)
        return
    if 0 < playlist <= playlist_count:
        if VARIABLES["storage"] == "yaml":
            playlist_name = guild["playlists"][playlist - 1]["name"]
            song_count = len(guild["playlists"][playlist - 1]["songs"])
        else:
            global_playlist_id, playlist_name, song_count = (
                await self.cursor.execute_fetchone(
                    GET_PLAYLIST_ID_AND_NAME_AND_SONG_COUNT_STATEMENT,
                    (context.guild.id, playlist - 1),
                )
            )
        # change the position of a track within the playlist
        if (
            song_index is None
            or song_index < 1
            or song_index > song_count
            or new_index is None
            or new_index < 1
            or new_index > song_count
        ):
            await declare_command_invalid(self, context, strings)
            return
        if VARIABLES["storage"] == "yaml":
            song = guild["playlists"][playlist - 1]["songs"][song_index - 1]
        else:
            song_copies = await self.cursor.execute_fetchall(
                f"{GET_SONGS_STATEMENT} order by pl_song_id",
                (context.guild.id, playlist - 1),
            )
            if new_index > song_index:
                await self.cursor.execute(
                    """
                    update pl_songs set pl_song_id = pl_song_id - 1
                    where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?
                    """,
                    (song_index - 1, new_index - 1, global_playlist_id),
                )
            elif new_index < song_index:
                await self.cursor.execute(
                    """
                    update pl_songs set pl_song_id = pl_song_id + 1
                    where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?
                    """,
                    (new_index - 1, song_index - 1, global_playlist_id),
                )
            song = song_copies[song_index - 1]
            await self.cursor.execute(
                "update pl_songs set pl_song_id = ? where song_id = ?",
                (new_index - 1, song[0]),
            )
        if song[SONG_URL_KEY] is None:
            song_file = str(
                (
                    await self.bot.get_guild(song[GUILD_ID_KEY])
                    .get_channel_or_thread(song[CHANNEL_ID_KEY])
                    .fetch_message(song[MESSAGE_ID_KEY])
                ).attachments[song[ATTACHMENT_INDEX_KEY]]
            )
        else:
            song_file = song[SONG_URL_KEY]
        if VARIABLES["storage"] == "yaml":
            guild["playlists"][playlist - 1]["songs"].remove(song)
            guild["playlists"][playlist - 1]["songs"].insert(new_index - 1, song)
        await context.followup.send(
            polished_message(
                strings["playlist_move_song"],
                {
                    "playlist": playlist_name,
                    "playlist_index": playlist,
                    "song": polished_url(song_file, song[SONG_NAME_KEY]),
                    "index": new_index,
                },
            )
        )
    else:
        await context.followup.delete_message(
            (await context.followup.send("...", silent=True)).id
        )
        await context.followup.send(
            polished_message(
                strings["invalid_playlist_number"], {"playlist_index": playlist}
            ),
            ephemeral=True,
        )
        self.lock.release()
        return
    if VARIABLES["storage"] == "yaml":
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        await self.connection.commit()
    self.lock.release()


async def playlist_rename_song(self, context, playlist, song_index, new_name):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # select a playlist to modify or show the contents of
    if playlist is None:
        await declare_command_invalid(self, context, strings)
        return
    if 0 < playlist <= playlist_count:
        if VARIABLES["storage"] == "yaml":
            playlist_name = guild["playlists"][playlist - 1]["name"]
            song_count = len(guild["playlists"][playlist - 1]["songs"])
        else:
            global_playlist_id, playlist_name, song_count = (
                await self.cursor.execute_fetchone(
                    GET_PLAYLIST_ID_AND_NAME_AND_SONG_COUNT_STATEMENT,
                    (context.guild.id, playlist - 1),
                )
            )
        # rename a track in the playlist
        if (
            song_index is None
            or song_index < 1
            or song_index > song_count
            or new_name is None
        ):
            await declare_command_invalid(self, context, strings)
            return
        if VARIABLES["storage"] == "yaml":
            song = guild["playlists"][playlist - 1]["songs"][song_index - 1]
        else:
            (
                song_id,
                song_name,
                guild_id,
                channel_id,
                message_id,
                attachment_index,
                song_file,
            ) = await self.cursor.execute_fetchone(
                f"{GET_SONGS_STATEMENT} and pl_song_id = ?",
                (context.guild.id, playlist - 1, song_index - 1),
            )
        if song_file is None:
            song_file = str(
                (
                    await self.bot.get_guild(guild_id)
                    .get_channel_or_thread(channel_id)
                    .fetch_message(message_id)
                ).attachments[attachment_index]
            )
        elif VARIABLES["storage"] == "yaml":
            song_file = song["file"]
        await context.followup.send(
            polished_message(
                strings["playlist_rename_song"],
                {
                    "playlist": playlist_name,
                    "playlist_index": playlist,
                    "song": polished_url(
                        song_file,
                        (song["name"] if VARIABLES["storage"] == "yaml" else song_name),
                    ),
                    "index": song_index,
                    "name": new_name,
                },
            )
        )
        if VARIABLES["storage"] == "yaml":
            song["name"] = new_name
        else:
            await self.cursor.execute(
                "update pl_songs set song_name = ? where song_id = ?",
                (new_name, song_id),
            )
    else:
        await context.followup.delete_message(
            (await context.followup.send("...", silent=True)).id
        )
        await context.followup.send(
            polished_message(
                strings["invalid_playlist_number"], {"playlist_index": playlist}
            ),
            ephemeral=True,
        )
        self.lock.release()
        return
    if VARIABLES["storage"] == "yaml":
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        await self.connection.commit()
    self.lock.release()


async def playlist_remove_song(self, context, playlist, song_index):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # select a playlist to modify or show the contents of
    if playlist is None:
        await declare_command_invalid(self, context, strings)
        return
    if 0 < playlist <= playlist_count:
        if VARIABLES["storage"] == "yaml":
            playlist_name = guild["playlists"][playlist - 1]["name"]
            song_count = len(guild["playlists"][playlist - 1]["songs"])
        else:
            global_playlist_id, playlist_name, song_count = (
                await self.cursor.execute_fetchone(
                    GET_PLAYLIST_ID_AND_NAME_AND_SONG_COUNT_STATEMENT,
                    (context.guild.id, playlist - 1),
                )
            )
        # remove a track from the playlist
        if song_index is None or song_index < 1 or song_index > song_count:
            await declare_command_invalid(self, context, strings)
            return
        if VARIABLES["storage"] == "yaml":
            song = guild["playlists"][playlist - 1]["songs"][song_index - 1]
        else:
            (
                song_id,
                song_name,
                guild_id,
                channel_id,
                message_id,
                attachment_index,
                song_file,
            ) = await self.cursor.execute_fetchone(
                f"{GET_SONGS_STATEMENT} and pl_song_id = ?",
                (context.guild.id, playlist - 1, song_index - 1),
            )
        if song_file is None:
            song_file = str(
                (
                    await self.bot.get_guild(guild_id)
                    .get_channel_or_thread(channel_id)
                    .fetch_message(message_id)
                ).attachments[attachment_index]
            )
        elif VARIABLES["storage"] == "yaml":
            song_file = song["file"]
        if VARIABLES["storage"] == "yaml":
            guild["playlists"][playlist - 1]["songs"].remove(song)
        else:
            await self.cursor.execute(
                "delete from pl_songs where pl_song_id = ? and pl_id = ?",
                (song_index - 1, global_playlist_id),
            )
            await self.cursor.execute(
                "delete from songs where song_id not in (select song_id from pl_songs)"
            )
            await self.cursor.execute(
                "update pl_songs set pl_song_id = pl_song_id - 1 where pl_song_id >= ? and pl_id = ?",
                (song_index - 1, global_playlist_id),
            )
        await context.followup.send(
            polished_message(
                strings["playlist_remove_song"],
                {
                    "playlist": playlist_name,
                    "playlist_index": playlist,
                    "song": polished_url(
                        song_file,
                        (song["name"] if VARIABLES["storage"] == "yaml" else song_name),
                    ),
                    "index": song_index,
                },
            )
        )
    else:
        await context.followup.delete_message(
            (await context.followup.send("...", silent=True)).id
        )
        await context.followup.send(
            polished_message(
                strings["invalid_playlist_number"], {"playlist_index": playlist}
            ),
            ephemeral=True,
        )
        self.lock.release()
        return
    if VARIABLES["storage"] == "yaml":
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        await self.connection.commit()
    self.lock.release()


async def playlist_list_songs(self, context, playlist):
    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
    else:
        playlist_count = (
            await self.cursor.execute_fetchone(
                "select count(pl_id) from playlists where guild_id = ?",
                (context.guild.id,),
            )
        )[0]
    # select a playlist to modify or show the contents of
    if playlist is None:
        await declare_command_invalid(self, context, strings)
        return
    if 0 < playlist <= playlist_count:
        if VARIABLES["storage"] == "yaml":
            playlist_name = guild["playlists"][playlist - 1]["name"]
        else:
            global_playlist_id, playlist_name, song_count = (
                await self.cursor.execute_fetchone(
                    GET_PLAYLIST_ID_AND_NAME_AND_SONG_COUNT_STATEMENT,
                    (context.guild.id, playlist - 1),
                )
            )
        # return a list of tracks in the playlist
        await context.followup.delete_message(
            (await context.followup.send("...", silent=True)).id
        )
        message = polished_message(
            strings["playlist_songs_header"] + "\n",
            {"playlist": playlist_name, "playlist_index": playlist},
        )
        songs = (
            guild["playlists"][playlist - 1]["songs"]
            if VARIABLES["storage"] == "yaml"
            else await self.cursor.execute_fetchall(
                f"{GET_SONGS_STATEMENT} order by pl_song_id",
                (context.guild.id, playlist - 1),
            )
        )
        self.lock.release()
        if not songs:
            await context.followup.send(
                polished_message(
                    strings["playlist_no_songs"],
                    {"playlist": playlist_name, "playlist_index": playlist},
                ),
                ephemeral=True,
            )
            return
        pages = []
        for index, song in enumerate(songs, 1):
            previous_message = message
            if song[SONG_URL_KEY] is None:
                try:
                    song_message = self.messages[str(song[MESSAGE_ID_KEY])]
                    if (
                        int(datetime.timestamp(datetime.now()))
                        > song_message["expiration"]
                    ):
                        raise Exception
                except:
                    song_message = {
                        "message": await self.bot.get_guild(song[GUILD_ID_KEY])
                        .get_channel_or_thread(song[CHANNEL_ID_KEY])
                        .fetch_message(song[MESSAGE_ID_KEY]),
                        "expiration": int(datetime.timestamp(datetime.now())) + 1209600,
                    }
                    self.messages[str(song[MESSAGE_ID_KEY])] = song_message
                song_file = str(
                    song_message["message"].attachments[song[ATTACHMENT_INDEX_KEY]]
                )
            else:
                song_file = song[SONG_URL_KEY]
            new_message = polished_message(
                strings["song"] + "\n",
                {
                    "song": polished_url(song_file, song[SONG_NAME_KEY]),
                    "index": index,
                },
            )
            message += new_message
            if len(message) > 2000:
                pages.append(previous_message)
                message = "".join(
                    [
                        polished_message(
                            strings["playlist_songs_header"] + "\n",
                            {
                                "playlist": playlist_name,
                                "playlist_index": playlist,
                            },
                        ),
                        new_message,
                    ]
                )
        pages.append(message)
        await page_selector(context, strings, pages, 0)
        return
    await context.followup.delete_message(
        (await context.followup.send("...", silent=True)).id
    )
    await context.followup.send(
        polished_message(
            strings["invalid_playlist_number"], {"playlist_index": playlist}
        ),
        ephemeral=True,
    )
    self.lock.release()
    return


async def playlist_guild_autocompletion(self, context, current):
    guild_names = []
    if VARIABLES["storage"] == "yaml":
        guild_ids = []
        for guild in self.data["guilds"]:
            user_ids = []
            for user in guild["users"]:
                user_ids.append(user["id"])
            if context.user.id in user_ids:
                guild_ids.append([guild["id"]])
    else:
        guild_ids = await self.cursor.execute_fetchall(
            "select guild_id from guild_users where user_id = ?", (context.user.id,)
        )
    for guild_id in guild_ids:
        guild_name = self.bot.get_guild(guild_id[0]).name
        guild_name = guild_name[:97] + "..." if len(guild_name) > 100 else guild_name
        if (
            (current == "" or current.lower() in guild_name.lower())
            and guild_id[0] != context.guild.id
            and len(guild_names) < 25
        ):
            guild_names.append(Choice(name=guild_name, value=str(guild_id[0])))
    return guild_names


async def playlist_autocompletion(self, context, current):
    strings = self.guilds[str(context.guild.id)]["strings"]
    playlists = []
    if VARIABLES["storage"] == "yaml":
        for guild in self.data["guilds"]:
            if guild["id"] == (
                context.guild.id
                if context.namespace.from_guild is None
                else int(context.namespace.from_guild)
            ):
                for index, playlist in enumerate(guild["playlists"], 1):
                    polished_playlist_name = polished_message(
                        strings["playlist"],
                        {"playlist": playlist["name"], "playlist_index": index},
                    )
                    playlist["name"] = (
                        playlist["name"][
                            : 97 - len(polished_playlist_name) + len(playlist["name"])
                        ]
                        + "..."
                        if len(polished_playlist_name) > 100
                        else playlist["name"]
                    )
                    if (
                        current == ""
                        or current.lower() in polished_playlist_name.lower()
                    ) and len(playlists) < 25:
                        playlists.append(
                            Choice(name=polished_playlist_name, value=index)
                        )
                break
    else:
        for index, playlist in enumerate(
            list(
                await self.cursor.execute_fetchall(
                    "select pl_name from playlists where guild_id = ? order by guild_pl_id",
                    (
                        (
                            context.guild.id
                            if context.namespace.from_guild is None
                            else int(context.namespace.from_guild)
                        ),
                    ),
                )
            ),
            1,
        ):
            playlist_name = list(playlist)
            polished_playlist_name = polished_message(
                strings["playlist"],
                {"playlist": playlist_name[0], "playlist_index": index},
            )
            playlist_name[0] = (
                playlist_name[0][
                    : 97 - len(polished_playlist_name) + len(playlist_name[0])
                ]
                + "..."
                if len(polished_playlist_name) > 100
                else playlist_name[0]
            )
            if (
                current == "" or current.lower() in polished_playlist_name.lower()
            ) and len(playlists) < 25:
                playlists.append(Choice(name=polished_playlist_name, value=index))
    return playlists


async def playlist_song_autocompletion(self, context, current):
    strings = self.guilds[str(context.guild.id)]["strings"]
    songs = []
    if VARIABLES["storage"] == "yaml":
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                try:
                    for index, song in enumerate(
                        guild["playlists"][context.namespace.select - 1]["songs"], 1
                    ):
                        polished_song_name = polished_message(
                            strings["song"], {"song": song["name"], "index": index}
                        )
                        song["name"] = (
                            song["name"][
                                : 97 - len(polished_song_name) + len(song["name"])
                            ]
                            + "..."
                            if len(polished_song_name) > 100
                            else song["name"]
                        )
                        if (
                            current == ""
                            or current.lower() in polished_song_name.lower()
                        ) and len(songs) < 25:
                            songs.append(Choice(name=polished_song_name, value=index))
                except:
                    pass
                break
    else:
        try:
            for index, song in enumerate(
                list(
                    await self.cursor.execute_fetchall(
                        """
                        select song_name from pl_songs
                        left outer join playlists on playlists.pl_id = pl_songs.pl_id
                        where guild_id = ? and guild_pl_id = ?
                        order by pl_song_id
                        """,
                        (context.guild.id, context.namespace.select - 1),
                    )
                ),
                1,
            ):
                song_name = list(song)
                polished_song_name = polished_message(
                    strings["song"], {"song": song_name[0], "index": index}
                )
                song_name[0] = (
                    song_name[0][: 97 - len(polished_song_name) + len(song_name[0])]
                    + "..."
                    if len(polished_song_name) > 100
                    else song_name[0]
                )
                if (
                    current == "" or current.lower() in polished_song_name.lower()
                ) and len(songs) < 25:
                    songs.append(Choice(name=polished_song_name, value=index))
        except:
            pass
    return songs


async def playlist_add_files(self, context, message_regarded):
    await context.response.defer()
    guild = self.guilds[str(context.guild.id)]
    strings = guild["strings"]
    # show a dropdown menu of all the playlists for the calling guild
    playlist_options = [SelectOption(label=strings["cancel_option"])]
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                for index, playlist in enumerate(guild_searched["playlists"], 1):
                    playlist_options.append(
                        SelectOption(
                            label=polished_message(
                                strings["playlist"],
                                {
                                    "playlist": playlist["name"],
                                    "playlist_index": index,
                                },
                            ),
                            value=str(index),
                        )
                    )
                break
    else:
        for index, playlist in enumerate(
            await self.cursor.execute_fetchall(
                "select pl_name from playlists where guild_id = ? order by guild_pl_id",
                (context.guild.id,),
            ),
            1,
        ):
            playlist_options.append(
                SelectOption(
                    label=polished_message(
                        strings["playlist"],
                        {"playlist": playlist[0], "playlist_index": index},
                    ),
                    value=str(index),
                )
            )
    playlist_menu = Select(
        placeholder=strings["playlist_select_menu_placeholder"],
        options=playlist_options,
    )
    chosen = []

    async def playlist_callback(context):
        await context.response.send_message("...", ephemeral=True)
        await context.delete_original_response()
        chosen.append(playlist_menu.values[0])

    playlist_menu.callback = playlist_callback
    view = View()
    view.add_item(playlist_menu)
    await context.followup.delete_message(
        (await context.followup.send("...", silent=True)).id
    )
    await context.followup.send("", view=view, ephemeral=True)
    while not chosen:
        await sleep(0.1)
    if chosen[0] == strings["cancel_option"]:
        return
    index = int(chosen[0])

    playlist = []
    urls = []
    for url in message_regarded.attachments:
        response = requests.get(str(url), stream=True)
        try:
            metadata = self.get_metadata(BytesIO(response.content), str(url))
        except:
            await context.followup.send(
                polished_message(strings["invalid_url"], {"url": str(url)}),
                ephemeral=True,
            )
            return
        # verify that the URL file is a media container
        if not any(
            content_type in response.headers.get("Content-Type", "")
            for content_type in ["audio", "video"]
        ):
            await context.followup.send(
                polished_message(
                    strings["invalid_song"],
                    {"song": polished_url(str(url), metadata["name"])},
                ),
                ephemeral=True,
            )
            return

        urls.append(str(url))
        playlist.append(
            {
                "id": get_next_song_id(self.data),
                "name": metadata["name"],
                "file": None,
                "duration": metadata["duration"],
                "guild_id": message_regarded.guild.id,
                "channel_id": message_regarded.channel.id,
                "message_id": message_regarded.id,
                "attachment_index": message_regarded.attachments.index(url),
            }
        )
    await self.lock.acquire()
    if VARIABLES["storage"] == "yaml":
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                message = ""
                for song in playlist:
                    guild_searched["playlists"][index - 1]["songs"].append(song)
                    previous_message = message
                    new_message = polished_message(
                        strings["playlist_add_song"] + "\n",
                        {
                            "playlist": guild_searched["playlists"][index - 1]["name"],
                            "playlist_index": index,
                            "song": polished_url(
                                urls[playlist.index(song)], song["name"]
                            ),
                            "index": len(
                                guild_searched["playlists"][index - 1]["songs"]
                            ),
                        },
                    )
                    message += new_message
                    if len(message) > 2000:
                        await context.followup.send(previous_message)
                        message = new_message
                await context.followup.send(message)
                break
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        message = ""
        for song in playlist:
            try:
                await self.cursor.execute(
                    """
                    insert into songs values(
                        (select * from (select max(song_id) from songs) as max_song_id) + 1,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?
                    )
                    """,
                    (
                        song["name"],
                        song["duration"],
                        song["guild_id"],
                        song["channel_id"],
                        song["message_id"],
                        song["attachment_index"],
                    ),
                )
            except:
                await self.cursor.execute(
                    "insert into songs values(0, ?, ?, ?, ?, ?, ?)",
                    (
                        song["name"],
                        song["duration"],
                        song["guild_id"],
                        song["channel_id"],
                        song["message_id"],
                        song["attachment_index"],
                    ),
                )
            await self.cursor.execute(
                """
                insert into pl_songs values(
                    (select max(song_id) from songs),
                    ?,
                    ?,
                    (select pl_id from playlists where guild_id = ? and guild_pl_id = ?),
                    (
                        select * from (
                            select count(song_id) from pl_songs
                            left outer join playlists on playlists.pl_id = pl_songs.pl_id
                            where guild_id = ? and guild_pl_id = ?
                        ) as count_song_id
                    )
                )
                """,
                (
                    song["name"],
                    song["file"],
                    context.guild.id,
                    index - 1,
                    context.guild.id,
                    index - 1,
                ),
            )
            previous_message = message
            new_message = polished_message(
                strings["playlist_add_song"] + "\n",
                {
                    "playlist": (
                        await self.cursor.execute_fetchone(
                            "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                            (context.guild.id, index - 1),
                        )
                    )[0],
                    "playlist_index": index,
                    "song": polished_url(urls[playlist.index(song)], song["name"]),
                    "index": (
                        await self.cursor.execute_fetchone(
                            """
                            select count(song_id) from pl_songs
                            left outer join playlists on playlists.pl_id = pl_songs.pl_id
                            where guild_id = ? and guild_pl_id = ?
                            """,
                            (context.guild.id, index - 1),
                        )
                    )[0],
                },
            )
            message += new_message
            if len(message) > 2000:
                await context.followup.send(previous_message)
                message = new_message
        if message:
            await context.followup.send(message)
        await self.connection.commit()
    self.lock.release()


async def renew_attachment(self, guild_id, channel_id, url, song_id):
    if VARIABLES["storage"] == "yaml":
        for guild in self.data["guilds"]:
            if guild["id"] == guild_id:
                try:
                    working_thread_id = guild["working_thread_id"]
                except:
                    working_thread_id = channel_id
                await self.bot.get_guild(guild_id).get_thread(working_thread_id).send(
                    dump({"song_id": song_id}),
                    file=File(BytesIO(requests.get(url).content), get_filename(url)),
                )
                break
    else:
        try:
            working_thread_id = (
                await self.cursor.execute_fetchone(
                    "select working_thread_id from guilds_music where guild_id = ?",
                    (guild_id,),
                )
            )[0]
        except:
            working_thread_id = channel_id
        await self.bot.get_guild(guild_id).get_thread(working_thread_id).send(
            dump({"song_id": song_id}),
            file=File(BytesIO(requests.get(url).content), get_filename(url)),
        )


async def renew_attachment_from_message(self, message):
    if message.author.id == self.bot.user.id:
        await self.lock.acquire()
        try:
            content = load(message.content)
            if VARIABLES["storage"] == "yaml" and str(content["song_id"]):
                for guild in self.data["guilds"]:
                    for playlist in guild["playlists"]:
                        for song in playlist["songs"]:
                            if song["id"] == content["song_id"]:
                                song["channel_id"] = message.channel.id
                                song["message_id"] = message.id
                                song["file"] = None
                dump(self.data, open(self.flat_file, "w"), indent=4)
            elif str(content["song_id"]):
                await self.cursor.execute(
                    "update songs set channel_id = ? where song_id = ?",
                    (message.channel.id, content["song_id"]),
                )
                await self.cursor.execute(
                    "update songs set message_id = ? where song_id = ?",
                    (message.id, content["song_id"]),
                )
                await self.connection.commit()
        except:
            pass
        self.lock.release()


async def working_thread_command(self, context, set):
    await self.lock.acquire()
    strings = self.guilds[str(context.guild.id)]["strings"]
    if VARIABLES["storage"] == "yaml":
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                if set is None:
                    try:
                        await context.response.send_message(
                            polished_message(
                                strings["working_thread"],
                                {
                                    "bot": self.bot.user.mention,
                                    "thread": self.bot.get_guild(guild["id"])
                                    .get_thread(guild["working_thread_id"])
                                    .jump_url,
                                },
                            ),
                            ephemeral=True,
                        )
                    except:
                        await context.response.send_message(
                            polished_message(
                                strings["working_thread_not_assigned"],
                                {"bot": self.bot.user.mention},
                            ),
                            ephemeral=True,
                        )
                    break
                thread_nonexistent = True
                for thread in context.guild.threads:
                    if set == thread.name:
                        guild["working_thread_id"] = thread.id
                        dump(self.data, open(self.flat_file, "w"), indent=4)
                        await context.response.send_message(
                            polished_message(
                                strings["working_thread_change"],
                                {
                                    "bot": self.bot.user.mention,
                                    "thread": thread.jump_url,
                                },
                            )
                        )
                        thread_nonexistent = False
                        break
                if thread_nonexistent:
                    await context.response.send_message(strings["invalid_command"])
                break
    else:
        if set is None:
            try:
                await context.response.send_message(
                    polished_message(
                        strings["working_thread"],
                        {
                            "bot": self.bot.user.mention,
                            "thread": self.bot.get_guild(context.guild.id)
                            .get_thread(
                                working_thread_id=(
                                    await self.cursor.execute_fetchone(
                                        "select working_thread_id from guilds_music where guild_id = ?",
                                        (context.guild.id,),
                                    )
                                )[0]
                            )
                            .jump_url,
                        },
                    ),
                    ephemeral=True,
                )
            except:
                await context.response.send_message(
                    polished_message(
                        strings["working_thread_not_assigned"],
                        {"bot": self.bot.user.mention},
                    )
                )
            self.lock.release()
            return
        thread_nonexistent = True
        for thread in context.guild.threads:
            if set == thread.name:
                await self.cursor.execute(
                    "update guilds_music set working_thread_id = ? where guild_id = ?",
                    (thread.id, context.guild.id),
                )
                await self.connection.commit()
                await context.response.send_message(
                    polished_message(
                        strings["working_thread_change"],
                        {"bot": self.bot.user.mention, "thread": thread.jump_url},
                    )
                )
                thread_nonexistent = False
                break
        if thread_nonexistent:
            await context.response.send_message(strings["invalid_command"])
    self.lock.release()


async def working_thread_autocompletion(context, current):
    threads = []
    for thread in context.guild.threads:
        if (current == "" or current.lower() in thread.name.lower()) and len(
            threads
        ) < 25:
            threads.append(Choice(name=thread.name, value=thread.name))
    return threads
