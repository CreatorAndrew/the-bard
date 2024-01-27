import os
import requests
import yaml
import asyncio
import typing
import random
import discord
from discord import app_commands
from discord.ext import commands
from subprocess import check_output

class Music(commands.Cog):
    def __init__(self, bot, flat_file, data, language_directory, lock):
        self.bot = bot
        self.flat_file = flat_file
        self.data = data
        self.language_directory = language_directory
        self.music_directory = "Media"
        self.lock = lock
        self.guilds = []
        self.playlist_add_files_context_menu = app_commands.ContextMenu(name="playlist_add_files_context_menu", callback=self.playlist_add_files)
        self.bot.tree.add_command(self.playlist_add_files_context_menu)

    def get_file_name(self, file):
        try: return file[file.rindex("/") + 1:file.rindex("?")]
        except: return file[file.rindex("/") + 1:]

    def get_metadata(self, file):
        for track in yaml.safe_load(check_output(["mediainfo", "--output=JSON", file]).decode("utf-8"))["media"]["track"]:
            try: name = track["Title"]
            except:
                try: name = track["Track"]
                except:
                    name = self.get_file_name(file)
                    try: name = name[:name.rindex(".")].replace("_", " ")
                    except: name = name.replace("_", " ")
            try: duration = float(track["Duration"])
            except: duration = .0
            return {"name": name, "duration": duration}

    def polished_song_name(self, file, name):
        index = 0
        while index <= 9:
            if f"{index}. " in name:
                return f"[{name[:name.index(f'{index}. ') + len(f'{index}. ')]}](<{file}>)" + f"[{name[name.index(f'{index}. ') + len(f'{index}. '):]}](<{file}>)"
            index += 1
        return f"[{name}](<{file}>)"

    def polished_message(self, message, placeholders, replacements):
        for placeholder in placeholders:
            replacement = replacements[placeholder]
            message = message.replace("%{" + placeholder + "}", str(replacement))
        return message

    def convert_to_time(self, number):
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

    def convert_to_seconds(self, time):
        segments = []
        if ":" in time: segments = time.split(":")
        if len(segments) == 2: seconds = float(segments[0]) * 60 + float(segments[1])
        elif len(segments) == 3: seconds = float(segments[0]) * 3600 + float(segments[1]) * 60 + float(segments[2])
        else: seconds = float(time)
        return seconds

    def init_guilds(self, set_languages=True):
        # add all guilds with this bot to memory that were not already
        if len(self.guilds) < len(self.data["guilds"]):
            ids = []
            for guild in self.data["guilds"]:
                for guild_searched in self.guilds: ids.append(guild_searched["id"])
                if guild["id"] not in ids: self.guilds.append({"id": guild["id"],
                                                               "strings": yaml.safe_load(open(f"{self.language_directory}/{guild['language']}.yaml", "r"))["strings"],
                                                               "repeat": guild["repeat"],
                                                               "keep": guild["keep"],
                                                               "queue": [],
                                                               "index": 0,
                                                               "time": .0,
                                                               "volume": 1.0,
                                                               "connected": False})
        # remove any guilds from memory that had removed this bot
        elif len(self.guilds) > len(self.data["guilds"]):
            index = 0
            while index < len(self.guilds):
                try:
                    if self.guilds[index]["id"] != self.data["guilds"][index]["id"]:
                        self.guilds.remove(self.guilds[index])
                        index -= 1
                except: self.guilds.remove(self.guilds[index])
                index += 1

        if set_languages:
            for guild in self.data["guilds"]:
                self.guilds[self.data["guilds"].index(guild)]["strings"] = yaml.safe_load(open(f"{self.language_directory}/{guild['language']}.yaml", "r"))["strings"]

    # return a list of playlists for the calling guild
    @app_commands.command(description="playlists_command_desc")
    async def playlists_command(self, context: discord.Interaction):
        await context.response.defer()
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                message = ""
                if self.data["guilds"][self.guilds.index(guild)]["playlists"]: message += guild["strings"]["playlists_header"] + "\n"
                else:
                    await context.followup.send(guild["strings"]["no_playlists"])
                    return
                index = 0
                while index < len(self.data["guilds"][self.guilds.index(guild)]["playlists"]):
                    previous_message = message
                    new_message = self.polished_message(guild["strings"]["playlist"] + "\n",
                                                        ["playlist", "playlist_index"],
                                                        {"playlist": self.data["guilds"][self.guilds.index(guild)]["playlists"][index]["name"], "playlist_index": index + 1})
                    message += new_message
                    if len(message) > 2000:
                        await context.followup.send(previous_message)
                        message = new_message
                    index += 1
                await context.followup.send(message)
                break

    @app_commands.command(description="playlist_command_desc")
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
        await context.response.defer()
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                strings = guild["strings"]
                break
        if select is not None and action == "add":
            if file is None and song_url is not None: url = song_url
            elif file is not None and song_url is None: url = str(file)
            else:
                await context.followup.send(strings["invalid_command"])
                return
            try: metadata = self.get_metadata(url)
            except:
                await context.followup.send(self.polished_message(strings["invalid_url"], ["url"], {"url": url}))
                self.lock.release()
                return
            response = requests.get(url, stream=True)
            # verify that the URL file is a media container
            if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                await context.followup.send(self.polished_message(strings["invalid_song"], ["song"], {"song": self.polished_song_name(url, song["name"])}))
                return
        await self.lock.acquire()
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                # add a playlist
                if add is not None and select is None:
                    if new_index is None: new_index = len(guild["playlists"]) + 1
                    guild["playlists"].insert(new_index - 1, {"name": add, "songs": []})
                    await context.followup.send(self.polished_message(strings["add_playlist"],
                                                                      ["playlist", "playlist_index"],
                                                                      {"playlist": add, "playlist_index": new_index}))
                # clone a playlist or copy its tracks into another playlist
                elif clone is not None and select is None:
                    # clone a playlist
                    if into is None:
                        if new_name is None: new_name = guild["playlists"][clone - 1]["name"]
                        if new_index is None: new_index = len(guild["playlists"]) + 1
                        guild["playlists"].insert(new_index - 1, {"name": new_name, "songs": guild["playlists"][clone - 1]["songs"].copy()})
                        await context.followup.send(self.polished_message(strings["clone_playlist"],
                                                                          ["playlist", "playlist_index", "into_playlist", "into_playlist_index"],
                                                                          {"playlist": guild["playlists"][clone - 1]["name"],
                                                                           "playlist_index": clone,
                                                                           "into_playlist": new_name,
                                                                           "into_playlist_index": new_index}))
                    # copy a playlist's tracks into another playlist
                    else:
                        guild["playlists"][into - 1]["songs"] += guild["playlists"][clone - 1]["songs"]
                        await context.followup.send(self.polished_message(strings["clone_playlist"],
                                                                          ["playlist", "playlist_index", "into_playlist", "into_playlist_index"],
                                                                          {"playlist": guild["playlists"][clone - 1]["name"],
                                                                           "playlist_index": clone,
                                                                           "into_playlist": guild["playlists"][into - 1]["name"],
                                                                           "into_playlist_index": into}))
                # change a playlist's position in the order of playlists
                elif move is not None and select is None:
                    if new_index is None or new_index > len(guild["playlists"]) or new_index < 1:
                        await context.followup.send(strings["invalid_command"])
                        self.lock.release()
                        return
                    playlists = guild["playlists"].copy()
                    guild["playlists"].remove(playlists[move - 1])
                    guild["playlists"].insert(new_index - 1, playlists[move - 1])
                    await context.followup.send(self.polished_message(strings["move_playlist"],
                                                                      ["playlist", "playlist_index"],
                                                                      {"playlist": playlists[move - 1]["name"], "playlist_index": new_index}))
                # rename a playlist
                elif rename is not None and select is None:
                    if new_name is None:
                        await context.followup.send(strings["invalid_command"])
                        self.lock.release()
                        return
                    else:
                        await context.followup.send(self.polished_message(strings["rename_playlist"],
                                                                          ["playlist", "playlist_index", "name"],
                                                                          {"playlist": guild["playlists"][rename - 1]["name"],
                                                                           "playlist_index": rename, "name": new_name}))
                        guild["playlists"][rename - 1]["name"] = new_name
                # remove a playlist
                elif remove is not None and select is None:
                    await context.followup.send(self.polished_message(strings["remove_playlist"],
                                                                      ["playlist", "playlist_index"],
                                                                      {"playlist": guild["playlists"][remove - 1]["name"], "playlist_index": remove}))
                    guild["playlists"].remove(guild["playlists"][remove - 1])
                # load a playlist
                elif load is not None and select is None:
                    self.lock.release()
                    if guild["playlists"][load - 1]["songs"]: await self.play_song(context, playlist=guild["playlists"][load - 1]["songs"])
                    else: await context.followup.send(self.polished_message(strings["playlist_no_songs"],
                                                                            ["playlist", "playlist_index"],
                                                                            {"playlist": guild["playlists"][load - 1]["name"], "playlist_index": load}))
                    return
                # select a playlist to modify or show the contents of
                elif select is not None and add is None and clone is None and move is None and rename is None and remove is None and load is None:
                    if select > 0 and select <= len(guild["playlists"]):
                        # add a track to the playlist
                        if action == "add":
                            if new_name is None: new_name = metadata["name"]
                            if new_index is None: new_index = len(guild["playlists"][select - 1]["songs"]) + 1
                            song = {"name": new_name, "index": new_index, "duration": metadata["duration"]}
                            guild["playlists"][select - 1]["songs"].insert(song["index"] - 1, {"file": url, "name": song["name"], "duration": song["duration"]})
                            await context.followup.send(self.polished_message(strings["playlist_add_song"],
                                                                              ["playlist", "playlist_index", "song", "index"],
                                                                              {"playlist": guild["playlists"][select - 1]["name"],
                                                                               "playlist_index": select,
                                                                               "song": self.polished_song_name(url, song["name"]),
                                                                               "index": song["index"]}))
                            if file is not None: await self.renew_attachment(guild["id"], select - 1, song["index"] - 1)
                        # change the position of a track within the playlist
                        elif action == "move":
                            if song_index is None or new_index is None:
                                await context.followup.send(strings["invalid_command"])
                                self.lock.release()
                                return
                            else:
                                song = guild["playlists"][select - 1]["songs"][int(song_index) - 1]
                                guild["playlists"][select - 1]["songs"].remove(song)
                                guild["playlists"][select - 1]["songs"].insert(new_index - 1, song)
                                await context.followup.send(self.polished_message(strings["playlist_move_song"],
                                                                                  ["playlist", "playlist_index", "song", "index"],
                                                                                  {"playlist": guild["playlists"][select - 1]["name"],
                                                                                   "playlist_index": select,
                                                                                   "song": self.polished_song_name(song["file"], song["name"]),
                                                                                   "index": new_index}))
                        # rename a track in the playlist
                        elif action == "rename":
                            if song_index is None or new_name is None:
                                await context.followup.send(strings["invalid_command"])
                                self.lock.release()
                                return
                            else:
                                song = guild["playlists"][select - 1]["songs"][int(song_index) - 1]
                                await context.followup.send(self.polished_message(strings["playlist_rename_song"],
                                                                                  ["playlist", "playlist_index", "song", "index", "name"],
                                                                                  {"playlist": guild["playlists"][select - 1]["name"],
                                                                                   "playlist_index": select,
                                                                                   "song": self.polished_song_name(song["file"], song["name"]),
                                                                                   "index": song_index,
                                                                                   "name": new_name}))
                                song["name"] = new_name
                        # remove a track from the playlist
                        elif action == "remove":
                            if song_index is None:
                                await context.followup.send(strings["invalid_command"])
                                self.lock.release()
                                return
                            else:
                                song = guild["playlists"][select - 1]["songs"][int(song_index) - 1]
                                guild["playlists"][select - 1]["songs"].remove(song)
                                await context.followup.send(self.polished_message(strings["playlist_remove_song"],
                                                                                  ["playlist", "playlist_index", "song", "index"],
                                                                                  {"playlist": guild["playlists"][select - 1]["name"],
                                                                                   "playlist_index": select,
                                                                                   "song": self.polished_song_name(song["file"], song["name"]),
                                                                                   "index": song_index}))
                        # return a list of tracks in the playlist
                        elif action == "list":
                            message = ""
                            if guild["playlists"][select - 1]["songs"]:
                                if guild["playlists"][select - 1]:
                                    message += self.polished_message(strings["playlist_songs_header"] + "\n",
                                                                     ["playlist", "playlist_index"],
                                                                     {"playlist": guild["playlists"][select - 1]["name"], "playlist_index": select})
                                else:
                                    await context.followup.send(strings["no_playlists"])
                                    self.lock.release()
                                    return
                            else:
                                await context.followup.send(self.polished_message(strings["playlist_no_songs"],
                                                                                  ["playlist", "playlist_index"],
                                                                                  {"playlist": guild["playlists"][select - 1]["name"], "playlist_index": select}))
                                self.lock.release()
                                return
                            index = 0
                            while index < len(guild["playlists"][select - 1]["songs"]):
                                previous_message = message
                                new_message = self.polished_message(strings["song"] + "\n",
                                                                    ["song", "index"],
                                                                    {"song": self.polished_song_name(guild["playlists"][select - 1]["songs"][index]["file"],
                                                                                                     guild["playlists"][select - 1]["songs"][index]["name"]),
                                                                     "index": index + 1})
                                message += new_message
                                if len(message) > 2000:
                                    await context.followup.send(previous_message)
                                    message = new_message
                                index += 1
                            await context.followup.send(message)
                            self.lock.release()
                            return
                        else:
                            await context.followup.send(strings["invalid_command"])
                            self.lock.release()
                            return
                    else:
                        context.followup.send(strings["invalid_playlist_number"])
                        self.lock.release()
                        return
                else:
                    await context.followup.send(strings["invalid_command"])
                    self.lock.release()
                    return
                # modify the flat file for guilds to reflect changes regarding playlists
                yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)

                break
        self.lock.release()

    @playlist_command.autocomplete("clone")
    @playlist_command.autocomplete("into")
    @playlist_command.autocomplete("move")
    @playlist_command.autocomplete("rename")
    @playlist_command.autocomplete("remove")
    @playlist_command.autocomplete("load")
    @playlist_command.autocomplete("select")
    async def playlist_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[int]]:
        self.init_guilds(False)
        playlists = []
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                index = 1
                for playlist in guild["playlists"]:
                    polished_playlist_name = self.polished_message(self.guilds[self.data["guilds"].index(guild)]["strings"]["playlist"],
                                                                   ["playlist", "playlist_index"],
                                                                   {"playlist": playlist["name"], "playlist_index": index})
                    playlist["name"] = playlist["name"][:97 - len(polished_playlist_name) + len(playlist["name"])] + "..." if len(polished_playlist_name) > 100 else playlist["name"]
                    if (current == "" or current.lower() in polished_playlist_name.lower()) and len(playlists) < 25:
                        playlists.append(app_commands.Choice(name=polished_playlist_name, value=index))
                    index += 1
                break
        return playlists

    @playlist_command.autocomplete("action")
    async def playlist_action_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        self.init_guilds(False)
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                action_options = [app_commands.Choice(name=guild["strings"]["add"], value="add"),
                                  app_commands.Choice(name=guild["strings"]["move"], value="move"),
                                  app_commands.Choice(name=guild["strings"]["rename"], value="rename"),
                                  app_commands.Choice(name=guild["strings"]["remove"], value="remove"),
                                  app_commands.Choice(name=guild["strings"]["list"], value="list")]
                break
        actions = []
        for action in action_options:
            if current == "" or current.lower() in action.name.lower(): actions.append(action)
        return actions

    @playlist_command.autocomplete("song_index")
    async def playlist_song_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[int]]:
        self.init_guilds(False)
        songs = []
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                try:
                    index = 1
                    for song in guild["playlists"][context.namespace.select - 1]["songs"]:
                        polished_song_name = self.polished_message(self.guilds[self.data["guilds"].index(guild)]["strings"]["song"],
                                                                   ["song", "index"],
                                                                   {"song": song["name"], "index": index})
                        song["name"] = song["name"][:97 - len(polished_song_name) + len(song["name"])] + "..." if len(polished_song_name) > 100 else song["name"]
                        if (current == "" or current.lower() in polished_song_name.lower()) and len(songs) < 25:
                            songs.append(app_commands.Choice(name=polished_song_name, value=index))
                        index += 1
                except: pass
                break
        return songs

    async def playlist_add_files(self, context: discord.Interaction, message_regarded: discord.Message):
        await context.response.defer()
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                strings = guild["strings"]
                # show a dropdown menu of all the playlists for the calling guild
                playlist_options = [discord.SelectOption(label=strings["cancel_option"])]
                index = 1
                for playlist in self.data["guilds"][self.guilds.index(guild)]["playlists"]:
                    playlist_options.append(discord.SelectOption(label=self.polished_message(strings["playlist"],
                                                                                             ["playlist", "playlist_index"],
                                                                                             {"playlist": playlist["name"], "playlist_index": index}),
                                                                 value=str(index)))
                    index += 1
                playlist_menu = discord.ui.Select(placeholder=strings["playlist_select_menu_placeholder"], options=playlist_options)
                chosen = []
                async def playlist_callback(context):
                    await context.response.send_message("...")
                    await context.delete_original_response()
                    chosen.append(playlist_menu.values[0])
                playlist_menu.callback = playlist_callback
                view = discord.ui.View()
                view.add_item(playlist_menu)
                await context.followup.send("", view=view)
                while not chosen: await asyncio.sleep(.1)
                if chosen[0] == strings["cancel_option"]: return
                index = int(chosen[0])

                break
        playlist = []
        for url in message_regarded.attachments:
            try: song = self.get_metadata(str(url))
            except:
                await context.followup.send(self.polished_message(strings["invalid_url"], ["url"], {"url": str(url)}))
                return
            response = requests.get(str(url), stream=True)
            # verify that the URL file is a media container
            if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                await context.followup.send(self.polished_message(strings["invalid_song"], ["song"], {"song": self.polished_song_name(str(url), song["name"])}))
                return

            playlist.append({"file": str(url), "name": song["name"], "duration": song["duration"]})
        await self.lock.acquire()
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                message = ""
                for song in playlist:
                    guild["playlists"][index - 1]["songs"].append({"file": song["file"], "name": song["name"], "duration": song["duration"]})
                    previous_message = message
                    new_message = self.polished_message(strings["playlist_add_song"] + "\n",
                                                        ["playlist", "playlist_index", "song", "index"],
                                                        {"playlist": guild["playlists"][index - 1]["name"],
                                                         "playlist_index": index,
                                                         "song": self.polished_song_name(song["file"], song["name"]),
                                                         "index": len(guild["playlists"][index - 1]["songs"])})
                    message += new_message
                    if len(message) > 2000:
                        await context.followup.send(previous_message)
                        message = new_message
                await context.followup.send(message)
                break
        yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
        self.lock.release()

    @app_commands.command(description="play_command_desc")
    async def play_command(self, context: discord.Interaction, file: discord.Attachment=None, song_url: str=None, new_name: str=None):
        await context.response.defer()
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if file is None and song_url is not None: await self.play_song(context, song_url, new_name)
                elif file is not None and song_url is None: await self.play_song(context, str(file), new_name)
                else: await context.followup.send(guild["strings"]["invalid_command"])
                break

    async def play_song(self, context, url=None, name=None, playlist=[]):
        try:
            async def add_time(guild, time): guild["time"] += time
            for guild in self.guilds:
                if guild["id"] == context.guild.id:
                    try: voice_channel = context.user.voice.channel
                    except: voice_channel = None
                    if voice_channel is None:
                        await context.followup.send(self.polished_message(guild["strings"]["not_in_voice"], ["user"], {"user": context.user.mention}))
                    else:
                        if url is None:
                            message = ""
                            for song in playlist:
                                previous_message = message
                                new_message = self.polished_message(guild["strings"]["queue_add_song"] + "\n",
                                                                    ["song", "index"],
                                                                    {"song": self.polished_song_name(song["file"], song["name"]), "index": len(guild["queue"]) + 1})
                                message += new_message
                                if len(message) > 2000:
                                    await context.followup.send(previous_message)
                                    message = new_message
                                # add the track to the queue
                                guild["queue"].append({"file": song["file"], "name": song["name"], "time": "0", "duration": song["duration"], "silence": False})
                            await context.followup.send(message)
                        else:
                            try: metadata = self.get_metadata(url)
                            except:
                                await context.followup.send(self.polished_message(guild["strings"]["invalid_url"], ["url"], {"url": url}))
                                return
                            if name is None: name = metadata["name"]
                            response = requests.get(url, stream=True)
                            # verify that the URL file is a media container
                            if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                                await context.followup.send(self.polished_message(guild["strings"]["invalid_song"],
                                                                                  ["song"],
                                                                                  {"song": self.polished_song_name(url, name)}))
                                return
                            await context.followup.send(self.polished_message(guild["strings"]["queue_add_song"],
                                                                              ["song", "index"],
                                                                              {"song": self.polished_song_name(url, name), "index": len(guild["queue"]) + 1}))
                            # add the track to the queue
                            guild["queue"].append({"file": url, "name": name, "time": "0", "duration": metadata["duration"], "silence": False})
                        if guild["connected"]: voice = context.guild.voice_client
                        else:
                            voice = await voice_channel.connect()
                            guild["connected"] = True
                            await context.guild.change_voice_state(channel=voice_channel, self_mute=False, self_deaf=True)
                        if not voice.is_playing():
                            while guild["index"] < len(guild["queue"]):
                                if guild["connected"]:
                                    if guild["queue"][guild["index"]]["silence"]: guild["queue"][guild["index"]]["silence"] = False
                                    else:
                                        await context.channel.send(self.polished_message(guild["strings"]["now_playing"],
                                                                                         ["song", "index", "max"],
                                                                                         {"song": self.polished_song_name(guild["queue"][guild["index"]]["file"],
                                                                                                                          guild["queue"][guild["index"]]["name"]),
                                                                                          "index": guild["index"] + 1,
                                                                                          "max": len(guild["queue"])}))
                                        guild["time"] = .0
                                # play the track
                                if not voice.is_playing():
                                    source = discord.FFmpegPCMAudio(source=guild["queue"][guild["index"]]["file"],
                                                                    before_options=f"-ss {guild['queue'][guild['index']]['time']}")
                                    source.read()
                                    voice.play(source)
                                    guild["queue"][guild["index"]]["time"] = "0"
                                    voice.source = discord.PCMVolumeTransformer(voice.source, volume = 1.0)
                                    voice.source.volume = guild["volume"]
                                # ensure that the track plays completely or is skipped by command before proceeding
                                while voice.is_playing() or voice.is_paused():
                                    await asyncio.sleep(.1)
                                    if voice.is_playing(): await add_time(guild, .1)

                                guild["index"] += 1
                                if guild["index"] == len(guild["queue"]):
                                    if not guild["repeat"]: await self.stop_music(context)
                                    guild["index"] = 0
                    break
        except: pass

    @app_commands.command(description="insert_command_desc")
    async def insert_command(self, context: discord.Interaction, file: discord.Attachment=None, song_url: str=None, new_name: str=None, new_index: int=None):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if file is None and new_index is not None and song_url is not None: await self.insert_song(context, str(file), new_name, new_index)
                elif file is not None and new_index is not None and song_url is None: await self.insert_song(context, song_url, new_name, new_index)
                else: await context.response.send_message(guild["strings"]["invalid_command"])
                break

    async def insert_song(self, context, url, name, index, time="0", duration=None, silence=False):
        try: voice_channel = context.user.voice.channel
        except: voice_channel = None
        if voice_channel is None: await context.response.send_message(self.polished_message(guild["strings"]["not_in_voice"], ["user"], {"user": context.user.mention}))
        else:
            for guild in self.guilds:
                if guild["id"] == context.guild.id:
                    if index > 0 and index < len(guild["queue"]) + 2:
                        try:
                            if name is None or duration is None:
                                metadata = self.get_metadata(url)
                                if name is None: name = metadata["name"]
                                if duration is None: duration = metadata["duration"]
                        except:
                            await context.response.send_message(self.polished_message(guild["strings"]["invalid_url"], ["url"], {"url": url}))
                            return
                        response = requests.get(url, stream=True)
                        # verify that the URL file is a media container
                        if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                            await context.response.send_message(self.polished_message(guild["strings"]["invalid_song"],
                                                                                      ["song"],
                                                                                      {"song": self.polished_song_name(url, name)}))
                            return
                        # add the track to the queue
                        guild["queue"].insert(index - 1, {"file": url, "name": name, "time": time, "duration": duration, "silence": silence})
                        if index - 1 <= guild["index"]: guild["index"] += 1
                        if not silence: await context.response.send_message(self.polished_message(guild["strings"]["queue_insert_song"],
                                                                                                  ["song", "index"],
                                                                                                  {"song": self.polished_song_name(url, name), "index": index}))
                    else: await context.response.send_message(self.polished_message(guild["strings"]["invalid_song_number"], ["index"], {"index": index}))
                    break

    @app_commands.command(description="move_command_desc")
    async def move_command(self, context: discord.Interaction, song_index: int, new_index: int):
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if song_index > 0 and song_index < len(guild["queue"]) + 1:
                    if new_index > 0 and new_index < len(guild["queue"]) + 1:
                        queue = guild["queue"].copy()
                        guild["queue"].remove(queue[song_index - 1])
                        guild["queue"].insert(new_index - 1, queue[song_index - 1])
                        await context.response.send_message(self.polished_message(guild["strings"]["queue_move_song"],
                                                                                  ["song", "index"],
                                                                                  {"song": self.polished_song_name(queue[song_index - 1]["file"],
                                                                                                                   queue[song_index - 1]["name"]),
                                                                                   "index": new_index}))
                    if song_index - 1 < guild["index"] and new_index - 1 >= guild["index"]: guild["index"] -= 1
                    elif song_index - 1 > guild["index"] and new_index - 1 <= guild["index"]: guild["index"] += 1
                    elif song_index - 1 == guild["index"] and new_index - 1 != guild["index"]: guild["index"] = new_index - 1
                    else: await context.response.send_message(self.polished_message(guild["strings"]["invalid_song_number"], ["index"], {"index": new_index}))
                else: await context.response.send_message(self.polished_message(guild["strings"]["invalid_song_number"], ["index"], {"index": song_index}))
                break

    @app_commands.command(description="rename_command_desc")
    async def rename_command(self, context: discord.Interaction, song_index: int, new_name: str):
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                await context.response.send_message(self.polished_message(guild["strings"]["queue_rename_song"],
                                                                          ["song", "index", "name"],
                                                                          {"song": self.polished_song_name(guild["queue"][song_index - 1]["file"],
                                                                                                           guild["queue"][song_index - 1]["name"]),
                                                                           "index": song_index,
                                                                           "name": new_name}))
                guild["queue"][song_index - 1]["name"] = new_name
                break

    @app_commands.command(description="remove_command_desc")
    async def remove_command(self, context: discord.Interaction, song_index: int): await self.remove_song(context, song_index)

    async def remove_song(self, context, index, silence=False):
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if index > 0 and index < len(guild["queue"]) + 1:
                    if not silence:
                        await context.response.send_message(self.polished_message(guild["strings"]["queue_remove_song"],
                                                                                  ["song", "index"],
                                                                                  {"song": self.polished_song_name(guild["queue"][index - 1]["file"],
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
                else: await context.response.send_message(self.polished_message(guild["strings"]["invalid_song_number"], ["index"], {"index": index}))
                break

    @move_command.autocomplete("song_index")
    @rename_command.autocomplete("song_index")
    @remove_command.autocomplete("song_index")
    async def song_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[int]]:
        self.init_guilds(False)
        songs = []
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                index = 1
                for song in guild["queue"]:
                    polished_song_name = self.polished_message(guild["strings"]["song"], ["song", "index"], {"song": song["name"], "index": index})
                    song["name"] = song["name"][:97 - len(polished_song_name) + len(song["name"])] + "..." if len(polished_song_name) > 100 else song["name"]
                    if (current == "" or current.lower() in polished_song_name.lower()) and len(songs) < 25:
                        songs.append(app_commands.Choice(name=polished_song_name, value=index))
                    index += 1
                break
        return songs

    @app_commands.command(description="skip_command_desc")
    async def skip_command(self, context: discord.Interaction, by: int=1, to: int=None):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if guild["queue"]:
                    if to is None:
                        if guild["index"] + by < len(guild["queue"]) and by > 0: guild["index"] += by - 1
                        else:
                            await context.response.send_message(guild["strings"]["invalid_command"])
                            return
                    else:
                        if to > 0 and to <= len(guild["queue"]): guild["index"] = to - 2
                        else:
                            await context.response.send_message(guild["strings"]["invalid_command"])
                            return
                    await context.response.send_message(self.polished_message(guild["strings"]["now_playing"],
                                                                              ["song", "index", "max"],
                                                                              {"song": self.polished_song_name(guild["queue"][guild["index"] + 1]["file"],
                                                                                                               guild["queue"][guild["index"] + 1]["name"]),
                                                                               "index": guild["index"] + 2,
                                                                               "max": len(guild["queue"])}))
                    guild["queue"][guild["index"] + 1]["silence"] = True
                    context.guild.voice_client.stop()
                else:
                    await context.response.send_message(guild["strings"]["queue_no_songs"])
                    return
                break

    @app_commands.command(description="previous_command_desc")
    async def previous_command(self, context: discord.Interaction, by: int=1):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if guild["queue"]:
                    if guild["index"] - by >= 0 and by > 0: guild["index"] -= by + 1
                    else:
                        await context.response.send_message(guild["strings"]["invalid_command"])
                        return
                    await context.response.send_message(self.polished_message(guild["strings"]["now_playing"],
                                                                              ["song", "index", "max"],
                                                                              {"song": self.polished_song_name(guild["queue"][guild["index"] + 1]["file"],
                                                                                                               guild["queue"][guild["index"] + 1]["name"]),
                                                                               "index": guild["index"] + 2,
                                                                               "max": len(guild["queue"])}))
                    guild["queue"][guild["index"] + 1]["silence"] = True
                    context.guild.voice_client.stop()
                else:
                    await context.response.send_message(guild["strings"]["queue_no_songs"])
                    return
                break

    @app_commands.command(description="stop_command_desc")
    async def stop_command(self, context: discord.Interaction):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                await context.response.send_message(guild["strings"]["stop"])
                break
        try:
            await context.response.send_message("...")
            await context.delete_original_response()
        except: pass
        await self.stop_music(context)

    async def stop_music(self, context, leave=False, guild=None):
        try:
            if guild is None: id = context.guild.id
            else: id = guild.id
            for guild in self.guilds:
                if guild["id"] == id:
                    guild["queue"] = []
                    if context.guild.voice_client.is_playing():
                        guild["index"] = -1
                        context.guild.voice_client.stop()
                    else: guild["index"] = 0
                    if leave or not guild["keep"]:
                        guild["connected"] = False
                        await context.guild.voice_client.disconnect()
                    break
        except: pass

    @app_commands.command(description="pause_command_desc")
    async def pause_command(self, context: discord.Interaction):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if guild["queue"]:
                    if context.guild.voice_client.is_paused():
                        context.guild.voice_client.resume()
                        now_or_no_longer = guild["strings"]["no_longer"]
                    else:
                        context.guild.voice_client.pause()
                        now_or_no_longer = guild["strings"]["now"]
                    await context.response.send_message(self.polished_message(guild["strings"]["pause"], ["now_or_no_longer"], {"now_or_no_longer": now_or_no_longer}))
                else:
                    await context.response.send_message(guild["strings"]["queue_no_songs"])
                    return
                break

    @app_commands.command(description="jump_command_desc")
    async def jump_command(self, context: discord.Interaction, time: str): await self.jump_to(context, time)

    async def jump_to(self, context, time):
        self.init_guilds()
        seconds = self.convert_to_seconds(time)
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if guild["queue"]:
                    await context.response.send_message(self.polished_message(guild["strings"]["jump"],
                                                                              ["time", "song", "index", "max"],
                                                                              {"time": self.convert_to_time(seconds),
                                                                               "song": self.polished_song_name(guild["queue"][guild["index"]]["file"],
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
                else: await context.response.send_message(guild["strings"]["queue_no_songs"])
                break

    @app_commands.command(description="forward_command_desc")
    async def forward_command(self, context: discord.Interaction, time: str):
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                await self.jump_to(context, str(float(guild["time"]) + self.convert_to_seconds(time)))
                break

    @app_commands.command(description="rewind_command_desc")
    async def rewind_command(self, context: discord.Interaction, time: str):
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                await self.jump_to(context, str(float(guild["time"]) - self.convert_to_seconds(time)))
                break

    @app_commands.command(description="when_command_desc")
    async def when_command(self, context: discord.Interaction):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if guild["queue"]:
                    await context.response.send_message(self.convert_to_time(guild["time"]) + " / " + self.convert_to_time(guild["queue"][guild["index"]]["duration"]))
                else: await context.response.send_message(guild["strings"]["queue_no_songs"])
                break

    @app_commands.command(description="loop_command_desc")
    async def loop_command(self, context: discord.Interaction):
        await self.lock.acquire()
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                strings = guild["strings"]
                break
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                repeat = not guild["repeat"]
                guild["repeat"] = repeat
                # modify the flat file for guilds to reflect the change of whether playlists repeat
                yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)

                self.guilds[self.data["guilds"].index(guild)]["repeat"] = repeat
                break
        if repeat: now_or_no_longer = strings["now"]
        else: now_or_no_longer = strings["no_longer"]
        await context.response.send_message(self.polished_message(strings["repeat"], ["now_or_no_longer"], {"now_or_no_longer": now_or_no_longer}))
        self.lock.release()

    @app_commands.command(description="shuffle_command_desc")
    async def shuffle_command(self, context: discord.Interaction, restart: typing.Literal[0, 1]=1):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
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
                else: await context.response.send_message(guild["strings"]["queue_no_songs"])
                break

    @app_commands.command(description="queue_command_desc")
    async def queue_command(self, context: discord.Interaction):
        await context.response.defer()
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                message = ""
                if guild["queue"]: message += guild["strings"]["queue_songs_header"] + "\n"
                else:
                    await context.followup.send(guild["strings"]["queue_no_songs"])
                    return
                index = 0
                while index < len(guild["queue"]):
                    previous_message = message
                    new_message = self.polished_message(guild["strings"]["song"] + "\n",
                                                        ["song", "index"],
                                                        {"song": self.polished_song_name(guild["queue"][index]["file"], guild["queue"][index]["name"]),
                                                         "index": index + 1})
                    message += new_message
                    if len(message) > 2000:
                        await context.followup.send(previous_message)
                        message = new_message
                    index += 1
                await context.followup.send(message)
                break

    @app_commands.command(description="what_command_desc")
    async def what_command(self, context: discord.Interaction):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if guild["queue"]: await context.response.send_message(self.polished_message(guild["strings"]["now_playing"],
                                                                                              ["song", "index", "max"],
                                                                                              {"song": self.polished_song_name(guild["queue"][guild["index"]]["file"],
                                                                                                                               guild["queue"][guild["index"]]["name"]),
                                                                                               "index": guild["index"] + 1,
                                                                                               "max": len(guild["queue"])}))
                else: await context.response.send_message(guild["strings"]["queue_no_songs"])
                break

    @app_commands.command(description="volume_command_desc")
    async def volume_command(self, context: discord.Interaction, set: str=None):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if set is not None:
                    if set.endswith("%"): guild["volume"] = float(set.replace("%", "")) / 100
                    else: guild["volume"] = float(set)
                    if context.guild.voice_client is not None and context.guild.voice_client.is_playing(): context.guild.voice_client.source.volume = guild["volume"]
                volume_percent = guild["volume"] * 100
                if volume_percent == float(int(volume_percent)): volume_percent = int(volume_percent)
                if set is None: await context.response.send_message(self.polished_message(guild["strings"]["volume"], ["volume"], {"volume": str(volume_percent) + "%"}))
                else: await context.response.send_message(self.polished_message(guild["strings"]["volume_change"], ["volume"], {"volume": str(volume_percent) + "%"}))
                break

    @app_commands.command(description="keep_command_desc")
    async def keep_command(self, context: discord.Interaction):
        await self.lock.acquire()
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                strings = guild["strings"]
                break
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                keep = not guild["keep"]
                guild["keep"] = keep
                # modify the flat file for guilds to reflect the change of whether to keep this bot in a voice call when no audio is playing
                yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)

                self.guilds[self.data["guilds"].index(guild)]["keep"] = keep
                break
        try: voice_channel = context.user.voice.channel.jump_url
        except: voice_channel = strings["whatever_voice"]
        if keep: now_or_no_longer = strings["now"]
        else: now_or_no_longer = strings["no_longer"]
        await context.response.send_message(self.polished_message(strings["keep"],
                                                                  ["bot", "voice", "now_or_no_longer"],
                                                                  {"bot": self.bot.user.mention, "voice": voice_channel, "now_or_no_longer": now_or_no_longer}))
        self.lock.release()

    @app_commands.command(description="recruit_command_desc")
    async def recruit_command(self, context: discord.Interaction):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                try: voice_channel = context.user.voice.channel
                except:
                    await context.response.send_message(self.polished_message(guild["strings"]["not_in_voice"], ["user"], {"user": context.user.mention}))
                    return
                if guild["connected"]:
                    await context.response.send_message("...")
                    await context.delete_original_response()
                else:
                    await context.response.send_message(self.polished_message(guild["strings"]["recruit_or_dismiss"],
                                                                              ["bot", "voice", "now_or_no_longer"],
                                                                              {"bot": self.bot.user.mention,
                                                                               "voice": voice_channel.jump_url,
                                                                               "now_or_no_longer": guild["strings"]["now"]}))
                    await voice_channel.connect()
                    guild["connected"] = True
                    await context.guild.change_voice_state(channel=voice_channel, self_mute=False, self_deaf=True)
                break

    @app_commands.command(description="dismiss_command_desc")
    async def dismiss_command(self, context: discord.Interaction):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                try: voice_channel = context.user.voice.channel
                except:
                    await context.response.send_message(self.polished_message(guild["strings"]["not_in_voice"], ["user"], {"user": context.user.mention}))
                    return
                if guild["connected"]:
                    await context.response.send_message(self.polished_message(guild["strings"]["recruit_or_dismiss"],
                                                                              ["bot", "voice", "now_or_no_longer"],
                                                                              {"bot": self.bot.user.mention,
                                                                               "voice": voice_channel.jump_url,
                                                                               "now_or_no_longer": guild["strings"]["no_longer"]}))
                    await self.stop_music(context, True)
                else:
                    await context.response.send_message("...")
                    await context.delete_original_response()
                break

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
                for guild in self.guilds:
                    if guild["id"] == member.guild.id:
                        if guild["connected"]:
                            guild["index"] = 0
                            guild["queue"] = []
                            guild["connected"] = False
                            member.guild.voice_client.cleanup()
                        break
        except: pass

    @app_commands.command(description="working_thread_command_desc")
    async def working_thread_command(self, context: discord.Interaction, set: str=None):
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                strings = guild["strings"]
                break
        await self.lock.acquire()
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                if set is None:
                    try: thread = self.bot.get_guild(guild["id"]).get_thread(guild["working_thread_id"]).jump_url
                    except: thread = strings["not_assigned"]
                    await context.response.send_message(self.polished_message(strings["working_thread"],
                                                                              ["bot", "thread"],
                                                                              {"bot": self.bot.user.mention, "thread": thread}))
                    break
                thread_nonexistent = True
                for thread in context.guild.threads:
                    if set == thread.name:
                        guild["working_thread_id"] = thread.id
                        yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
                        await context.response.send_message(self.polished_message(strings["working_thread_change"],
                                                                                  ["bot", "thread"],
                                                                                  {"bot": self.bot.user.mention, "thread": thread.jump_url}))
                        thread_nonexistent = False
                        break
                if thread_nonexistent: await context.response.send_message(strings["invalid_command"])
                break
        self.lock.release()

    @working_thread_command.autocomplete("set")
    async def working_thread_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        threads = []
        for thread in context.guild.threads:
            if (current == "" or current.lower() in thread.name.lower()) and len(threads) < 25: threads.append(app_commands.Choice(name=thread.name, value=thread.name))
        return threads

    async def renew_attachment(self, guild_id, playlist_index, song_index):
        for guild in self.data["guilds"]:
            if guild["id"] == guild_id:
                file = f"{self.music_directory}/{self.get_file_name(guild['playlists'][playlist_index]['songs'][song_index]['file'])}"
                if not os.path.exists(self.music_directory): os.mkdir(self.music_directory)
                open(file, "wb").write(requests.get(str(guild["playlists"][playlist_index]["songs"][song_index]["file"])).content)
                while not os.path.exists(file): await asyncio.sleep(.1)
                try: await self.bot.get_guild(guild_id).get_thread(guild["working_thread_id"]).send(yaml.safe_dump({"playlist_index": playlist_index, "song_index": song_index}),
                                                                                                    files=[discord.File(file)])
                except: pass
                break

    @commands.Cog.listener("on_message")
    async def renew_attachment_from_message(self, message: discord.Message):
        try:
            if message.author.id != self.bot.user.id: return
            message_data = yaml.safe_load(message.content)
            for guild in self.data["guilds"]:
                if guild["id"] == message.guild.id:                    
                    if self.get_file_name(guild["playlists"][message_data["playlist_index"]]["songs"][message_data["song_index"]]["file"]) == message.attachments[0].filename:
                        guild["playlists"][message_data["playlist_index"]]["songs"][message_data["song_index"]]["file"] = str(message.attachments[0])
                    try: os.remove(f"{self.music_directory}/{message.attachments[0].filename}")
                    except: pass
                    break
            yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
        except: pass
