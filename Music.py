import asyncio
import random
import typing
from io import BytesIO
import requests
import yaml
import discord
from discord import app_commands
from discord.ext import commands
from pymediainfo import MediaInfo

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.connection = bot.connection
        self.cursor = bot.cursor
        self.data = bot.data
        self.flat_file = bot.flat_file
        self.guilds = bot.guilds_
        self.language_directory = bot.language_directory
        self.lock = bot.lock
        self.messages = {}
        self.playlist_add_files_context_menu = app_commands.ContextMenu(name="playlist_add_files_context_menu", callback=self.playlist_add_files)
        bot.tree.add_command(self.playlist_add_files_context_menu)

    async def get_file_name(self, file):
        try: return file[file.rindex("/") + 1:file.rindex("?")]
        except: return file[file.rindex("/") + 1:]

    async def get_metadata(self, file, url):
        duration = .0
        for track in MediaInfo.parse(file).tracks:
            try:
                if track.to_data()["track_type"] == "General": name = track.to_data()["title"]
            except:
                try: name = track.to_data()["track_name"]
                except:
                    name = (await self.get_file_name(url)).replace("_", " ")
                    try: name = name[:name.rindex(".")]
                    except: pass
            try: duration = float(track.to_data()["duration"]) / 1000
            except: pass
        return {"name": name, "duration": duration}

    async def polished_song_name(self, file, name): return f"[{name}](<{file}>)"

    async def polished_message(self, message, replacements):
        for placeholder, replacement in replacements.items(): message = message.replace("%{" + placeholder + "}", str(replacement))
        return message

    async def convert_to_time(self, number):
        segments = []
        temp_number = number
        if temp_number >= 3600:
            segments.append(str(int(temp_number / 3600)))
            temp_number %= 3600
        else: segments.append("00")
        if temp_number >= 60:
            segments.append(str(int(temp_number / 60)))
            temp_number %= 60
        else: segments.append("00")
        segments.append(str(int(temp_number)))
        marker = ""
        index = 0
        for segment in segments:
            if len(segment) == 1: segment = "0" + segment
            marker += segment
            if index < len(segments) - 1: marker += ":"
            index += 1
        return marker

    async def convert_to_seconds(self, time):
        segments = []
        if ":" in time: segments = time.split(":")
        if len(segments) == 2: seconds = float(segments[0]) * 60 + float(segments[1])
        elif len(segments) == 3: seconds = float(segments[0]) * 3600 + float(segments[1]) * 60 + float(segments[2])
        else: seconds = float(time)
        return seconds

    async def page_selector(self, context, strings, pages, index, message=None):
        previous_button = discord.ui.Button(label="<", disabled=index == 0, style=discord.ButtonStyle.primary)
        page_input_button = discord.ui.Button(label=f"{str(index + 1)}/{len(pages)}", disabled=len(pages) == 1)
        next_button = discord.ui.Button(label=">", disabled=index == len(pages) - 1, style=discord.ButtonStyle.primary)
        async def previous_callback(context):
            await context.response.defer()
            await self.page_selector(context, strings, pages, index - 1, message)
        async def page_input_callback(context):
            page_input = discord.ui.TextInput(label=strings["page"])
            modal = discord.ui.Modal(title=strings["page_selector_title"])
            modal.add_item(page_input)
            async def submit(context):
                await context.response.defer()
                await self.page_selector(context,
                                         strings,
                                         pages,
                                         int(page_input.value) - 1 if 0 < int(page_input.value) <= len(pages) else index,
                                         message)
            modal.on_submit = submit
            await context.response.send_modal(modal)
        async def next_callback(context):
            await context.response.defer()
            await self.page_selector(context, strings, pages, index + 1, message)
        next_button.callback = next_callback
        page_input_button.callback = page_input_callback
        previous_button.callback = previous_callback
        view = discord.ui.View()
        view.add_item(previous_button)
        view.add_item(page_input_button)
        view.add_item(next_button)
        if message is None: message = await context.followup.send("...", ephemeral=True)
        await context.followup.edit_message(message.id, content=pages[index], view=view)

    # return a list of playlists for the calling guild
    @app_commands.command(description="playlists_command_desc")
    async def playlists_command(self, context: discord.Interaction):
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
            await self.cursor.execute("select pl_name from playlists where guild_id = ? order by guild_pl_id", (context.guild.id,))
            playlists = await self.cursor.fetchall()
            self.lock.release()
        message = guild["strings"]["playlists_header"] + "\n"
        if not (playlists or (self.cursor is None and self.data["guilds"][guild_index]["playlists"])):
            await context.followup.send(guild["strings"]["no_playlists"])
            return
        pages = []
        index = 0
        while index < len(self.data["guilds"][guild_index]["playlists"] if self.cursor is None else playlists):
            previous_message = message
            new_message = await self.polished_message(guild["strings"]["playlist"] + "\n",
                                                      {"playlist": self.data["guilds"][guild_index]["playlists"][index]["name"]
                                                                   if self.cursor is None
                                                                   else playlists[index][0],
                                                       "playlist_index": index + 1})
            message += new_message
            if len(message) > 2000:
                pages.append(previous_message)
                message = guild["strings"]["playlists_header"] + "\n" + new_message
            index += 1
        pages.append(message)
        await self.page_selector(context, guild["strings"], pages, 0)

    @app_commands.command(description="playlist_command_desc")
    @app_commands.describe(from_guild="from_guild_desc")
    @app_commands.describe(transfer="transfer_desc")
    @app_commands.describe(add="add_desc")
    @app_commands.describe(clone="clone_desc")
    @app_commands.describe(into="into_desc")
    @app_commands.describe(move="move_desc")
    @app_commands.describe(rename="rename_desc")
    @app_commands.describe(remove="remove_desc")
    @app_commands.describe(load="load_desc")
    @app_commands.describe(select="select_desc")
    @app_commands.describe(action="action_desc")
    @app_commands.describe(file="file_desc")
    @app_commands.describe(song_url="song_url_desc")
    @app_commands.describe(song_index="song_index_desc")
    @app_commands.describe(new_name="new_name_desc")
    @app_commands.describe(new_index="new_index_desc")
    async def playlist_command(self,
                               context: discord.Interaction,
                               from_guild: str=None,
                               transfer: int=None,
                               add: str=None,
                               clone: int=None,
                               into: int=None,
                               move: int=None,
                               rename: int=None,
                               remove: int=None,
                               load: int=None,
                               select: int=None,
                               action: str=None,
                               file: discord.Attachment=None,
                               song_url: str=None,
                               song_index: int=None,
                               new_name: str=None,
                               new_index: int=None):
        async def declare_command_invalid():
            await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
            await context.followup.send(strings["invalid_command"], ephemeral=True)
            self.lock.release()
        await context.response.defer()
        strings = self.guilds[str(context.guild.id)]["strings"]
        if select is not None and action == "add":
            if file is None and song_url is not None: url = song_url
            elif file is not None and song_url is None: url = str(file)
            else:
                await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
                await context.followup.send(strings["invalid_command"], ephemeral=True)
                return
            response = requests.get(url, stream=True)
            try: metadata = await self.get_metadata(BytesIO(response.content), url)
            except:
                await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
                await context.followup.send(await self.polished_message(strings["invalid_url"], {"url": url}), ephemeral=True)
                return
            # verify that the URL file is a media container
            if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
                await context.followup.send(await self.polished_message(strings["invalid_song"], {"song": await self.polished_song_name(url, metadata["name"])}),
                                            ephemeral=True)
                return
        await self.lock.acquire()
        if self.cursor is None:
            async def get_song_message(song):
                return await self.bot.get_guild(song["guild_id"]).get_channel_or_thread(song["channel_id"]).fetch_message(song["message_id"])
            for guild in self.data["guilds"]:
                if guild["id"] == context.guild.id:
                    # import a playlist
                    if from_guild is not None:
                        for guild_searched in self.data["guilds"]:
                            if guild_searched["id"] == int(from_guild):
                                from_guild_playlists = guild_searched["playlists"]
                                break
                        if transfer is None or transfer < 1 or transfer > len(from_guild_playlists):
                            await declare_command_invalid()
                            return
                        if new_name is None: new_name = from_guild_playlists[transfer - 1]["name"]
                        if new_index is None: new_index = len(guild["playlists"]) + 1
                        elif new_index < 1 or new_index > len(guild["playlists"]) + 1:
                            await declare_command_invalid()
                            return
                        guild["playlists"].insert(new_index - 1, {"name": new_name, "songs": from_guild_playlists[transfer - 1]["songs"].copy()})
                        await context.followup.send(await self.polished_message(strings["clone_playlist"], {"playlist": from_guild_playlists[transfer - 1]["name"],
                                                                                                            "playlist_index": transfer,
                                                                                                            "into_playlist": new_name,
                                                                                                            "into_playlist_index": new_index}))
                    # add a playlist
                    elif add is not None:
                        if new_index is None: new_index = len(guild["playlists"]) + 1
                        elif new_index < 1 or new_index > len(guild["playlists"]) + 1:
                            await declare_command_invalid()
                            return
                        guild["playlists"].insert(new_index - 1, {"name": add, "songs": []})
                        await context.followup.send(await self.polished_message(strings["add_playlist"], {"playlist": add, "playlist_index": new_index}))
                    # clone a playlist or copy its tracks into another playlist
                    elif clone is not None and 0 < clone <= len(guild["playlists"]):
                        # clone a playlist
                        if into is None or into < 1 or into > len(guild["playlists"]):
                            playlist = guild["playlists"][clone - 1]["name"]
                            if new_name is None: new_name = playlist
                            if new_index is None: new_index = len(guild["playlists"]) + 1
                            elif new_index < 1 or new_index > len(guild["playlists"]) + 1:
                                await declare_command_invalid()
                                return
                            guild["playlists"].insert(new_index - 1, {"name": new_name, "songs": guild["playlists"][clone - 1]["songs"].copy()})
                            await context.followup.send(await self.polished_message(strings["clone_playlist"],
                                                                                    {"playlist": playlist,
                                                                                     "playlist_index": clone,
                                                                                     "into_playlist": new_name,
                                                                                     "into_playlist_index": new_index}))
                        # copy a playlist's tracks into another playlist
                        else:
                            guild["playlists"][into - 1]["songs"] += guild["playlists"][clone - 1]["songs"]
                            await context.followup.send(await self.polished_message(strings["clone_playlist"],
                                                                                    {"playlist": guild["playlists"][clone - 1]["name"],
                                                                                     "playlist_index": clone,
                                                                                     "into_playlist": guild["playlists"][into - 1]["name"],
                                                                                     "into_playlist_index": into}))
                    # change a playlist's position in the order of playlists
                    elif move is not None and 0 < move <= len(guild["playlists"]):
                        if new_index is None or new_index < 1 or new_index > len(guild["playlists"]):
                            await declare_command_invalid()
                            return
                        playlists = guild["playlists"].copy()
                        guild["playlists"].remove(playlists[move - 1])
                        guild["playlists"].insert(new_index - 1, playlists[move - 1])
                        await context.followup.send(await self.polished_message(strings["move_playlist"], {"playlist": playlists[move - 1]["name"],
                                                                                                           "playlist_index": new_index}))
                    # rename a playlist
                    elif rename is not None and 0 < rename <= len(guild["playlists"]):
                        if new_name is None:
                            await declare_command_invalid()
                            return
                        await context.followup.send(await self.polished_message(strings["rename_playlist"], {"playlist": guild["playlists"][rename - 1]["name"],
                                                                                                             "playlist_index": rename,
                                                                                                             "name": new_name}))
                        guild["playlists"][rename - 1]["name"] = new_name
                    # remove a playlist
                    elif remove is not None and 0 < remove <= len(guild["playlists"]):
                        await context.followup.send(await self.polished_message(strings["remove_playlist"], {"playlist": guild["playlists"][remove - 1]["name"],
                                                                                                             "playlist_index": remove}))
                        guild["playlists"].remove(guild["playlists"][remove - 1])
                    # load a playlist
                    elif load is not None and 0 < load <= len(guild["playlists"]):
                        self.lock.release()
                        if guild["playlists"][load - 1]["songs"]:
                            songs = []
                            for song in guild["playlists"][load - 1]["songs"]:
                                if song["file"] is None:
                                    try: song_message = self.messages[str(song["message_id"])]
                                    except:
                                        song_message = await get_song_message(song)
                                        self.messages[str(song["message_id"])] = song_message
                                    song_file = str(song_message.attachments[song["attachment_index"]])
                                else: song_file = song["file"]
                                songs.append({"name": song["name"], "file": song_file, "duration": song["duration"]})
                            await context.followup.send(await self.polished_message(strings["load_playlist"],
                                                                                    {"playlist": guild["playlists"][load - 1]["name"], "playlist_index": load}))
                            await self.play_song(context, playlist=songs)
                        else: await context.followup.send(await self.polished_message(strings["playlist_no_songs"],
                                                                                      {"playlist": guild["playlists"][load - 1]["name"], "playlist_index": load}))
                        return
                    # select a playlist to modify or show the contents of
                    elif select is not None and action is not None:
                        if 0 < select <= len(guild["playlists"]):
                            playlist = guild["playlists"][select - 1]["name"]
                            # add a track to the playlist
                            if action == "add":
                                if new_name is None: new_name = metadata["name"]
                                if new_index is None: new_index = len(guild["playlists"][select - 1]["songs"]) + 1
                                elif new_index < 1 or new_index > len(guild["playlists"][select - 1]["songs"]):
                                    await declare_command_invalid()
                                    return
                                song = {"name": new_name, "index": new_index, "duration": metadata["duration"]}
                                guild["playlists"][select - 1]["songs"].insert(song["index"] - 1, {"name": song["name"],
                                                                                                   "file": url if file is None else None,
                                                                                                   "duration": song["duration"],
                                                                                                   "guild_id": context.guild.id,
                                                                                                   "channel_id": 0,
                                                                                                   "message_id": 0,
                                                                                                   "attachment_index": 0})
                                await context.followup.send(await self.polished_message(strings["playlist_add_song"],
                                                                                        {"playlist": playlist,
                                                                                         "playlist_index": select,
                                                                                         "song": await self.polished_song_name(url, song["name"]),
                                                                                         "index": song["index"]}))
                                if file is not None:
                                    self.lock.release()
                                    await self.renew_attachment(guild["id"], context.channel.id, select - 1, song["index"] - 1, url)
                                    return
                            # change the position of a track within the playlist
                            elif action == "move":
                                if (song_index is None or
                                    song_index < 1 or
                                    song_index > len(guild["playlists"][select - 1]["songs"]) or
                                    new_index is None or
                                    new_index < 1 or
                                    new_index > len(guild["playlists"][select - 1]["songs"])):
                                    await declare_command_invalid()
                                    return
                                song = guild["playlists"][select - 1]["songs"][song_index - 1]
                                if song["file"] is None: song_file = str(await get_song_message(song).attachments[song["attachment_index"]])
                                else: song_file = song["file"]
                                guild["playlists"][select - 1]["songs"].remove(song)
                                guild["playlists"][select - 1]["songs"].insert(new_index - 1, song)
                                await context.followup.send(await self.polished_message(strings["playlist_move_song"],
                                                                                        {"playlist": playlist,
                                                                                         "playlist_index": select,
                                                                                         "song": await self.polished_song_name(song_file, song["name"]),
                                                                                         "index": new_index}))
                            # rename a track in the playlist
                            elif action == "rename":
                                if song_index is None or song_index < 1 or song_index > len(guild["playlists"][select - 1]["songs"]) or new_name is None:
                                    await declare_command_invalid()
                                    return
                                song = guild["playlists"][select - 1]["songs"][song_index - 1]
                                if song["file"] is None: song_file = str(await get_song_message(song).attachments[song["attachment_index"]])
                                else: song_file = song["file"]
                                await context.followup.send(await self.polished_message(strings["playlist_rename_song"],
                                                                                        {"playlist": playlist,
                                                                                         "playlist_index": select,
                                                                                         "song": await self.polished_song_name(song_file, song["name"]),
                                                                                         "index": song_index,
                                                                                         "name": new_name}))
                                song["name"] = new_name
                            # remove a track from the playlist
                            elif action == "remove":
                                if song_index is None or song_index < 1 or song_index > len(guild["playlists"][select - 1]["songs"]):
                                    await declare_command_invalid()
                                    return
                                song = guild["playlists"][select - 1]["songs"][song_index - 1]
                                if song["file"] is None: song_file = str(await get_song_message(song).attachments[song["attachment_index"]])
                                else: song_file = song["file"]
                                guild["playlists"][select - 1]["songs"].remove(song)
                                await context.followup.send(await self.polished_message(strings["playlist_remove_song"],
                                                                                        {"playlist": playlist,
                                                                                         "playlist_index": select,
                                                                                         "song": await self.polished_song_name(song_file, song["name"]),
                                                                                         "index": song_index}))
                            # return a list of tracks in the playlist
                            elif action == "list":
                                await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
                                message = await self.polished_message(strings["playlist_songs_header"] + "\n", {"playlist": playlist, "playlist_index": select})
                                self.lock.release()
                                if not guild["playlists"][select - 1]["songs"]:
                                    await context.followup.send(await self.polished_message(strings["playlist_no_songs"], {"playlist": playlist,
                                                                                                                           "playlist_index": select}),
                                                                ephemeral=True)
                                    return
                                pages = []
                                index = 0
                                for song in guild["playlists"][select - 1]["songs"]:
                                    previous_message = message
                                    if song["file"] is None:
                                        try: song_message = self.messages[str(song["message_id"])]
                                        except:
                                            song_message = await get_song_message(song)
                                            self.messages[str(song["message_id"])] = song_message
                                        song_file = str(song_message.attachments[song["attachment_index"]])
                                    else: song_file = song["file"]
                                    new_message = await self.polished_message(strings["song"] + "\n", {"song": await self.polished_song_name(song_file, song["name"]),
                                                                                                       "index": index + 1})
                                    message += new_message
                                    if len(message) > 2000:
                                        pages.append(previous_message)
                                        message = "".join([await self.polished_message(strings["playlist_songs_header"] + "\n", {"playlist": playlist,
                                                                                                                                 "playlist_index": select}),
                                                           new_message])
                                    index += 1
                                pages.append(message)
                                await self.page_selector(context, strings, pages, 0)
                                return
                            else:
                                await declare_command_invalid()
                                return
                        else:
                            await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
                            await context.followup.send(await self.polished_message(strings["invalid_playlist_number"], {"playlist_index": select}), ephemeral=True)
                            self.lock.release()
                            return
                    else:
                        await declare_command_invalid()
                        return
                    # modify the flat file for guilds to reflect changes regarding playlists
                    yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)

                    break
        else:
            get_songs_statement = """select pl_songs.song_id, pl_songs.song_name, songs.guild_id, channel_id, message_id, attachment_index, song_url from pl_songs
                                     left outer join songs on songs.song_id = pl_songs.song_id
                                     left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                     where playlists.guild_id = ? and guild_pl_id = ?"""
            await self.cursor.execute("select count(pl_id) from playlists where guild_id = ?", (context.guild.id,))
            playlist_count = (await self.cursor.fetchone())[0]
            # import a playlist
            if from_guild is not None:
                await self.cursor.execute("select count(pl_id) from playlists where guild_id = ?", (int(from_guild),))
                from_guild_playlist_count = (await self.cursor.fetchone())[0]
                if transfer is None or transfer < 1 or transfer > from_guild_playlist_count:
                    await declare_command_invalid()
                    return
                await self.cursor.execute("""select song_id, song_name, song_url from pl_songs
                                             left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                             where guild_id = ? and guild_pl_id = ?
                                             order by pl_song_id""",
                                          (int(from_guild), transfer - 1))
                songs = await self.cursor.fetchall()
                if new_name is None:
                    await self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?", (int(from_guild), transfer - 1))
                    new_name = (await self.cursor.fetchone())[0]
                if new_index is not None and (new_index < 1 or new_index > playlist_count + 1):
                    await declare_command_invalid()
                    return
                await self.cursor.execute("""insert into playlists values((select max(pl_id) from playlists) + 1,
                                                                          ?,
                                                                          ?,
                                                                          (select count(pl_id) from playlists where guild_id = ?))""",
                                          (new_name, context.guild.id, context.guild.id))
                for song in songs:
                    await self.cursor.execute("""insert into pl_songs values(?,
                                                                             ?,
                                                                             ?,
                                                                             (select max(pl_id) from playlists),
                                                                             (select count(song_id) from pl_songs where pl_id = (select max(pl_id) from playlists)))""",
                                              (song[0], song[1], song[2]))
                if new_index is None: new_index = playlist_count + 1
                else:
                    await self.cursor.execute("update playlists set guild_pl_id = guild_pl_id + 1 where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?",
                                              (new_index - 1, playlist_count, context.guild.id))
                    await self.cursor.execute("update playlists set guild_pl_id = ? where pl_id = (select max(pl_id) from playlists)", (new_index - 1,))
                await self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?", (int(from_guild), transfer - 1))
                await context.followup.send(await self.polished_message(strings["clone_playlist"], {"playlist": (await self.cursor.fetchone())[0],
                                                                                                    "playlist_index": transfer,
                                                                                                    "into_playlist": new_name,
                                                                                                    "into_playlist_index": new_index}))
            # add a playlist
            elif add is not None:
                if new_index is not None and (new_index < 1 or new_index > playlist_count + 1):
                    await declare_command_invalid()
                    return
                try: await self.cursor.execute("""insert into playlists values((select max(pl_id) from playlists) + 1,
                                                                               ?,
                                                                               ?,
                                                                               (select count(pl_id) from playlists where guild_id = ?))""",
                                               (add, context.guild.id, context.guild.id))
                except: await self.cursor.execute("""insert into playlists values(0,
                                                                                  ?,
                                                                                  ?,
                                                                                  (select count(pl_id) from playlists where guild_id = ?))""",
                                                  (add, context.guild.id, context.guild.id))
                if new_index is None: new_index = playlist_count + 1
                else:
                    await self.cursor.execute("update playlists set guild_pl_id = guild_pl_id + 1 where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?",
                                              (new_index - 1, playlist_count, context.guild.id))
                    await self.cursor.execute("update playlists set guild_pl_id = ? where pl_id = (select max(pl_id) from playlists)", (new_index - 1,))
                await context.followup.send(await self.polished_message(strings["add_playlist"], {"playlist": add, "playlist_index": new_index}))
            # clone a playlist or copy its tracks into another playlist
            elif clone is not None and 0 < clone <= playlist_count:
                # clone a playlist
                await self.cursor.execute("""select song_id, song_name, song_url from pl_songs
                                             left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                             where guild_id = ? and guild_pl_id = ?
                                             order by pl_song_id""",
                                          (context.guild.id, clone - 1))
                songs = await self.cursor.fetchall()
                if into is None or into < 1 or into > playlist_count:
                    await self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?", (context.guild.id, clone - 1))
                    playlist = (await self.cursor.fetchone())[0]
                    if new_name is None: new_name = playlist
                    if new_index is not None and (new_index < 1 or new_index > playlist_count + 1):
                        await declare_command_invalid()
                        return
                    await self.cursor.execute("""insert into playlists values((select max(pl_id) from playlists) + 1,
                                                                              ?,
                                                                              ?,
                                                                              (select count(pl_id) from playlists where guild_id = ?))""",
                                              (new_name, context.guild.id, context.guild.id))
                    for song in songs:
                        await self.cursor.execute("""insert into pl_songs values(?,
                                                                                 ?,
                                                                                 ?,
                                                                                 (select max(pl_id) from playlists),
                                                                                 (select count(song_id) from pl_songs
                                                                                  where pl_id = (select max(pl_id) from playlists)))""",
                                                  (song[0], song[1], song[2]))
                    if new_index is None: new_index = playlist_count + 1
                    else:
                        await self.cursor.execute("update playlists set guild_pl_id = guild_pl_id + 1 where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?",
                                                  (new_index - 1, playlist_count, context.guild.id))
                        await self.cursor.execute("update playlists set guild_pl_id = ? where pl_id = (select max(pl_id) from playlists)", (new_index - 1,))
                    await context.followup.send(await self.polished_message(strings["clone_playlist"], {"playlist": playlist,
                                                                                                        "playlist_index": clone,
                                                                                                        "into_playlist": new_name,
                                                                                                        "into_playlist_index": new_index}))
                # copy a playlist's tracks into another playlist
                else:
                    for song in songs: await self.cursor.execute("""insert into pl_songs values(?,
                                                                                                ?,
                                                                                                ?,
                                                                                                (select pl_id from playlists where guild_id = ? and guild_pl_id = ?),
                                                                                                (select count(song_id) from pl_songs
                                                                                                 left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                                                                                 where guild_id = ? and guild_pl_id = ?))""",
                                                                 (song[0], song[1], song[2], context.guild.id, into - 1, context.guild.id, into - 1))
                    await self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?", (context.guild.id, clone - 1))
                    playlist = (await self.cursor.fetchone())[0]
                    await self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?", (context.guild.id, into - 1))
                    into_playlist = (await self.cursor.fetchone())[0]
                    await context.followup.send(await self.polished_message(strings["clone_playlist"], {"playlist": playlist,
                                                                                                        "playlist_index": clone,
                                                                                                        "into_playlist": into_playlist,
                                                                                                        "into_playlist_index": into}))
            # change a playlist's position in the order of playlists
            elif move is not None and 0 < move <= playlist_count:
                await self.cursor.execute("select pl_id, pl_name from playlists where guild_id = ? order by guild_pl_id", (context.guild.id,))
                playlist_copies = await self.cursor.fetchall()
                if new_index is None or new_index < 1 or new_index > playlist_count:
                    await declare_command_invalid()
                    return
                elif new_index > move: await self.cursor.execute("""update playlists set guild_pl_id = guild_pl_id - 1
                                                                    where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?""",
                                                                 (move - 1, new_index - 1, context.guild.id))
                elif new_index < move: await self.cursor.execute("""update playlists set guild_pl_id = guild_pl_id + 1
                                                                    where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?""",
                                                                 (new_index - 1, move - 1, context.guild.id))
                await self.cursor.execute("update playlists set guild_pl_id = ? where pl_id = ?", (new_index - 1, playlist_copies[move - 1][0]))
                await context.followup.send(await self.polished_message(strings["move_playlist"], {"playlist": playlist_copies[move - 1][1],
                                                                                                   "playlist_index": new_index}))
            # rename a playlist
            elif rename is not None and 0 < rename <= playlist_count:
                if new_name is None:
                    await declare_command_invalid()
                    return
                await self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?", (context.guild.id, rename - 1))
                await context.followup.send(await self.polished_message(strings["rename_playlist"], {"playlist": (await self.cursor.fetchone())[0],
                                                                                                     "playlist_index": rename,
                                                                                                     "name": new_name}))
                await self.cursor.execute("update playlists set pl_name = ? where guild_id = ? and guild_pl_id = ?", (new_name, context.guild.id, rename - 1))
            # remove a playlist
            elif remove is not None and 0 < remove <= playlist_count:
                await self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?", (context.guild.id, remove - 1))
                await context.followup.send(await self.polished_message(strings["remove_playlist"], {"playlist": (await self.cursor.fetchone())[0],
                                                                                                     "playlist_index": remove}))
                await self.cursor.execute("delete from pl_songs where pl_id = (select pl_id from playlists where guild_id = ? and guild_pl_id = ?)",
                                          (context.guild.id, remove - 1))
                await self.cursor.execute("delete from songs where song_id not in (select song_id from pl_songs)")
                await self.cursor.execute("delete from playlists where guild_id = ? and guild_pl_id = ?", (context.guild.id, remove - 1))
                await self.cursor.execute("update playlists set guild_pl_id = guild_pl_id - 1 where guild_pl_id >= ? and guild_id = ?", (remove - 1, context.guild.id))
            # load a playlist
            elif load is not None and 0 < load <= playlist_count:
                await self.cursor.execute(f"{get_songs_statement} order by pl_song_id".replace("pl_songs.song_id,", "song_duration,"), (context.guild.id, load - 1))
                songs = await self.cursor.fetchall()
                self.lock.release()
                if songs:
                    proper_songs = []
                    for song in songs:
                        if song[6] is None:
                            try: song_message = self.messages[str(song[4])]
                            except:
                                song_message = await self.bot.get_guild(song[2]).get_channel_or_thread(song[3]).fetch_message(song[4])
                                self.messages[str(song[4])] = song_message
                            song_file = str(song_message.attachments[song[5]])
                        else: song_file = song[6]
                        proper_songs.append({"name": song[1], "duration": song[0], "file": song_file})
                    await self.lock.acquire()
                    await self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?", (context.guild.id, load - 1))
                    try:
                        if context.user.voice.channel is not None:
                            await context.followup.send(await self.polished_message(strings["load_playlist"], {"playlist": (await self.cursor.fetchone())[0],
                                                                                                               "playlist_index": load}))
                    except: pass
                    self.lock.release()
                    await self.play_song(context, playlist=proper_songs)
                else:
                    await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
                    await self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?", (context.guild.id, load - 1))
                    await context.followup.send(await self.polished_message(strings["playlist_no_songs"], {"playlist": (await self.cursor.fetchone())[0],
                                                                                                           "playlist_index": load}),
                                                ephemeral=True)
                return
            # select a playlist to modify or show the contents of
            elif select is not None and action is not None:
                if 0 < select <= playlist_count:
                    await self.cursor.execute("""select pl_songs.pl_id, pl_name, count(song_id) from pl_songs
                                                 right outer join playlists on playlists.pl_id = pl_songs.pl_id
                                                 where guild_id = ? and guild_pl_id = ?
                                                 group by pl_songs.pl_id, pl_name""",
                                              (context.guild.id, select - 1))
                    global_playlist_id, playlist, song_count = await self.cursor.fetchone()
                    # add a track to the playlist
                    if action == "add":
                        if new_name is None: new_name = metadata["name"]
                        if new_index is not None and (new_index < 1 or new_index > song_count + 1):
                            await declare_command_invalid()
                            return
                        try: await self.cursor.execute("insert into songs values((select max(song_id) from songs) + 1, ?, ?, ?, ?, ?, ?)",
                                                       (new_name, metadata["duration"], context.guild.id, 0, 0, 0))
                        except: await self.cursor.execute("insert into songs values(0, ?, ?, ?, ?, ?, ?)", (new_name, metadata["duration"], context.guild.id, 0, 0, 0))
                        await self.cursor.execute("""insert into pl_songs values((select max(song_id) from songs),
                                                                                 ?,
                                                                                 ?,
                                                                                 (select pl_id from playlists where guild_id = ? and guild_pl_id = ?),
                                                                                 (select count(song_id) from pl_songs
                                                                                  left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                                                                  where guild_id = ? and guild_pl_id = ?))""",
                                                  (new_name, url if file is None else None, context.guild.id, select - 1, context.guild.id, select - 1))
                        if new_index is None: new_index = song_count + 1
                        else:
                            await self.cursor.execute("update pl_songs set pl_song_id = pl_song_id + 1 where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?",
                                                      (new_index - 1, song_count, global_playlist_id))
                            await self.cursor.execute("update pl_songs set pl_song_id = ? where song_id = (select max(song_id) from songs)", (new_index - 1,))
                        await context.followup.send(await self.polished_message(strings["playlist_add_song"], {"playlist": playlist,
                                                                                                               "playlist_index": select,
                                                                                                               "song": await self.polished_song_name(url, new_name),
                                                                                                               "index": new_index}))
                        if file is not None:
                            await self.cursor.execute("select max(song_id) from songs")
                            song_id = (await self.cursor.fetchone())[0]
                            self.lock.release()
                            await self.renew_attachment(context.guild.id, context.channel.id, select - 1, new_index - 1, url, song_id)
                            return
                    # change the position of a track within the playlist
                    elif action == "move":
                        await self.cursor.execute(f"{get_songs_statement} order by pl_song_id", (context.guild.id, select - 1))
                        song_copies = await self.cursor.fetchall()
                        if song_index is None or song_index < 1 or song_index > song_count or new_index is None or new_index < 1 or new_index > song_count:
                            await declare_command_invalid()
                            return
                        elif new_index > song_index: await self.cursor.execute("""update pl_songs set pl_song_id = pl_song_id - 1
                                                                                  where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?""",
                                                                               (song_index - 1, new_index - 1, global_playlist_id))
                        elif new_index < song_index: await self.cursor.execute("""update pl_songs set pl_song_id = pl_song_id + 1
                                                                                  where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?""",
                                                                               (new_index - 1, song_index - 1, global_playlist_id))
                        song = song_copies[song_index - 1]
                        await self.cursor.execute("update pl_songs set pl_song_id = ? where song_id = ?", (new_index - 1, song[0]))
                        if song[6] is None:
                            song_file = str((await self.bot.get_guild(song[2]).get_channel_or_thread(song[3]).fetch_message(song[4])).attachments[song[5]])
                        else: song_file = song[6]
                        await context.followup.send(await self.polished_message(strings["playlist_move_song"],
                                                                                {"playlist": playlist,
                                                                                 "playlist_index": select,
                                                                                 "song": await self.polished_song_name(song_file, song[1]),
                                                                                 "index": new_index}))
                    # rename a track in the playlist
                    elif action == "rename":
                        if song_index is None or song_index < 1 or song_index > song_count or new_name is None:
                            await declare_command_invalid()
                            return
                        await self.cursor.execute(f"{get_songs_statement} and pl_song_id = ?", (context.guild.id, select - 1, song_index - 1))
                        song_id, song_name, guild_id, channel_id, message_id, attachment_index, song_file = await self.cursor.fetchone()
                        if song_file is None:
                            song_file = str((await self.bot.get_guild(guild_id).get_channel_or_thread(channel_id).fetch_message(message_id))
                                            .attachments[attachment_index])
                        await context.followup.send(await self.polished_message(strings["playlist_rename_song"],
                                                                                {"playlist": playlist,
                                                                                 "playlist_index": select,
                                                                                 "song": await self.polished_song_name(song_file, song_name),
                                                                                 "index": song_index,
                                                                                 "name": new_name}))
                        await self.cursor.execute("update pl_songs set song_name = ? where song_id = ?", (new_name, song_id))
                    # remove a track from the playlist
                    elif action == "remove":
                        if song_index is None or song_index < 1 or song_index > song_count:
                            await declare_command_invalid()
                            return
                        await self.cursor.execute(f"{get_songs_statement} and pl_song_id = ?", (context.guild.id, select - 1, song_index - 1))
                        song_id, song_name, guild_id, channel_id, message_id, attachment_index, song_file = await self.cursor.fetchone()
                        if song_file is None:
                            song_file = str((await self.bot.get_guild(guild_id).get_channel_or_thread(channel_id).fetch_message(message_id))
                                            .attachments[attachment_index])
                        await self.cursor.execute("delete from pl_songs where song_id = ?", (song_id,))
                        await self.cursor.execute("delete from songs where song_id not in (select song_id from pl_songs)")
                        await self.cursor.execute("update pl_songs set pl_song_id = pl_song_id - 1 where pl_song_id >= ? and pl_id = ?",
                                                  (song_index - 1, global_playlist_id))
                        await context.followup.send(await self.polished_message(strings["playlist_remove_song"],
                                                                                {"playlist": playlist,
                                                                                 "playlist_index": select,
                                                                                 "song": await self.polished_song_name(song_file, song_name),
                                                                                 "index": song_index}))
                    # return a list of tracks in the playlist
                    elif action == "list":
                        await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
                        message = await self.polished_message(strings["playlist_songs_header"] + "\n", {"playlist": playlist, "playlist_index": select})
                        await self.cursor.execute(f"{get_songs_statement} order by pl_song_id", (context.guild.id, select - 1))
                        songs = await self.cursor.fetchall()
                        self.lock.release()
                        if not songs:
                            await context.followup.send(await self.polished_message(strings["playlist_no_songs"], {"playlist": playlist, "playlist_index": select}),
                                                        ephemeral=True)
                            return
                        pages = []
                        index = 0
                        for song in songs:
                            previous_message = message
                            if song[6] is None:
                                try: song_message = self.messages[str(song[4])]
                                except:
                                    song_message = await self.bot.get_guild(song[2]).get_channel_or_thread(song[3]).fetch_message(song[4])
                                    self.messages[str(song[4])] = song_message
                                song_file = str(song_message.attachments[song[5]])
                            else: song_file = song[6]
                            new_message = await self.polished_message(strings["song"] + "\n",
                                                                      {"song": await self.polished_song_name(song_file, song[1]), "index": index + 1})
                            message += new_message
                            if len(message) > 2000:
                                pages.append(previous_message)
                                message = "".join([await self.polished_message(strings["playlist_songs_header"] + "\n", {"playlist": playlist,
                                                                                                                         "playlist_index": select}),
                                                   new_message])
                            index += 1
                        pages.append(message)
                        await self.page_selector(context, strings, pages, 0)
                        return
                    else:
                        await declare_command_invalid()
                        return
                else:
                    await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
                    await context.followup.send(await self.polished_message(strings["invalid_playlist_number"], {"playlist_index": select}), ephemeral=True)
                    self.lock.release()
                    return
            else:
                await declare_command_invalid()
                return
            await self.connection.commit()
        self.lock.release()

    @playlist_command.autocomplete("from_guild")
    async def playlist_guild_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        guild_names = []
        if self.cursor is None:
            guild_ids = []
            for guild in self.data["guilds"]:
                user_ids = []
                for user in guild["users"]: user_ids.append(user["id"])
                if context.user.id in user_ids: guild_ids.append([guild["id"]])
        else:
            await self.lock.acquire()
            await self.cursor.execute("select guild_id from guild_users where user_id = ?", (context.user.id,))
            guild_ids = await self.cursor.fetchall()
            self.lock.release()
        for guild_id in guild_ids:
            guild_name = self.bot.get_guild(guild_id[0]).name
            guild_name = guild_name[:97] + "..." if len(guild_name) > 100 else guild_name
            if (current == "" or current.lower() in guild_name.lower()) and guild_id[0] != context.guild.id and len(guild_names) < 25:
                guild_names.append(app_commands.Choice(name=guild_name, value=str(guild_id[0])))
        return guild_names

    @playlist_command.autocomplete("transfer")
    @playlist_command.autocomplete("clone")
    @playlist_command.autocomplete("into")
    @playlist_command.autocomplete("move")
    @playlist_command.autocomplete("rename")
    @playlist_command.autocomplete("remove")
    @playlist_command.autocomplete("load")
    @playlist_command.autocomplete("select")
    async def playlist_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[int]]:
        strings = self.guilds[str(context.guild.id)]["strings"]
        playlists = []
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == (context.guild.id if context.namespace.from_guild is None else int(context.namespace.from_guild)):
                    index = 1
                    for playlist in guild["playlists"]:
                        polished_playlist_name = await self.polished_message(strings["playlist"], {"playlist": playlist["name"], "playlist_index": index})
                        playlist["name"] = (playlist["name"][:97 - len(polished_playlist_name) + len(playlist["name"])] + "..."
                                            if len(polished_playlist_name) > 100 else playlist["name"])
                        if (current == "" or current.lower() in polished_playlist_name.lower()) and len(playlists) < 25:
                            playlists.append(app_commands.Choice(name=polished_playlist_name, value=index))
                        index += 1
                    break
        else:
            await self.lock.acquire()
            await self.cursor.execute("select pl_name from playlists where guild_id = ? order by guild_pl_id",
                                      (context.guild.id if context.namespace.from_guild is None else int(context.namespace.from_guild),))
            playlist_names = list(await self.cursor.fetchall())
            self.lock.release()
            index = 1
            for playlist in playlist_names:
                playlist_name = list(playlist)
                polished_playlist_name = await self.polished_message(strings["playlist"], {"playlist": playlist_name[0], "playlist_index": index})
                playlist_name[0] = (playlist_name[0][:97 - len(polished_playlist_name) + len(playlist_name[0])] + "..."
                                    if len(polished_playlist_name) > 100 else playlist_name[0])
                if (current == "" or current.lower() in polished_playlist_name.lower()) and len(playlists) < 25:
                    playlists.append(app_commands.Choice(name=polished_playlist_name, value=index))
                index += 1
        return playlists

    @playlist_command.autocomplete("action")
    async def playlist_action_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        strings = self.guilds[str(context.guild.id)]["strings"]
        action_options = [app_commands.Choice(name=strings["add"], value="add"),
                          app_commands.Choice(name=strings["move"], value="move"),
                          app_commands.Choice(name=strings["rename"], value="rename"),
                          app_commands.Choice(name=strings["remove"], value="remove"),
                          app_commands.Choice(name=strings["list"], value="list")]
        actions = []
        for action in action_options:
            if current == "" or current.lower() in action.name.lower(): actions.append(action)
        return actions

    @playlist_command.autocomplete("song_index")
    async def playlist_song_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[int]]:
        strings = self.guilds[str(context.guild.id)]["strings"]
        songs = []
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == context.guild.id:
                    try:
                        index = 1
                        for song in guild["playlists"][context.namespace.select - 1]["songs"]:
                            polished_song_name = await self.polished_message(strings["song"], {"song": song["name"], "index": index})
                            song["name"] = song["name"][:97 - len(polished_song_name) + len(song["name"])] + "..." if len(polished_song_name) > 100 else song["name"]
                            if (current == "" or current.lower() in polished_song_name.lower()) and len(songs) < 25:
                                songs.append(app_commands.Choice(name=polished_song_name, value=index))
                            index += 1
                    except: pass
                    break
        else:
            try:
                await self.lock.acquire()
                await self.cursor.execute("""select song_name from pl_songs
                                             left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                             where guild_id = ? and guild_pl_id = ?
                                             order by pl_song_id""",
                                          (context.guild.id, context.namespace.select - 1))
                song_names = list(await self.cursor.fetchall())
                self.lock.release()
                index = 1
                for song in song_names:
                    song_name = list(song)
                    polished_song_name = await self.polished_message(strings["song"], {"song": song_name[0], "index": index})
                    song_name[0] = song_name[0][:97 - len(polished_song_name) + len(song_name[0])] + "..." if len(polished_song_name) > 100 else song_name[0]
                    if (current == "" or current.lower() in polished_song_name.lower()) and len(songs) < 25:
                        songs.append(app_commands.Choice(name=polished_song_name, value=index))
                    index += 1
            except: pass
        return songs

    async def playlist_add_files(self, context: discord.Interaction, message_regarded: discord.Message):
        await context.response.defer()
        guild = self.guilds[str(context.guild.id)]
        strings = guild["strings"]
        # show a dropdown menu of all the playlists for the calling guild
        playlist_options = [discord.SelectOption(label=strings["cancel_option"])]
        index = 1
        if self.cursor is None:
            for guild_searched in self.data["guilds"]:
                if guild_searched["id"] == context.guild.id:
                    for playlist in guild_searched["playlists"]:
                        playlist_options.append(discord.SelectOption(label=await self.polished_message(strings["playlist"], {"playlist": playlist["name"],
                                                                                                                             "playlist_index": index}),
                                                                     value=str(index)))
                        index += 1
                    break
        else:
            await self.lock.acquire()
            await self.cursor.execute("select pl_name from playlists where guild_id = ? order by guild_pl_id", (context.guild.id,))
            playlists = await self.cursor.fetchall()
            self.lock.release()
            for playlist in playlists:
                playlist_options.append(discord.SelectOption(label=await self.polished_message(strings["playlist"], {"playlist": playlist[0], "playlist_index": index}),
                                                             value=str(index)))
                index += 1
        playlist_menu = discord.ui.Select(placeholder=strings["playlist_select_menu_placeholder"], options=playlist_options)
        chosen = []
        async def playlist_callback(context):
            await context.response.send_message("...", ephemeral=True)
            await context.delete_original_response()
            chosen.append(playlist_menu.values[0])
        playlist_menu.callback = playlist_callback
        view = discord.ui.View()
        view.add_item(playlist_menu)
        await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
        await context.followup.send("", view=view, ephemeral=True)
        while not chosen: await asyncio.sleep(.1)
        if chosen[0] == strings["cancel_option"]: return
        index = int(chosen[0])

        playlist = []
        urls = []
        for url in message_regarded.attachments:
            response = requests.get(str(url), stream=True)
            try: metadata = await self.get_metadata(BytesIO(response.content), str(url))
            except:
                await context.followup.send(await self.polished_message(strings["invalid_url"], {"url": str(url)}), ephemeral=True)
                return
            # verify that the URL file is a media container
            if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                await context.followup.send(await self.polished_message(strings["invalid_song"], {"song": await self.polished_song_name(str(url), metadata["name"])}),
                                            ephemeral=True)
                return

            urls.append(str(url))
            playlist.append({"name": metadata["name"],
                             "file": None,
                             "duration": metadata["duration"],
                             "guild_id": message_regarded.guild.id,
                             "channel_id": message_regarded.channel.id,
                             "message_id": message_regarded.id,
                             "attachment_index": message_regarded.attachments.index(url)})
        await self.lock.acquire()
        if self.cursor is None:
            for guild_searched in self.data["guilds"]:
                if guild_searched["id"] == context.guild.id:
                    message = ""
                    for song in playlist:
                        guild_searched["playlists"][index - 1]["songs"].append(song)
                        previous_message = message
                        new_message = await self.polished_message(strings["playlist_add_song"] + "\n",
                                                                  {"playlist": guild_searched["playlists"][index - 1]["name"],
                                                                   "playlist_index": index,
                                                                   "song": await self.polished_song_name(urls[playlist.index(song)], song["name"]),
                                                                   "index": len(guild_searched["playlists"][index - 1]["songs"])})
                        message += new_message
                        if len(message) > 2000:
                            await context.followup.send(previous_message)
                            message = new_message
                    await context.followup.send(message)
                    break
            yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
        else:
            message = ""
            for song in playlist:
                try: await self.cursor.execute("insert into songs values((select max(song_id) from songs) + 1, ?, ?, ?, ?, ?, ?)",
                                               (song["name"], song["duration"], song["guild_id"], song["channel_id"], song["message_id"], song["attachment_index"]))
                except: await self.cursor.execute("insert into songs values(0, ?, ?, ?, ?, ?, ?)",
                                                  (song["name"], song["duration"], song["guild_id"], song["channel_id"], song["message_id"], song["attachment_index"]))
                await self.cursor.execute("""insert into pl_songs values((select max(song_id) from songs),
                                                                         ?,
                                                                         ?,
                                                                         (select pl_id from playlists where guild_id = ? and guild_pl_id = ?),
                                                                         (select count(song_id) from pl_songs
                                                                          left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                                                          where guild_id = ? and guild_pl_id = ?))""",
                                          (song["name"], song["file"], context.guild.id, index - 1, context.guild.id, index - 1))
                previous_message = message
                await self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?", (context.guild.id, index - 1))
                playlist_name = (await self.cursor.fetchone())[0]
                await self.cursor.execute("""select count(song_id) from pl_songs
                                             left outer join playlists on playlists.pl_id = pl_songs.pl_id
                                             where guild_id = ? and guild_pl_id = ?""",
                                          (context.guild.id, index - 1))
                song_index = (await self.cursor.fetchone())[0]
                new_message = await self.polished_message(strings["playlist_add_song"] + "\n",
                                                          {"playlist": playlist_name,
                                                           "playlist_index": index,
                                                           "song": await self.polished_song_name(urls[playlist.index(song)], song["name"]),
                                                           "index": song_index})
                message += new_message
                if len(message) > 2000:
                    await context.followup.send(previous_message)
                    message = new_message
            await context.followup.send(message)
            await self.connection.commit()
        self.lock.release()

    @app_commands.command(description="play_command_desc")
    async def play_command(self, context: discord.Interaction, file: discord.Attachment=None, song_url: str=None, new_name: str=None):
        await context.response.defer()
        if file is None and song_url is not None: await self.play_song(context, song_url, new_name)
        elif file is not None and song_url is None: await self.play_song(context, str(file), new_name)
        else:
            await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
            await context.followup.send(self.guilds[str(context.guild.id)]["strings"]["invalid_command"], ephemeral=True)

    async def play_song(self, context, url=None, name=None, playlist=None):
        try:
            async def add_time(guild, time): guild["time"] += time
            guild = self.guilds[str(context.guild.id)]
            try: voice_channel = context.user.voice.channel
            except: voice_channel = None
            if voice_channel is None:
                await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
                await context.followup.send(await self.polished_message(guild["strings"]["not_in_voice"], {"user": context.user.mention}), ephemeral=True)
            else:
                if url is None:
                    if playlist is None: playlist = []
                    for song in playlist:
                        # add the track to the queue
                        guild["queue"].append({"file": song["file"], "name": song["name"], "time": "0", "duration": song["duration"], "silent": False})
                else:
                    response = requests.get(url, stream=True)
                    try: metadata = await self.get_metadata(BytesIO(response.content), url)
                    except:
                        await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
                        await context.followup.send(await self.polished_message(guild["strings"]["invalid_url"], {"url": url}), ephemeral=True)
                        return
                    if name is None: name = metadata["name"]
                    
                    # verify that the URL file is a media container
                    if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                        await context.followup.delete_message((await context.followup.send("...", silent=True)).id)
                        await context.followup.send(await self.polished_message(guild["strings"]["invalid_song"], {"song": await self.polished_song_name(url, name)}),
                                                    ephemeral=True)
                        return
                    await context.followup.send(await self.polished_message(guild["strings"]["queue_add_song"], {"song": await self.polished_song_name(url, name),
                                                                                                                 "index": len(guild["queue"]) + 1}))
                    # add the track to the queue
                    guild["queue"].append({"file": url, "name": name, "time": "0", "duration": metadata["duration"], "silent": False})
                if guild["connected"]: voice = context.guild.voice_client
                else:
                    voice = await voice_channel.connect()
                    guild["connected"] = True
                    await context.guild.change_voice_state(channel=voice_channel, self_mute=False, self_deaf=True)
                if not voice.is_playing():
                    while guild["index"] < len(guild["queue"]):
                        if guild["connected"]:
                            if guild["queue"][guild["index"]]["silent"]: guild["queue"][guild["index"]]["silent"] = False
                            else:
                                await context.channel.send(await self.polished_message(guild["strings"]["now_playing"],
                                                                                       {"song": await self.polished_song_name(guild["queue"][guild["index"]]["file"],
                                                                                                                              guild["queue"][guild["index"]]["name"]),
                                                                                        "index": guild["index"] + 1,
                                                                                        "max": len(guild["queue"])}))
                                guild["time"] = .0
                        # play the track
                        if not voice.is_playing():
                            source = discord.FFmpegPCMAudio(source=guild["queue"][guild["index"]]["file"],
                                                            before_options=f"-re -ss {guild['queue'][guild['index']]['time']}")
                            source.read()
                            voice.play(source)
                            guild["queue"][guild["index"]]["time"] = "0"
                            voice.source = discord.PCMVolumeTransformer(voice.source, volume=1.0)
                            voice.source.volume = guild["volume"]
                        # ensure that the track plays completely or is skipped by command before proceeding
                        while voice.is_playing() or voice.is_paused():
                            await asyncio.sleep(.1)
                            if voice.is_playing(): await add_time(guild, .1)

                        guild["index"] += 1
                        if guild["index"] == len(guild["queue"]):
                            if not guild["repeat"]: await self.stop_music(context)
                            guild["index"] = 0
        except: pass

    @app_commands.command(description="insert_command_desc")
    async def insert_command(self, context: discord.Interaction, file: discord.Attachment=None, song_url: str=None, new_name: str=None, new_index: int=None):
        if file is None and new_index is not None and song_url is not None: await self.insert_song(context, song_url, new_name, new_index)
        elif file is not None and new_index is not None and song_url is None: await self.insert_song(context, str(file), new_name, new_index)
        else: await context.response.send_message(self.guilds[str(context.guild.id)]["strings"]["invalid_command"])

    async def insert_song(self, context, url, name, index, time="0", duration=None, silent=False):
        guild = self.guilds[str(context.guild.id)]
        try: voice_channel = context.user.voice.channel
        except: voice_channel = None
        if voice_channel is None: await context.response.send_message(await self.polished_message(guild["strings"]["not_in_voice"], {"user": context.user.mention}))
        elif 0 < index < len(guild["queue"]) + 2:
            response = requests.get(url, stream=True)
            try:
                if name is None or duration is None:
                    metadata = await self.get_metadata(BytesIO(response.content), url)
                    if name is None: name = metadata["name"]
                    if duration is None: duration = metadata["duration"]
            except:
                await context.response.send_message(await self.polished_message(guild["strings"]["invalid_url"], {"url": url}))
                return
            # verify that the URL file is a media container
            if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                await context.response.send_message(await self.polished_message(guild["strings"]["invalid_song"], {"song": await self.polished_song_name(url, name)}))
                return
            # add the track to the queue
            guild["queue"].insert(index - 1, {"file": url, "name": name, "time": time, "duration": duration, "silent": silent})
            if index - 1 <= guild["index"]: guild["index"] += 1
            if not silent: await context.response.send_message(await self.polished_message(guild["strings"]["queue_insert_song"],
                                                                                           {"song": await self.polished_song_name(url, name), "index": index}))
        else: await context.response.send_message(await self.polished_message(guild["strings"]["invalid_song_number"], {"index": index}))

    @app_commands.command(description="move_command_desc")
    async def move_command(self, context: discord.Interaction, song_index: int, new_index: int):
        guild = self.guilds[str(context.guild.id)]
        if 0 < song_index < len(guild["queue"]) + 1:
            if 0 < new_index < len(guild["queue"]) + 1:
                queue = guild["queue"].copy()
                guild["queue"].remove(queue[song_index - 1])
                guild["queue"].insert(new_index - 1, queue[song_index - 1])
                await context.response.send_message(await self.polished_message(guild["strings"]["queue_move_song"],
                                                                                {"song": await self.polished_song_name(queue[song_index - 1]["file"],
                                                                                                                       queue[song_index - 1]["name"]),
                                                                                 "index": new_index}))
            if song_index - 1 < guild["index"] and new_index - 1 >= guild["index"]: guild["index"] -= 1
            elif song_index - 1 > guild["index"] and new_index - 1 <= guild["index"]: guild["index"] += 1
            elif song_index - 1 == guild["index"] and new_index - 1 != guild["index"]: guild["index"] = new_index - 1
            else: await context.response.send_message(await self.polished_message(guild["strings"]["invalid_song_number"], {"index": new_index}))
        else: await context.response.send_message(await self.polished_message(guild["strings"]["invalid_song_number"], {"index": song_index}))

    @app_commands.command(description="rename_command_desc")
    async def rename_command(self, context: discord.Interaction, song_index: int, new_name: str):
        guild = self.guilds[str(context.guild.id)]
        await context.response.send_message(await self.polished_message(guild["strings"]["queue_rename_song"],
                                                                        {"song": await self.polished_song_name(guild["queue"][song_index - 1]["file"],
                                                                                                               guild["queue"][song_index - 1]["name"]),
                                                                         "index": song_index,
                                                                         "name": new_name}))
        guild["queue"][song_index - 1]["name"] = new_name

    @app_commands.command(description="remove_command_desc")
    async def remove_command(self, context: discord.Interaction, song_index: int): await self.remove_song(context, song_index)

    async def remove_song(self, context, index, silent=False):
        guild = self.guilds[str(context.guild.id)]
        if 0 < index < len(guild["queue"]) + 1:
            if not silent:
                await context.response.send_message(await self.polished_message(guild["strings"]["queue_remove_song"],
                                                                                {"song": await self.polished_song_name(guild["queue"][index - 1]["file"],
                                                                                                                       guild["queue"][index - 1]["name"]),
                                                                                 "index": index}))
            # remove the track from the queue
            guild["queue"].remove(guild["queue"][index - 1])
            # decrement the index of the current track to match its new position in the queue, should the removed track have been before it
            if index - 1 < guild["index"]: guild["index"] -= 1
            # if the removed track is the current track, play the new track in its place in the queue
            elif index - 1 == guild["index"]:
                guild["index"] -= 1
                context.guild.voice_client.stop()
        else: await context.response.send_message(await self.polished_message(guild["strings"]["invalid_song_number"], {"index": index}))

    @move_command.autocomplete("song_index")
    @rename_command.autocomplete("song_index")
    @remove_command.autocomplete("song_index")
    async def song_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[int]]:
        guild = self.guilds[str(context.guild.id)]
        songs = []
        index = 1
        for song in guild["queue"]:
            polished_song_name = await self.polished_message(guild["strings"]["song"], {"song": song["name"], "index": index})
            song["name"] = song["name"][:97 - len(polished_song_name) + len(song["name"])] + "..." if len(polished_song_name) > 100 else song["name"]
            if (current == "" or current.lower() in polished_song_name.lower()) and len(songs) < 25:
                songs.append(app_commands.Choice(name=polished_song_name, value=index))
            index += 1
        return songs

    @app_commands.command(description="skip_command_desc")
    async def skip_command(self, context: discord.Interaction, by: int=1, to: int=None):
        guild = self.guilds[str(context.guild.id)]
        if guild["queue"]:
            if to is None:
                if guild["index"] + by < len(guild["queue"]) and by > 0: guild["index"] += by - 1
                else:
                    await context.response.send_message(guild["strings"]["invalid_command"], ephemeral=True)
                    return
            else:
                if 0 < to <= len(guild["queue"]): guild["index"] = to - 2
                else:
                    await context.response.send_message(guild["strings"]["invalid_command"], ephemeral=True)
                    return
            await context.response.send_message(await self.polished_message(guild["strings"]["now_playing"],
                                                                            {"song": await self.polished_song_name(guild["queue"][guild["index"] + 1]["file"],
                                                                                                                   guild["queue"][guild["index"] + 1]["name"]),
                                                                             "index": guild["index"] + 2,
                                                                             "max": len(guild["queue"])}))
            guild["queue"][guild["index"] + 1]["silent"] = True
            guild["time"] = .0
            context.guild.voice_client.stop()
        else: await context.response.send_message(guild["strings"]["queue_no_songs"], ephemeral=True)

    @app_commands.command(description="previous_command_desc")
    async def previous_command(self, context: discord.Interaction, by: int=1):
        guild = self.guilds[str(context.guild.id)]
        if guild["queue"]:
            if guild["index"] - by >= 0 and by > 0: guild["index"] -= by + 1
            else:
                await context.response.send_message(guild["strings"]["invalid_command"], ephemeral=True)
                return
            await context.response.send_message(await self.polished_message(guild["strings"]["now_playing"],
                                                                            {"song": await self.polished_song_name(guild["queue"][guild["index"] + 1]["file"],
                                                                                                                   guild["queue"][guild["index"] + 1]["name"]),
                                                                             "index": guild["index"] + 2,
                                                                             "max": len(guild["queue"])}))
            guild["queue"][guild["index"] + 1]["silent"] = True
            guild["time"] = .0
            context.guild.voice_client.stop()
        else: await context.response.send_message(guild["strings"]["queue_no_songs"], ephemeral=True)

    @app_commands.command(description="stop_command_desc")
    async def stop_command(self, context: discord.Interaction):
        await context.response.send_message(self.guilds[str(context.guild.id)]["strings"]["stop"])
        await self.stop_music(context)

    async def stop_music(self, context, leave=False, guild=None):
        if guild is None: id = context.guild.id
        else: id = guild.id
        guild = self.guilds[str(id)]
        guild["queue"] = []
        try:
            if context.guild.voice_client.is_playing():
                guild["index"] = -1
                context.guild.voice_client.stop()
            else: guild["index"] = 0
            if leave or not guild["keep"]:
                guild["connected"] = False
                await context.guild.voice_client.disconnect()
        except:
            guild["index"] = 0
            guild["connected"] = False
            await context.guild.voice_client.cleanup()

    @app_commands.command(description="pause_command_desc")
    async def pause_command(self, context: discord.Interaction):
        guild = self.guilds[str(context.guild.id)]
        if guild["queue"]:
            if context.guild.voice_client.is_paused():
                context.guild.voice_client.resume()
                now_or_no_longer = guild["strings"]["no_longer"]
            else:
                context.guild.voice_client.pause()
                now_or_no_longer = guild["strings"]["now"]
            await context.response.send_message(await self.polished_message(guild["strings"]["pause"], {"now_or_no_longer": now_or_no_longer}))
        else: await context.response.send_message(guild["strings"]["queue_no_songs"], ephemeral=True)

    @app_commands.command(description="jump_command_desc")
    async def jump_command(self, context: discord.Interaction, time: str): await self.jump_to(context, time)

    async def jump_to(self, context, time):
        seconds = await self.convert_to_seconds(time)
        guild = self.guilds[str(context.guild.id)]
        if guild["queue"]:
            await context.response.send_message(await self.polished_message(guild["strings"]["jump"],
                                                                            {"time": await self.convert_to_time(seconds),
                                                                             "song": await self.polished_song_name(guild["queue"][guild["index"]]["file"],
                                                                                                                   guild["queue"][guild["index"]]["name"]),
                                                                             "index": guild["index"] + 1,
                                                                             "max": len(guild["queue"])}))
            guild["time"] = seconds
            await self.insert_song(context,
                                   guild["queue"][guild["index"]]["file"],
                                   guild["queue"][guild["index"]]["name"],
                                   guild["index"] + 2,
                                   seconds,
                                   guild["queue"][guild["index"]]["duration"],
                                   True)
            await self.remove_song(context, guild["index"] + 1, True)
        else: await context.response.send_message(guild["strings"]["queue_no_songs"], ephemeral=True)

    @app_commands.command(description="forward_command_desc")
    async def forward_command(self, context: discord.Interaction, time: str):
        await self.jump_to(context, str(float(self.guilds[str(context.guild.id)]["time"]) + await self.convert_to_seconds(time)))

    @app_commands.command(description="rewind_command_desc")
    async def rewind_command(self, context: discord.Interaction, time: str):
        await self.jump_to(context, str(float(self.guilds[str(context.guild.id)]["time"]) - await self.convert_to_seconds(time)))

    @app_commands.command(description="when_command_desc")
    async def when_command(self, context: discord.Interaction):
        guild = self.guilds[str(context.guild.id)]
        if guild["queue"]: await context.response.send_message("".join([await self.convert_to_time(guild["time"]),
                                                                        " / ",
                                                                        await self.convert_to_time(guild["queue"][guild["index"]]["duration"])]),
                                                               ephemeral=True)
        else: await context.response.send_message(guild["strings"]["queue_no_songs"], ephemeral=True)

    @app_commands.command(description="loop_command_desc")
    async def loop_command(self, context: discord.Interaction, set: typing.Literal[0, 1]=None):
        await self.lock.acquire()
        strings = self.guilds[str(context.guild.id)]["strings"]
        if set is None:
            await context.response.send_message(await self.polished_message(strings["repeat"],
                                                                            {"do_not": "" if self.guilds[str(context.guild.id)]["repeat"] else strings["do_not"]}),
                                                ephemeral=True)
            self.lock.release()
            return
        else:
            repeat = bool(set)
            if self.cursor is None:
                for guild in self.data["guilds"]:
                    if guild["id"] == context.guild.id:
                        guild["repeat"] = repeat
                        # modify the flat file for guilds to reflect the change of whether playlists repeat
                        yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)

                        self.guilds[str(context.guild.id)]["repeat"] = repeat
                        break
            else:
                await self.cursor.execute("update guilds set repeat_queue = ? where guild_id = ?", (repeat, context.guild.id))
                await self.connection.commit()
                self.guilds[str(context.guild.id)]["repeat"] = repeat
        await context.response.send_message(await self.polished_message(strings["repeat_change"],
                                                                        {"now_or_no_longer": strings["now"] if repeat else strings["no_longer"]}))
        self.lock.release()

    @app_commands.command(description="shuffle_command_desc")
    async def shuffle_command(self, context: discord.Interaction, restart: typing.Literal[0, 1]=1):
        guild = self.guilds[str(context.guild.id)]
        if guild["queue"]:
            index = 0
            while index < len(guild["queue"]):
                temp_index = random.randint(0, len(guild["queue"]) - 1)
                temp_song = guild["queue"][index]
                guild["queue"][index] = guild["queue"][temp_index]
                guild["queue"][temp_index] = temp_song
                if index == guild["index"]: guild["index"] = temp_index
                index += 1
            await context.response.send_message(guild["strings"]["shuffle"])
            if bool(restart):
                guild["index"] = -1
                context.guild.voice_client.stop()
        else: await context.response.send_message(guild["strings"]["queue_no_songs"], ephemeral=True)

    @app_commands.command(description="queue_command_desc")
    async def queue_command(self, context: discord.Interaction):
        await context.response.defer(ephemeral=True)
        guild = self.guilds[str(context.guild.id)]
        message = guild["strings"]["queue_songs_header"] + "\n"
        if not guild["queue"]:
            await context.followup.send(guild["strings"]["queue_no_songs"])
            return
        pages = []
        index = 0
        while index < len(guild["queue"]):
            previous_message = message
            new_message = await self.polished_message(guild["strings"]["song"] + "\n",
                                                      {"song": await self.polished_song_name(guild["queue"][index]["file"], guild["queue"][index]["name"]),
                                                       "index": index + 1})
            message += new_message
            if len(message) > 2000:
                pages.append(previous_message)
                message = guild["strings"]["queue_songs_header"] + "\n" + new_message
            index += 1
        pages.append(message)
        await self.page_selector(context, guild["strings"], pages, 0)

    @app_commands.command(description="what_command_desc")
    async def what_command(self, context: discord.Interaction):
        guild = self.guilds[str(context.guild.id)]
        if guild["queue"]:
            await context.response.send_message(await self.polished_message(guild["strings"]["now_playing"],
                                                                            {"song": await self.polished_song_name(guild["queue"][guild["index"]]["file"],
                                                                                                                   guild["queue"][guild["index"]]["name"]),
                                                                             "index": guild["index"] + 1,
                                                                             "max": len(guild["queue"])}),
                                                ephemeral=True)
        else: await context.response.send_message(guild["strings"]["queue_no_songs"], ephemeral=True)

    @app_commands.command(description="volume_command_desc")
    async def volume_command(self, context: discord.Interaction, set: str=None):
        guild = self.guilds[str(context.guild.id)]
        if set is not None:
            if set.endswith("%"): guild["volume"] = float(set.replace("%", "")) / 100
            else: guild["volume"] = float(set)
            if context.guild.voice_client is not None and context.guild.voice_client.is_playing(): context.guild.voice_client.source.volume = guild["volume"]
        volume_percent = guild["volume"] * 100
        if volume_percent == float(int(volume_percent)): volume_percent = int(volume_percent)
        if set is None: await context.response.send_message(await self.polished_message(guild["strings"]["volume"], {"volume": str(volume_percent) + "%"}),
                                                            ephemeral=True)
        else: await context.response.send_message(await self.polished_message(guild["strings"]["volume_change"], {"volume": str(volume_percent) + "%"}))

    @app_commands.command(description="keep_command_desc")
    async def keep_command(self, context: discord.Interaction, set: typing.Literal[0, 1]=None):
        await self.lock.acquire()
        strings = self.guilds[str(context.guild.id)]["strings"]
        try: voice_channel = context.user.voice.channel.jump_url
        except: voice_channel = strings["whatever_voice"]
        if set is None:
            await context.response.send_message(await self.polished_message(strings["keep"],
                                                                            {"bot": self.bot.user.mention,
                                                                             "voice": voice_channel,
                                                                             "stay_in_or_leave": strings["stay_in"]
                                                                                                 if self.guilds[str(context.guild.id)]["keep"]
                                                                                                 else strings["leave"]}),
                                                ephemeral=True)
            self.lock.release()
            return
        else:
            keep = bool(set)
            if self.cursor is None:
                for guild in self.data["guilds"]:
                    if guild["id"] == context.guild.id:
                        guild["keep"] = keep
                        # modify the flat file for guilds to reflect the change of whether to keep this bot in a voice call when no audio is playing
                        yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)

                        self.guilds[str(context.guild.id)]["keep"] = keep
                        break
            else:
                await self.cursor.execute("update guilds set keep_in_voice = ? where guild_id = ?", (keep, context.guild.id))
                await self.connection.commit()
                self.guilds[str(context.guild.id)]["keep"] = keep
        await context.response.send_message(await self.polished_message(strings["keep_change"], {"bot": self.bot.user.mention,
                                                                                                 "voice": voice_channel,
                                                                                                 "now_or_no_longer": strings["now"] if keep else strings["no_longer"]}))
        self.lock.release()

    @app_commands.command(description="recruit_command_desc")
    async def recruit_command(self, context: discord.Interaction):
        guild = self.guilds[str(context.guild.id)]
        try: voice_channel = context.user.voice.channel
        except:
            await context.response.send_message(await self.polished_message(guild["strings"]["not_in_voice"], {"user": context.user.mention}))
            return
        if guild["connected"]:
            await context.response.send_message("...", ephemeral=True)
            await context.delete_original_response()
        else:
            await context.response.send_message(await self.polished_message(guild["strings"]["recruit_or_dismiss"],
                                                                            {"bot": self.bot.user.mention,
                                                                             "voice": voice_channel.jump_url,
                                                                             "now_or_no_longer": guild["strings"]["now"]}))
            await voice_channel.connect()
            guild["connected"] = True
            await context.guild.change_voice_state(channel=voice_channel, self_mute=False, self_deaf=True)

    @app_commands.command(description="dismiss_command_desc")
    async def dismiss_command(self, context: discord.Interaction):
        guild = self.guilds[str(context.guild.id)]
        try: voice_channel = context.user.voice.channel
        except:
            await context.response.send_message(await self.polished_message(guild["strings"]["not_in_voice"], {"user": context.user.mention}))
            return
        if guild["connected"]:
            await context.response.send_message(await self.polished_message(guild["strings"]["recruit_or_dismiss"], {"bot": self.bot.user.mention,
                                                                                                                     "voice": voice_channel.jump_url,
                                                                                                                     "now_or_no_longer": guild["strings"]["no_longer"]}))
            await self.stop_music(context, True)
        else:
            await context.response.send_message("...", ephemeral=True)
            await context.delete_original_response()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            # ensure that this bot disconnects from any empty voice channel it is in
            if member.guild.voice_client.is_connected():
                for voice_channel in member.guild.voice_channels:
                    if voice_channel.voice_states and list(voice_channel.voice_states)[0] == self.bot.user.id and len(list(voice_channel.voice_states)) == 1:
                        await self.stop_music(member, True, member.guild)
                        break
            # ensure that this bot's connected status and the queue are reset if it is not properly disconnected
            elif member.id == self.bot.user.id:
                guild = self.guilds[str(member.guild.id)]
                if guild["connected"]:
                    guild["index"] = 0
                    guild["queue"] = []
                    guild["connected"] = False
                    member.guild.voice_client.cleanup()
        except: pass

    @app_commands.command(description="working_thread_command_desc")
    async def working_thread_command(self, context: discord.Interaction, set: str=None):
        await self.lock.acquire()
        strings = self.guilds[str(context.guild.id)]["strings"]
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == context.guild.id:
                    if set is None:
                        try: await context.response.send_message(await self.polished_message(strings["working_thread"],
                                                                                             {"bot": self.bot.user.mention,
                                                                                              "thread": self.bot.get_guild(guild["id"])
                                                                                                                .get_thread(guild["working_thread_id"])
                                                                                                                .jump_url}),
                                                                 ephemeral=True)
                        except: await context.response.send_message(await self.polished_message(strings["working_thread_not_assigned"], {"bot": self.bot.user.mention}),
                                                                    ephemeral=True)
                        break
                    thread_nonexistent = True
                    for thread in context.guild.threads:
                        if set == thread.name:
                            guild["working_thread_id"] = thread.id
                            yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
                            await context.response.send_message(await self.polished_message(strings["working_thread_change"], {"bot": self.bot.user.mention,
                                                                                                                               "thread": thread.jump_url}))
                            thread_nonexistent = False
                            break
                    if thread_nonexistent: await context.response.send_message(strings["invalid_command"])
                    break
        else:
            if set is None:
                await self.cursor.execute("select working_thread_id from guilds where guild_id = ?", (context.guild.id,))
                working_thread_id = (await self.cursor.fetchone())[0]
                try: await context.response.send_message(await self.polished_message(strings["working_thread"],
                                                                                     {"bot": self.bot.user.mention,
                                                                                      "thread": self.bot.get_guild(context.guild.id)
                                                                                                        .get_thread(working_thread_id)
                                                                                                        .jump_url}),
                                                         ephemeral=True)
                except: await context.response.send_message(await self.polished_message(strings["working_thread_not_assigned"], {"bot": self.bot.user.mention}))
            thread_nonexistent = True
            for thread in context.guild.threads:
                if set == thread.name:
                    await self.cursor.execute("update guilds set working_thread_id = ? where guild_id = ?", (thread.id, context.guild.id))
                    await self.connection.commit()
                    await context.response.send_message(await self.polished_message(strings["working_thread_change"], {"bot": self.bot.user.mention,
                                                                                                                       "thread": thread.jump_url}))
                    thread_nonexistent = False
                    break
            if thread_nonexistent: await context.response.send_message(strings["invalid_command"])
        self.lock.release()

    @working_thread_command.autocomplete("set")
    async def working_thread_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        threads = []
        for thread in context.guild.threads:
            if (current == "" or current.lower() in thread.name.lower()) and len(threads) < 25: threads.append(app_commands.Choice(name=thread.name, value=thread.name))
        return threads

    async def renew_attachment(self, guild_id, channel_id, playlist_index, song_index, url, song_id=None):
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == guild_id:
                    try: working_thread_id = guild["working_thread_id"]
                    except: working_thread_id = channel_id
                    await self.bot.get_guild(guild_id).get_thread(working_thread_id).send(yaml.safe_dump({"playlist_index": playlist_index, "song_index": song_index}),
                                                                                          file=discord.File(BytesIO(requests.get(url).content),
                                                                                                            await self.get_file_name(url)))
                    break
        else:
            await self.lock.acquire()
            await self.cursor.execute("select working_thread_id from guilds where guild_id = ?", (guild_id,))
            try: working_thread_id = (await self.cursor.fetchone())[0]
            except: working_thread_id = channel_id
            self.lock.release()
            await self.bot.get_guild(guild_id).get_thread(working_thread_id).send(yaml.safe_dump({"song_id": song_id}),
                                                                                  file=discord.File(BytesIO(requests.get(url).content), await self.get_file_name(url)))

    @commands.Cog.listener("on_message")
    async def renew_attachment_from_message(self, message: discord.Message):
        try:
            if message.author.id == self.bot.user.id:
                content = yaml.safe_load(message.content)
                if str(content["song_id"]):
                    if self.cursor is None:
                        for guild in self.data["guilds"]:
                            if guild["id"] == message.guild.id:
                                guild["playlists"][content["playlist_index"]]["songs"][content["song_index"]]["channel_id"] = message.channel.id
                                guild["playlists"][content["playlist_index"]]["songs"][content["song_index"]]["message_id"] = message.id
                                break
                        yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
                    else:
                        await self.lock.acquire()
                        await self.cursor.execute("select working_thread_id from guilds where guild_id = ?", (message.guild.id,))
                        await self.cursor.execute("update songs set channel_id = ? where song_id = ?", (message.channel.id, content["song_id"]))
                        await self.cursor.execute("update songs set message_id = ? where song_id = ?", (message.id, content["song_id"]))
                        await self.connection.commit()
                        self.lock.release()
        except: pass

async def setup(bot): await bot.add_cog(Music(bot))
