from asyncio import sleep
from datetime import datetime
from io import BytesIO
import requests
from yaml import safe_dump as dump, safe_load as load
from discord import File, SelectOption
from discord.app_commands import Choice
from discord.ui import Select, View
from utils import get_file_name, page_selector, polished_message, polished_url


# return a list of playlists for the calling guild
async def playlists_command(self, context):
    await context.response.defer(ephemeral=True)
    guild = self.guilds[str(context.guild.id)]
    if self.cursor is None:
        playlists = []
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild_index = self.data["guilds"].index(guild_searched)
                break
    else:
        await self.lock.acquire()
        await self.cursor.execute(
            "select pl_name from playlists where guild_id = ? order by guild_pl_id",
            (context.guild.id,),
        )
        playlists = await self.cursor.fetchall()
        self.lock.release()
    message = guild["strings"]["playlists_header"] + "\n"
    if not (
        playlists
        or (self.cursor is None and self.data["guilds"][guild_index]["playlists"])
    ):
        await context.followup.send(guild["strings"]["no_playlists"])
        return
    pages = []
    index = 0
    while index < len(
        self.data["guilds"][guild_index]["playlists"]
        if self.cursor is None
        else playlists
    ):
        previous_message = message
        new_message = await polished_message(
            guild["strings"]["playlist"] + "\n",
            {
                "playlist": (
                    self.data["guilds"][guild_index]["playlists"][index]["name"]
                    if self.cursor is None
                    else playlists[index][0]
                ),
                "playlist_index": index + 1,
            },
        )
        message += new_message
        if len(message) > 2000:
            pages.append(previous_message)
            message = guild["strings"]["playlists_header"] + "\n" + new_message
        index += 1
    pages.append(message)
    await page_selector(context, guild["strings"], pages, 0)


async def playlist_command(
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
    select,
    action,
    file,
    song_url,
    song_index,
    new_name,
    new_index,
):
    async def declare_command_invalid():
        await context.followup.delete_message(
            (await context.followup.send("...", silent=True)).id
        )
        await context.followup.send(strings["invalid_command"], ephemeral=True)
        self.lock.release()

    await context.response.defer()
    strings = self.guilds[str(context.guild.id)]["strings"]
    if select is not None and action == "add":
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
            metadata = await self.get_metadata(BytesIO(response.content), url)
        except:
            await context.followup.delete_message(
                (await context.followup.send("...", silent=True)).id
            )
            await context.followup.send(
                await polished_message(strings["invalid_url"], {"url": url}),
                ephemeral=True,
            )
            return
        # verify that the URL file is a media container
        if "audio" not in response.headers.get(
            "Content-Type", ""
        ) and "video" not in response.headers.get("Content-Type", ""):
            await context.followup.delete_message(
                (await context.followup.send("...", silent=True)).id
            )
            await context.followup.send(
                await polished_message(
                    strings["invalid_song"],
                    {"song": await polished_url(url, metadata["name"])},
                ),
                ephemeral=True,
            )
            return
    await self.lock.acquire()
    if self.cursor is None:
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                guild = guild_searched
                break
        playlist_count = len(guild["playlists"])
        song_duration_entry = "duration"
        song_name_entry = "name"
        guild_id_entry = "guild_id"
        channel_id_entry = "channel_id"
        message_id_entry = "message_id"
        attachment_index_entry = "attachment_index"
        song_url_entry = "file"
    else:
        get_songs_statement = """
            select pl_songs.song_id, pl_songs.song_name, songs.guild_id, channel_id, message_id, attachment_index, song_url from pl_songs
            left outer join songs on songs.song_id = pl_songs.song_id
            left outer join playlists on playlists.pl_id = pl_songs.pl_id
            where playlists.guild_id = ? and guild_pl_id = ?
        """
        await self.cursor.execute(
            "select count(pl_id) from playlists where guild_id = ?",
            (context.guild.id,),
        )
        playlist_count = (await self.cursor.fetchone())[0]
        song_duration_entry = 0
        song_name_entry = 1
        guild_id_entry = 2
        channel_id_entry = 3
        message_id_entry = 4
        attachment_index_entry = 5
        song_url_entry = 6
    # import a playlist
    if from_guild is not None:
        if self.cursor is None:
            for guild_searched in self.data["guilds"]:
                if guild_searched["id"] == int(from_guild):
                    from_guild_playlists = guild_searched["playlists"]
                    from_guild_playlist_count = len(from_guild_playlists)
                    break
        else:
            await self.cursor.execute(
                "select count(pl_id) from playlists where guild_id = ?",
                (int(from_guild),),
            )
            from_guild_playlist_count = (await self.cursor.fetchone())[0]
        if transfer is None or transfer < 1 or transfer > from_guild_playlist_count:
            await declare_command_invalid()
            return
        if self.cursor is not None:
            await self.cursor.execute(
                """
                select song_id, song_name, song_url from pl_songs
                left outer join playlists on playlists.pl_id = pl_songs.pl_id
                where guild_id = ? and guild_pl_id = ?
                order by pl_song_id
                """,
                (int(from_guild), transfer - 1),
            )
            songs = await self.cursor.fetchall()
        if new_name is None:
            if self.cursor is None:
                new_name = from_guild_playlists[transfer - 1]["name"]
            else:
                await self.cursor.execute(
                    "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                    (int(from_guild), transfer - 1),
                )
                new_name = (await self.cursor.fetchone())[0]
        if new_index is None:
            new_index = (playlist_count + 1) if self.cursor is None else None
        elif new_index < 1 or new_index > playlist_count + 1:
            await declare_command_invalid()
            return
        if self.cursor is None:
            guild["playlists"].insert(
                new_index - 1,
                {
                    "name": new_name,
                    "songs": from_guild_playlists[transfer - 1]["songs"].copy(),
                },
            )
        else:
            await self.cursor.execute(
                """
                insert into playlists values(
                    (select max(pl_id) from playlists) + 1,
                    ?,
                    ?,
                    (select count(pl_id) from playlists where guild_id = ?)
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
                            select count(song_id) from pl_songs
                            where pl_id = (select max(pl_id) from playlists)
                        )
                    )
                    """,
                    (song[0], song[1], song[2]),
                )
            if new_index is None:
                new_index = playlist_count + 1
            else:
                await self.cursor.execute(
                    "update playlists set guild_pl_id = guild_pl_id + 1 where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?",
                    (new_index - 1, playlist_count, context.guild.id),
                )
                await self.cursor.execute(
                    "update playlists set guild_pl_id = ? where pl_id = (select max(pl_id) from playlists)",
                    (new_index - 1,),
                )
            await self.cursor.execute(
                "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                (int(from_guild), transfer - 1),
            )
        await context.followup.send(
            await polished_message(
                strings["clone_playlist"],
                {
                    "playlist": (
                        from_guild_playlists[transfer - 1]["name"]
                        if self.cursor is None
                        else (await self.cursor.fetchone())[0]
                    ),
                    "playlist_index": transfer,
                    "into_playlist": new_name,
                    "into_playlist_index": new_index,
                },
            )
        )
    # add a playlist
    elif add is not None:
        if new_index is None:
            new_index = (playlist_count + 1) if self.cursor is None else None
        elif new_index < 1 or new_index > playlist_count + 1:
            await declare_command_invalid()
            return
        if self.cursor is None:
            guild["playlists"].insert(new_index - 1, {"name": add, "songs": []})
        else:
            try:
                await self.cursor.execute(
                    """
                    insert into playlists values(
                        (select max(pl_id) from playlists) + 1,
                        ?,
                        ?,
                        (select count(pl_id) from playlists where guild_id = ?)
                    )
                    """,
                    (add, context.guild.id, context.guild.id),
                )
            except:
                await self.cursor.execute(
                    """
                    insert into playlists values(
                        0,
                        ?,
                        ?,
                        (select count(pl_id) from playlists where guild_id = ?)
                    )
                    """,
                    (add, context.guild.id, context.guild.id),
                )
            if new_index is None:
                new_index = playlist_count + 1
            else:
                await self.cursor.execute(
                    "update playlists set guild_pl_id = guild_pl_id + 1 where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?",
                    (new_index - 1, playlist_count, context.guild.id),
                )
                await self.cursor.execute(
                    "update playlists set guild_pl_id = ? where pl_id = (select max(pl_id) from playlists)",
                    (new_index - 1,),
                )
        await context.followup.send(
            await polished_message(
                strings["add_playlist"],
                {"playlist": add, "playlist_index": new_index},
            )
        )
    # clone a playlist or copy its tracks into another playlist
    elif clone is not None and 0 < clone <= playlist_count:
        # clone a playlist
        if self.cursor is not None:
            await self.cursor.execute(
                """
                select song_id, song_name, song_url from pl_songs
                left outer join playlists on playlists.pl_id = pl_songs.pl_id
                where guild_id = ? and guild_pl_id = ?
                order by pl_song_id
                """,
                (context.guild.id, clone - 1),
            )
            songs = await self.cursor.fetchall()
        if into is None or into < 1 or into > playlist_count:
            if self.cursor is None:
                playlist = guild["playlists"][clone - 1]["name"]
            else:
                await self.cursor.execute(
                    "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                    (context.guild.id, clone - 1),
                )
                playlist = (await self.cursor.fetchone())[0]
            if new_name is None:
                new_name = playlist
            if new_index is None:
                new_index = (playlist_count + 1) if self.cursor is None else None
            elif new_index < 1 or new_index > playlist_count + 1:
                await declare_command_invalid()
                return
            if self.cursor is None:
                guild["playlists"].insert(
                    new_index - 1,
                    {
                        "name": new_name,
                        "songs": guild["playlists"][clone - 1]["songs"].copy(),
                    },
                )
            else:
                await self.cursor.execute(
                    """
                    insert into playlists values(
                        (select max(pl_id) from playlists) + 1,
                        ?,
                        ?,
                        (select count(pl_id) from playlists where guild_id = ?)
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
                                select count(song_id) from pl_songs
                                where pl_id = (select max(pl_id) from playlists)
                            )
                        )
                        """,
                        (song[0], song[1], song[2]),
                    )
                if new_index is None:
                    new_index = playlist_count + 1
                else:
                    await self.cursor.execute(
                        "update playlists set guild_pl_id = guild_pl_id + 1 where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?",
                        (new_index - 1, playlist_count, context.guild.id),
                    )
                    await self.cursor.execute(
                        "update playlists set guild_pl_id = ? where pl_id = (select max(pl_id) from playlists)",
                        (new_index - 1,),
                    )
            await context.followup.send(
                await polished_message(
                    strings["clone_playlist"],
                    {
                        "playlist": playlist,
                        "playlist_index": clone,
                        "into_playlist": new_name,
                        "into_playlist_index": new_index,
                    },
                )
            )
        # copy a playlist's tracks into another playlist
        else:
            if self.cursor is None:
                guild["playlists"][into - 1]["songs"] += guild["playlists"][clone - 1][
                    "songs"
                ]
                playlist = guild["playlists"][clone - 1]["name"]
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
                                select count(song_id) from pl_songs
                                left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                where guild_id = ? and guild_pl_id = ?
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
                await self.cursor.execute(
                    "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                    (context.guild.id, clone - 1),
                )
                playlist = (await self.cursor.fetchone())[0]
                await self.cursor.execute(
                    "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                    (context.guild.id, into - 1),
                )
                into_playlist = (await self.cursor.fetchone())[0]
            await context.followup.send(
                await polished_message(
                    strings["clone_playlist"],
                    {
                        "playlist": playlist,
                        "playlist_index": clone,
                        "into_playlist": into_playlist,
                        "into_playlist_index": into,
                    },
                )
            )
    # change a playlist's position in the order of playlists
    elif move is not None and 0 < move <= playlist_count:
        if new_index is None or new_index < 1 or new_index > playlist_count:
            await declare_command_invalid()
            return
        if self.cursor is None:
            playlist_copies = guild["playlists"].copy()
            guild["playlists"].remove(playlist_copies[move - 1])
            guild["playlists"].insert(new_index - 1, playlist_copies[move - 1])
        else:
            await self.cursor.execute(
                "select pl_id, pl_name from playlists where guild_id = ? order by guild_pl_id",
                (context.guild.id,),
            )
            playlist_copies = await self.cursor.fetchall()
            if new_index > move:
                await self.cursor.execute(
                    "update playlists set guild_pl_id = guild_pl_id - 1 where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?",
                    (move - 1, new_index - 1, context.guild.id),
                )
            elif new_index < move:
                await self.cursor.execute(
                    "update playlists set guild_pl_id = guild_pl_id + 1 where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?",
                    (new_index - 1, move - 1, context.guild.id),
                )
            await self.cursor.execute(
                "update playlists set guild_pl_id = ? where pl_id = ?",
                (new_index - 1, playlist_copies[move - 1][0]),
            )
        await context.followup.send(
            await polished_message(
                strings["move_playlist"],
                {
                    "playlist": playlist_copies[move - 1][song_name_entry],
                    "playlist_index": new_index,
                },
            )
        )
    # rename a playlist
    elif rename is not None and 0 < rename <= playlist_count:
        if new_name is None:
            await declare_command_invalid()
            return
        if self.cursor is None:
            await context.followup.send(
                await polished_message(
                    strings["rename_playlist"],
                    {
                        "playlist": guild["playlists"][rename - 1]["name"],
                        "playlist_index": rename,
                        "name": new_name,
                    },
                )
            )
            guild["playlists"][rename - 1]["name"] = new_name
        else:
            await self.cursor.execute(
                "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                (context.guild.id, rename - 1),
            )
            await context.followup.send(
                await polished_message(
                    strings["rename_playlist"],
                    {
                        "playlist": (await self.cursor.fetchone())[0],
                        "playlist_index": rename,
                        "name": new_name,
                    },
                )
            )
            await self.cursor.execute(
                "update playlists set pl_name = ? where guild_id = ? and guild_pl_id = ?",
                (new_name, context.guild.id, rename - 1),
            )
    # remove a playlist
    elif remove is not None and 0 < remove <= playlist_count:
        if self.cursor is None:
            await context.followup.send(
                await polished_message(
                    strings["remove_playlist"],
                    {
                        "playlist": guild["playlists"][remove - 1]["name"],
                        "playlist_index": remove,
                    },
                )
            )
            guild["playlists"].remove(guild["playlists"][remove - 1])
        else:
            await self.cursor.execute(
                "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                (context.guild.id, remove - 1),
            )
            await context.followup.send(
                await polished_message(
                    strings["remove_playlist"],
                    {
                        "playlist": (await self.cursor.fetchone())[0],
                        "playlist_index": remove,
                    },
                )
            )
            await self.cursor.execute(
                "delete from pl_songs where pl_id = (select pl_id from playlists where guild_id = ? and guild_pl_id = ?)",
                (context.guild.id, remove - 1),
            )
            await self.cursor.execute(
                "delete from songs where song_id not in (select song_id from pl_songs)"
            )
            await self.cursor.execute(
                "delete from playlists where guild_id = ? and guild_pl_id = ?",
                (context.guild.id, remove - 1),
            )
            await self.cursor.execute(
                "update playlists set guild_pl_id = guild_pl_id - 1 where guild_pl_id >= ? and guild_id = ?",
                (remove - 1, context.guild.id),
            )
    # load a playlist
    elif load is not None and 0 < load <= playlist_count:
        if self.cursor is None:
            songs = guild["playlists"][load - 1]["songs"]
        else:
            await self.cursor.execute(
                f"{get_songs_statement} order by pl_song_id".replace(
                    "pl_songs.song_id,", "song_duration,"
                ),
                (context.guild.id, load - 1),
            )
            songs = await self.cursor.fetchall()
        self.lock.release()
        if songs:
            proper_songs = []
            for song in songs:
                if song[song_url_entry] is None:
                    try:
                        song_message = self.messages[str(song[message_id_entry])]
                        if (
                            int(datetime.timestamp(datetime.now()))
                            > song_message["expiration"]
                        ):
                            raise Exception
                    except:
                        song_message = {
                            "message": await self.bot.get_guild(song[guild_id_entry])
                            .get_channel_or_thread(song[channel_id_entry])
                            .fetch_message(song[message_id_entry]),
                            "expiration": int(datetime.timestamp(datetime.now()))
                            + 1209600,
                        }
                        self.messages[str(song[message_id_entry])] = song_message
                    song_file = str(
                        song_message["message"].attachments[
                            song[attachment_index_entry]
                        ]
                    )
                else:
                    song_file = song[song_url_entry]
                proper_songs.append(
                    {
                        "name": song[song_name_entry],
                        "file": song_file,
                        "duration": song[song_duration_entry],
                    }
                )
            if self.cursor is None:
                await context.followup.send(
                    await polished_message(
                        strings["load_playlist"],
                        {
                            "playlist": guild["playlists"][load - 1]["name"],
                            "playlist_index": load,
                        },
                    )
                )
            else:
                await self.lock.acquire()
                await self.cursor.execute(
                    "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                    (context.guild.id, load - 1),
                )
                try:
                    if context.user.voice.channel is not None:
                        await context.followup.send(
                            await polished_message(
                                strings["load_playlist"],
                                {
                                    "playlist": (await self.cursor.fetchone())[0],
                                    "playlist_index": load,
                                },
                            )
                        )
                except:
                    pass
                self.lock.release()
            await self.play_song(context, playlist=proper_songs)
        else:
            await context.followup.delete_message(
                (await context.followup.send("...", silent=True)).id
            )
            if self.cursor is not None:
                await self.cursor.execute(
                    "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                    (context.guild.id, load - 1),
                )
            await context.followup.send(
                await polished_message(
                    strings["playlist_no_songs"],
                    {
                        "playlist": (
                            guild["playlists"][load - 1]["name"]
                            if self.cursor is None
                            else (await self.cursor.fetchone())[0]
                        ),
                        "playlist_index": load,
                    },
                ),
                ephemeral=True,
            )
        return
    # select a playlist to modify or show the contents of
    elif select is not None and action is not None:
        if 0 < select <= playlist_count:
            if self.cursor is None:
                playlist = guild["playlists"][select - 1]["name"]
                song_count = len(guild["playlists"][select - 1]["songs"])
            else:
                await self.cursor.execute(
                    """
                    select pl_songs.pl_id, pl_name, count(song_id) from pl_songs
                    right outer join playlists on playlists.pl_id = pl_songs.pl_id
                    where guild_id = ? and guild_pl_id = ?
                    group by pl_songs.pl_id, pl_name
                    """,
                    (context.guild.id, select - 1),
                )
                global_playlist_id, playlist, song_count = await self.cursor.fetchone()
            # add a track to the playlist
            if action == "add":
                if new_name is None:
                    new_name = metadata["name"]
                if new_index is None:
                    new_index = (song_count + 1) if self.cursor is None else None
                elif new_index < 1 or new_index > song_count + 1:
                    await declare_command_invalid()
                    return
                if self.cursor is None:
                    song = {
                        "name": new_name,
                        "index": new_index,
                        "duration": metadata["duration"],
                    }
                    guild["playlists"][select - 1]["songs"].insert(
                        song["index"] - 1,
                        {
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
                            "insert into songs values((select max(song_id) from songs) + 1, ?, ?, ?, ?, ?, ?)",
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
                                select count(song_id) from pl_songs
                                left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                where guild_id = ? and guild_pl_id = ?
                            )
                        )
                        """,
                        (
                            new_name,
                            url if file is None else None,
                            context.guild.id,
                            select - 1,
                            context.guild.id,
                            select - 1,
                        ),
                    )
                    if new_index is None:
                        new_index = song_count + 1
                    else:
                        await self.cursor.execute(
                            "update pl_songs set pl_song_id = pl_song_id + 1 where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?",
                            (new_index - 1, song_count, global_playlist_id),
                        )
                        await self.cursor.execute(
                            "update pl_songs set pl_song_id = ? where song_id = (select max(song_id) from songs)",
                            (new_index - 1,),
                        )
                await context.followup.send(
                    await polished_message(
                        strings["playlist_add_song"],
                        {
                            "playlist": playlist,
                            "playlist_index": select,
                            "song": await polished_url(url, new_name),
                            "index": new_index,
                        },
                    )
                )
                if file is not None:
                    if self.cursor is not None:
                        await self.cursor.execute("select max(song_id) from songs")
                        song_id = (await self.cursor.fetchone())[0]
                    self.lock.release()
                    await self.renew_attachment(
                        context.guild.id, context.channel.id, url, song_id
                    )
                    return
            # change the position of a track within the playlist
            elif action == "move":
                if (
                    song_index is None
                    or song_index < 1
                    or song_index > song_count
                    or new_index is None
                    or new_index < 1
                    or new_index > song_count
                ):
                    await declare_command_invalid()
                    return
                if self.cursor is None:
                    song = guild["playlists"][select - 1]["songs"][song_index - 1]
                else:
                    await self.cursor.execute(
                        f"{get_songs_statement} order by pl_song_id",
                        (context.guild.id, select - 1),
                    )
                    song_copies = await self.cursor.fetchall()
                    if new_index > song_index:
                        await self.cursor.execute(
                            "update pl_songs set pl_song_id = pl_song_id - 1 where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?",
                            (song_index - 1, new_index - 1, global_playlist_id),
                        )
                    elif new_index < song_index:
                        await self.cursor.execute(
                            "update pl_songs set pl_song_id = pl_song_id + 1 where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?",
                            (new_index - 1, song_index - 1, global_playlist_id),
                        )
                    song = song_copies[song_index - 1]
                    await self.cursor.execute(
                        "update pl_songs set pl_song_id = ? where song_id = ?",
                        (new_index - 1, song[0]),
                    )
                if song[song_url_entry] is None:
                    song_file = str(
                        (
                            await self.bot.get_guild(song[guild_id_entry])
                            .get_channel_or_thread(song[channel_id_entry])
                            .fetch_message(song[message_id_entry])
                        ).attachments[song[attachment_index_entry]]
                    )
                else:
                    song_file = song[song_url_entry]
                if self.cursor is None:
                    guild["playlists"][select - 1]["songs"].remove(song)
                    guild["playlists"][select - 1]["songs"].insert(new_index - 1, song)
                await context.followup.send(
                    await polished_message(
                        strings["playlist_move_song"],
                        {
                            "playlist": playlist,
                            "playlist_index": select,
                            "song": await polished_url(
                                song_file, song[song_name_entry]
                            ),
                            "index": new_index,
                        },
                    )
                )
            # rename a track in the playlist
            elif action == "rename":
                if (
                    song_index is None
                    or song_index < 1
                    or song_index > song_count
                    or new_name is None
                ):
                    await declare_command_invalid()
                    return
                if self.cursor is None:
                    song = guild["playlists"][select - 1]["songs"][song_index - 1]
                else:
                    await self.cursor.execute(
                        f"{get_songs_statement} and pl_song_id = ?",
                        (context.guild.id, select - 1, song_index - 1),
                    )
                    (
                        song_id,
                        song_name,
                        guild_id,
                        channel_id,
                        message_id,
                        attachment_index,
                        song_file,
                    ) = await self.cursor.fetchone()
                if song_file is None:
                    song_file = str(
                        (
                            await self.bot.get_guild(guild_id)
                            .get_channel_or_thread(channel_id)
                            .fetch_message(message_id)
                        ).attachments[attachment_index]
                    )
                elif self.cursor is None:
                    song_file = song["file"]
                await context.followup.send(
                    await polished_message(
                        strings["playlist_rename_song"],
                        {
                            "playlist": playlist,
                            "playlist_index": select,
                            "song": await polished_url(
                                song_file,
                                song["name"] if self.cursor is None else song_name,
                            ),
                            "index": song_index,
                            "name": new_name,
                        },
                    )
                )
                if self.cursor is None:
                    song["name"] = new_name
                else:
                    await self.cursor.execute(
                        "update pl_songs set song_name = ? where song_id = ?",
                        (new_name, song_id),
                    )
            # remove a track from the playlist
            elif action == "remove":
                if song_index is None or song_index < 1 or song_index > song_count:
                    await declare_command_invalid()
                    return
                if self.cursor is None:
                    song = guild["playlists"][select - 1]["songs"][song_index - 1]
                else:
                    await self.cursor.execute(
                        f"{get_songs_statement} and pl_song_id = ?",
                        (context.guild.id, select - 1, song_index - 1),
                    )
                    (
                        song_id,
                        song_name,
                        guild_id,
                        channel_id,
                        message_id,
                        attachment_index,
                        song_file,
                    ) = await self.cursor.fetchone()
                if song_file is None:
                    song_file = str(
                        (
                            await self.bot.get_guild(guild_id)
                            .get_channel_or_thread(channel_id)
                            .fetch_message(message_id)
                        ).attachments[attachment_index]
                    )
                elif self.cursor is None:
                    song_file = song["file"]
                if self.cursor is None:
                    guild["playlists"][select - 1]["songs"].remove(song)
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
                    await polished_message(
                        strings["playlist_remove_song"],
                        {
                            "playlist": playlist,
                            "playlist_index": select,
                            "song": await polished_url(
                                song_file,
                                song["name"] if self.cursor is None else song_name,
                            ),
                            "index": song_index,
                        },
                    )
                )
            # return a list of tracks in the playlist
            elif action == "list":
                await context.followup.delete_message(
                    (await context.followup.send("...", silent=True)).id
                )
                message = await polished_message(
                    strings["playlist_songs_header"] + "\n",
                    {"playlist": playlist, "playlist_index": select},
                )
                if self.cursor is None:
                    songs = guild["playlists"][select - 1]["songs"]
                else:
                    await self.cursor.execute(
                        f"{get_songs_statement} order by pl_song_id",
                        (context.guild.id, select - 1),
                    )
                    songs = await self.cursor.fetchall()
                self.lock.release()
                if not songs:
                    await context.followup.send(
                        await polished_message(
                            strings["playlist_no_songs"],
                            {"playlist": playlist, "playlist_index": select},
                        ),
                        ephemeral=True,
                    )
                    return
                pages = []
                index = 0
                for song in songs:
                    previous_message = message
                    if song[song_url_entry] is None:
                        try:
                            song_message = self.messages[str(song[message_id])]
                            if (
                                int(datetime.timestamp(datetime.now()))
                                > song_message["expiration"]
                            ):
                                raise Exception
                        except:
                            song_message = {
                                "message": await self.bot.get_guild(
                                    song[guild_id_entry]
                                )
                                .get_channel_or_thread(song[channel_id_entry])
                                .fetch_message(song[message_id_entry]),
                                "expiration": int(datetime.timestamp(datetime.now()))
                                + 1209600,
                            }
                            self.messages[str(song[message_id_entry])] = song_message
                        song_file = str(
                            song_message["message"].attachments[
                                song[attachment_index_entry]
                            ]
                        )
                    else:
                        song_file = song[song_url_entry]
                    new_message = await polished_message(
                        strings["song"] + "\n",
                        {
                            "song": await polished_url(
                                song_file, song[song_name_entry]
                            ),
                            "index": index + 1,
                        },
                    )
                    message += new_message
                    if len(message) > 2000:
                        pages.append(previous_message)
                        message = "".join(
                            [
                                await polished_message(
                                    strings["playlist_songs_header"] + "\n",
                                    {
                                        "playlist": playlist,
                                        "playlist_index": select,
                                    },
                                ),
                                new_message,
                            ]
                        )
                    index += 1
                pages.append(message)
                await page_selector(context, strings, pages, 0)
                return
            else:
                await declare_command_invalid()
                return
        else:
            await context.followup.delete_message(
                (await context.followup.send("...", silent=True)).id
            )
            await context.followup.send(
                await polished_message(
                    strings["invalid_playlist_number"], {"playlist_index": select}
                ),
                ephemeral=True,
            )
            self.lock.release()
            return
    else:
        await declare_command_invalid()
        return
    if self.cursor is None:
        dump(self.data, open(self.flat_file, "w"), indent=4)
    else:
        await self.connection.commit()
    self.lock.release()


async def playlist_guild_autocompletion(self, context, current):
    guild_names = []
    if self.cursor is None:
        guild_ids = []
        for guild in self.data["guilds"]:
            user_ids = []
            for user in guild["users"]:
                user_ids.append(user["id"])
            if context.user.id in user_ids:
                guild_ids.append([guild["id"]])
    else:
        await self.lock.acquire()
        await self.cursor.execute(
            "select guild_id from guild_users where user_id = ?", (context.user.id,)
        )
        guild_ids = await self.cursor.fetchall()
        self.lock.release()
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
    if self.cursor is None:
        for guild in self.data["guilds"]:
            if guild["id"] == (
                context.guild.id
                if context.namespace.from_guild is None
                else int(context.namespace.from_guild)
            ):
                index = 1
                for playlist in guild["playlists"]:
                    polished_playlist_name = await polished_message(
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
                    index += 1
                break
    else:
        await self.lock.acquire()
        await self.cursor.execute(
            "select pl_name from playlists where guild_id = ? order by guild_pl_id",
            (
                (
                    context.guild.id
                    if context.namespace.from_guild is None
                    else int(context.namespace.from_guild)
                ),
            ),
        )
        playlist_names = list(await self.cursor.fetchall())
        self.lock.release()
        index = 1
        for playlist in playlist_names:
            playlist_name = list(playlist)
            polished_playlist_name = await polished_message(
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
            index += 1
    return playlists


async def playlist_action_autocompletion(self, context, current):
    strings = self.guilds[str(context.guild.id)]["strings"]
    action_options = [
        Choice(name=strings["add"], value="add"),
        Choice(name=strings["move"], value="move"),
        Choice(name=strings["rename"], value="rename"),
        Choice(name=strings["remove"], value="remove"),
        Choice(name=strings["list"], value="list"),
    ]
    actions = []
    for action in action_options:
        if current == "" or current.lower() in action.name.lower():
            actions.append(action)
    return actions


async def playlist_song_autocompletion(self, context, current):
    strings = self.guilds[str(context.guild.id)]["strings"]
    songs = []
    if self.cursor is None:
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                try:
                    index = 1
                    for song in guild["playlists"][context.namespace.select - 1][
                        "songs"
                    ]:
                        polished_song_name = await polished_message(
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
                        index += 1
                except:
                    pass
                break
    else:
        try:
            await self.lock.acquire()
            await self.cursor.execute(
                """
                select song_name from pl_songs
                left outer join playlists on playlists.pl_id = pl_songs.pl_id
                where guild_id = ? and guild_pl_id = ?
                order by pl_song_id
                """,
                (context.guild.id, context.namespace.select - 1),
            )
            song_names = list(await self.cursor.fetchall())
            self.lock.release()
            index = 1
            for song in song_names:
                song_name = list(song)
                polished_song_name = await polished_message(
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
                index += 1
        except:
            pass
    return songs


async def playlist_add_files(self, context, message_regarded):
    await context.response.defer()
    guild = self.guilds[str(context.guild.id)]
    strings = guild["strings"]
    # show a dropdown menu of all the playlists for the calling guild
    playlist_options = [SelectOption(label=strings["cancel_option"])]
    index = 1
    if self.cursor is None:
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                for playlist in guild_searched["playlists"]:
                    playlist_options.append(
                        SelectOption(
                            label=await polished_message(
                                strings["playlist"],
                                {
                                    "playlist": playlist["name"],
                                    "playlist_index": index,
                                },
                            ),
                            value=str(index),
                        )
                    )
                    index += 1
                break
    else:
        await self.lock.acquire()
        await self.cursor.execute(
            "select pl_name from playlists where guild_id = ? order by guild_pl_id",
            (context.guild.id,),
        )
        playlists = await self.cursor.fetchall()
        self.lock.release()
        for playlist in playlists:
            playlist_options.append(
                SelectOption(
                    label=await polished_message(
                        strings["playlist"],
                        {"playlist": playlist[0], "playlist_index": index},
                    ),
                    value=str(index),
                )
            )
            index += 1
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
            metadata = await self.get_metadata(BytesIO(response.content), str(url))
        except:
            await context.followup.send(
                await polished_message(strings["invalid_url"], {"url": str(url)}),
                ephemeral=True,
            )
            return
        # verify that the URL file is a media container
        if "audio" not in response.headers.get(
            "Content-Type", ""
        ) and "video" not in response.headers.get("Content-Type", ""):
            await context.followup.send(
                await polished_message(
                    strings["invalid_song"],
                    {"song": await polished_url(str(url), metadata["name"])},
                ),
                ephemeral=True,
            )
            return

        urls.append(str(url))
        playlist.append(
            {
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
    if self.cursor is None:
        for guild_searched in self.data["guilds"]:
            if guild_searched["id"] == context.guild.id:
                message = ""
                for song in playlist:
                    guild_searched["playlists"][index - 1]["songs"].append(song)
                    previous_message = message
                    new_message = await polished_message(
                        strings["playlist_add_song"] + "\n",
                        {
                            "playlist": guild_searched["playlists"][index - 1]["name"],
                            "playlist_index": index,
                            "song": await polished_url(
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
                    "insert into songs values((select max(song_id) from songs) + 1, ?, ?, ?, ?, ?, ?)",
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
                        select count(song_id) from pl_songs
                        left outer join playlists on playlists.pl_id = pl_songs.pl_id
                        where guild_id = ? and guild_pl_id = ?
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
            await self.cursor.execute(
                "select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                (context.guild.id, index - 1),
            )
            playlist_name = (await self.cursor.fetchone())[0]
            await self.cursor.execute(
                """
                select count(song_id) from pl_songs
                left outer join playlists on playlists.pl_id = pl_songs.pl_id
                where guild_id = ? and guild_pl_id = ?
                """,
                (context.guild.id, index - 1),
            )
            song_index = (await self.cursor.fetchone())[0]
            new_message = await polished_message(
                strings["playlist_add_song"] + "\n",
                {
                    "playlist": playlist_name,
                    "playlist_index": index,
                    "song": await polished_url(
                        urls[playlist.index(song)], song["name"]
                    ),
                    "index": song_index,
                },
            )
            message += new_message
            if len(message) > 2000:
                await context.followup.send(previous_message)
                message = new_message
        await context.followup.send(message)
        await self.connection.commit()
    self.lock.release()


async def renew_attachment(self, guild_id, channel_id, url, song_id):
    if self.cursor is None:
        for guild in self.data["guilds"]:
            if guild["id"] == guild_id:
                try:
                    working_thread_id = guild["working_thread_id"]
                except:
                    working_thread_id = channel_id
                await self.bot.get_guild(guild_id).get_thread(working_thread_id).send(
                    dump({"song_url": url}),
                    file=File(
                        BytesIO(requests.get(url).content), await get_file_name(url)
                    ),
                )
                break
    else:
        await self.lock.acquire()
        await self.cursor.execute(
            "select working_thread_id from guilds_music where guild_id = ?", (guild_id,)
        )
        try:
            working_thread_id = (await self.cursor.fetchone())[0]
        except:
            working_thread_id = channel_id
        self.lock.release()
        await self.bot.get_guild(guild_id).get_thread(working_thread_id).send(
            dump({"song_id": song_id}),
            file=File(BytesIO(requests.get(url).content), await get_file_name(url)),
        )


async def renew_attachment_from_message(self, message):
    if message.author.id == self.bot.user.id:
        await self.lock.acquire()
        try:
            content = load(message.content)
            if self.cursor is None and str(content["song_url"]):
                for guild in self.data["guilds"]:
                    for playlist in guild["playlists"]:
                        for song in playlist["songs"]:
                            if song["file"] == content["song_url"]:
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
    if self.cursor is None:
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                if set is None:
                    try:
                        await context.response.send_message(
                            await polished_message(
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
                            await polished_message(
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
                            await polished_message(
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
            await self.cursor.execute(
                "select working_thread_id from guilds_music where guild_id = ?",
                (context.guild.id,),
            )
            working_thread_id = (await self.cursor.fetchone())[0]
            try:
                await context.response.send_message(
                    await polished_message(
                        strings["working_thread"],
                        {
                            "bot": self.bot.user.mention,
                            "thread": self.bot.get_guild(context.guild.id)
                            .get_thread(working_thread_id)
                            .jump_url,
                        },
                    ),
                    ephemeral=True,
                )
            except:
                await context.response.send_message(
                    await polished_message(
                        strings["working_thread_not_assigned"],
                        {"bot": self.bot.user.mention},
                    )
                )
        thread_nonexistent = True
        for thread in context.guild.threads:
            if set == thread.name:
                await self.cursor.execute(
                    "update guilds_music set working_thread_id = ? where guild_id = ?",
                    (thread.id, context.guild.id),
                )
                await self.connection.commit()
                await context.response.send_message(
                    await polished_message(
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
