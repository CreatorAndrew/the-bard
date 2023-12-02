import requests
import yaml
import asyncio
import typing
import discord
from discord import app_commands
from discord.ext import commands
from subprocess import check_output

class Music(commands.Cog):
    def __init__(self, bot, config, language_directory, lock):
        self.lock = lock
        self.bot = bot
        self.servers = []
        self.config = config
        self.language_directory = language_directory

    def get_metadata(self, file):
        for track in yaml.safe_load(check_output(["mediainfo", "--output=JSON", file]).decode("utf-8"))["media"]["track"]:
            try: name = track["Title"]
            except:
                try: name = track["Track"]
                except:
                    try: name = file[file.rindex("/") + 1:file.rindex(".")].replace("_", " ")
                    except: name = file[file.rindex("/") + 1:].replace("_", " ")
            try: duration = float(track["Duration"])
            except: duration = .0
            return {"name": name, "duration": duration}

    def polished_song_name(self, file, name): return f"[{name}](<{file}>)"

    def polished_message(self, message, placeholders, replacements):
        for placeholder in placeholders:
            replacement = replacements[placeholder]
            message = message.replace("%{" + placeholder + "}", str(replacement))
        return message

    def initialize_servers(self):
        data = yaml.safe_load(open(self.config, "r"))
        # add all servers with this bot to memory that weren't already
        if len(self.servers) < len(data["servers"]):
            ids = []
            for server in data["servers"]:
                for server_searched in self.servers: ids.append(server_searched["id"])
                if server["id"] not in ids: self.servers.append({"id": server["id"],
                                                                 "strings": yaml.safe_load(open(f"{self.language_directory}/{server['language']}.yaml", "r"))["strings"],
                                                                 "repeat": server["repeat"],
                                                                 "keep": server["keep"],
                                                                 "queue": [],
                                                                 "index": 0,
                                                                 "time": .0,
                                                                 "volume": 1.0,
                                                                 "connected": False})
        # remove any servers from memory that had removed this bot
        elif len(self.servers) > len(data["servers"]):
            index = 0
            while index < len(self.servers):
                try:
                    if self.servers[index]["id"] != data["servers"][index]["id"]:
                        self.servers.remove(self.servers[index])
                        index -= 1
                except: self.servers.remove(self.servers[index])
                index += 1

    @app_commands.command(description="playlist_command_desc")
    @app_commands.describe(add="add_desc")
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
                               rename: str=None,
                               remove: str=None,
                               load: str=None,
                               select: str=None,
                               action: str=None,
                               file: discord.Attachment=None,
                               song_url: str=None,
                               song_index: str=None,
                               new_name: str=None,
                               new_index: str=None):
        await context.response.defer()    
        def index_or_name(arg, playlists):
            try: return int(arg) - 1
            except ValueError: return playlists.index(arg)
        self.initialize_servers()
        data = yaml.safe_load(open(self.config, "r"))
        for server in self.servers:
            if server["id"] == context.guild.id:
                strings = server["strings"]
                # if a playlist-altering action was called in this command and no track index was specified, show a dropdown menu with the selected playlist's contents
                if (action == "move" or action == "rename" or action == "remove") and select is not None and song_index is None:
                    try:
                        song_options = [discord.SelectOption(label=strings["cancel_option"])]
                        for playlist in data["servers"][self.servers.index(server)]["playlists"]:
                            if select == str(data["servers"][self.servers.index(server)]["playlists"].index(playlist) + 1):
                                index = 1
                                for song in playlist["songs"]:
                                    song_options.append(discord.SelectOption(label=self.polished_message(server["strings"]["song"],
                                                                                                         ["song", "index"],
                                                                                                         {"song": song["name"], "index": index}),
                                                                             value=str(index)))
                                    index += 1
                                break
                        song_menu = discord.ui.Select(options=song_options)
                        chosen = []
                        async def song_callback(context):
                            await context.response.send_message("...")
                            await context.delete_original_response()
                            chosen.append(song_menu.values[0])
                        song_menu.callback = song_callback
                        view = discord.ui.View()
                        view.add_item(song_menu)
                        await context.followup.send("", view=view)
                        while not chosen: await asyncio.sleep(.1)
                        if chosen[0] == strings["cancel_option"]: return
                        song_index = chosen[0]
                    except: pass
                break
        await self.lock.acquire()
        for server in data["servers"]:
            if server["id"] == context.guild.id:
                playlists = []
                for playlist_instance in server["playlists"]: playlists.append(playlist_instance["name"])
                # add a playlist
                if add is not None and select is None:
                    server["playlists"].append({"name": add, "songs": []})
                    await context.followup.send(self.polished_message(strings["add_playlist"],
                                                                      ["playlist", "playlist_index"],
                                                                      {"playlist": add, "playlist_index": len(server["playlists"])}))
                # rename a playlist
                elif rename is not None and select is None:
                    if new_name is None:
                        await context.followup.send(strings["invalid_command"])
                        self.lock.release()
                        return
                    else:
                        index = index_or_name(rename, playlists)
                        await context.followup.send(self.polished_message(strings["rename_playlist"],
                                                                          ["playlist", "playlist_index", "name"],
                                                                          {"playlist": playlists[index], "playlist_index": index + 1, "name": new_name}))
                        server["playlists"][index]["name"] = new_name
                # remove a playlist
                elif remove is not None and select is None:
                    index = index_or_name(remove, playlists)
                    server["playlists"].remove(server["playlists"][index])
                    await context.followup.send(self.polished_message(strings["remove_playlist"],
                                                                      ["playlist", "playlist_index"],
                                                                      {"playlist": playlists[index], "playlist_index": index + 1}))
                # load a playlist
                elif load is not None and select is None:
                    if load is None:
                        await context.followup.send(strings["invalid_command"])
                        self.lock.release()
                        return
                    else:
                        index = index_or_name(load, playlists)
                        self.lock.release()
                        await self.play_song(context, playlist=server["playlists"][index]["songs"])
                        return
                # return a list of playlists for the calling Discord server
                elif action == "list" and select is None:
                    message = ""
                    if server["playlists"]: message += strings["playlists_header"] + "\n"
                    else:
                        await context.followup.send(strings["no_playlists"])
                        self.lock.release()
                        return
                    index = 0
                    while index < len(server["playlists"]):
                        previous_message = "" + message
                        new_message = self.polished_message(strings["playlist"] + "\n",
                                                            ["playlist", "playlist_index"],
                                                            {"playlist": playlists[index], "playlist_index": index + 1})
                        message += new_message
                        if len(message) > 2000:
                            await context.followup.send(previous_message)
                            message = new_message
                        index += 1
                    await context.followup.send(message)
                    self.lock.release()
                    return
                # take a playlist name or index as the first argument and make arguments after it have to do with the playlist
                elif select is not None:
                    try:
                        if select in playlists or int(select) > 0:
                            try:
                                playlist_number = int(select) - 1
                                # an index is entered, but is out of range
                                if playlist_number >= len(server["playlists"]) or playlist_number < 0:
                                    await context.followup.send(self.polished_message(strings["invalid_playlist_number"],
                                                                                      ["playlist_index"],
                                                                                      {"placeholders": playlist_number + 1}))
                                    self.lock.release()
                                    return
                            # an existent playlist name is entered
                            except ValueError: playlist_number = playlists.index(select)
                            # handle adding a track to the playlist
                            if action == "add":
                                if file is None and song_url is not None: url = song_url
                                elif file is not None and song_url is None: url = str(file)
                                else:
                                    await context.followup.send(strings["invalid_command"])
                                    self.lock.release()
                                    return
                                if new_index is None: song = {"name": new_name, "index": len(server["playlists"][playlist_number]["songs"]) + 1}
                                else: song = {"name": new_name, "index": int(new_index)}
                                try:
                                    if song["name"] is None: song["name"] = self.get_metadata(url)["name"]
                                    song["duration"] = self.get_metadata(url)["duration"]
                                except:
                                    await context.followup.send(self.polished_message(server["strings"]["invalid_url"], ["url"], {"url": url}))
                                    self.lock.release()
                                    return
                                response = requests.get(url, stream = True)
                                # verify that the URL file is a media container
                                if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                                    await context.followup.send(self.polished_message(strings["invalid_song"],
                                                                                      ["song"],
                                                                                      {"song": self.polished_song_name(url, song["name"])}))
                                    self.lock.release()
                                    return

                                server["playlists"][playlist_number]["songs"].insert(song["index"] - 1, {"file": url,
                                                                                                         "name": song["name"],
                                                                                                         "time": "0",
                                                                                                         "duration": song["duration"],
                                                                                                         "silence": False})
                                await context.followup.send(self.polished_message(strings["playlist_add_song"],
                                                                                          ["playlist", "playlist_index", "song", "index"],
                                                                                          {"playlist": playlists[playlist_number],
                                                                                           "playlist_index": playlist_number + 1,
                                                                                           "song": self.polished_song_name(url, song["name"]),
                                                                                           "index": song["index"]}))
                            # handle moving the position of a track within the playlist
                            elif action == "move":
                                if song_index is None or new_index is None:
                                    await context.followup.send(strings["invalid_command"])
                                    self.lock.release()
                                    return
                                else:
                                    song = server["playlists"][playlist_number]["songs"][int(song_index) - 1]
                                    server["playlists"][playlist_number]["songs"].remove(song)
                                    server["playlists"][playlist_number]["songs"].insert(int(new_index) - 1, song)
                                    await context.followup.send(self.polished_message(strings["playlist_move_song"],
                                                                                              ["playlist", "playlist_index", "song", "index"],
                                                                                              {"playlist": playlists[playlist_number],
                                                                                               "playlist_index": playlist_number + 1,
                                                                                               "song": self.polished_song_name(song["file"], song["name"]),
                                                                                               "index": new_index}))

                            # handle renaming a track in the playlist
                            elif action == "rename":
                                if song_index is None or new_name is None:
                                    await context.followup.send(strings["invalid_command"])
                                    self.lock.release()
                                    return
                                else:
                                    song = server["playlists"][playlist_number]["songs"][int(song_index) - 1]
                                    await context.followup.send(self.polished_message(strings["playlist_rename_song"],
                                                                                      ["playlist", "playlist_index", "song", "index", "name"],
                                                                                      {"playlist": server["playlists"][playlist_number]["name"],
                                                                                       "playlist_index": playlist_number + 1,
                                                                                       "song": self.polished_song_name(song["file"], song["name"]),
                                                                                       "index": song_index,
                                                                                       "name": new_name}))
                                    song["name"] = new_name
                            # handle removing a track from the playlist
                            elif action == "remove":
                                if song_index is None:
                                    await context.followup.send(strings["invalid_command"])
                                    self.lock.release()
                                    return
                                else:
                                    song = server["playlists"][playlist_number]["songs"][int(song_index) - 1]
                                    server["playlists"][playlist_number]["songs"].remove(song)
                                    await context.followup.send(self.polished_message(strings["playlist_remove_song"],
                                                                                      ["playlist", "playlist_index", "song", "index"],
                                                                                      {"playlist": server["playlists"][playlist_number]["name"],
                                                                                       "playlist_index": playlist_number + 1,
                                                                                       "song": self.polished_song_name(song["file"], song["name"]),
                                                                                       "index": song_index}))
                            # return a list of tracks in the playlist
                            elif action == "list":
                                message = ""
                                if server["playlists"][playlist_number]["songs"]:
                                    if server["playlists"][playlist_number]:
                                        message += self.polished_message(strings["playlist_songs_header"] + "\n",
                                                                         ["playlist", "playlist_index"],
                                                                         {"playlist": playlists[playlist_number], "playlist_index": playlist_number + 1})
                                    else:
                                        await context.followup.send(strings["no_playlists"])
                                        self.lock.release()
                                        return
                                else:
                                    await context.followup.send(self.polished_message(strings["playlist_no_songs"],
                                                                                      ["playlist", "playlist_index"],
                                                                                      {"playlist": playlists[playlist_number], "playlist_index": playlist_number + 1}))
                                    self.lock.release()
                                    return
                                index = 0
                                while index < len(server["playlists"][playlist_number]["songs"]):
                                    previous_message = "" + message
                                    new_message = self.polished_message(strings["song"] + "\n",
                                                                        ["song", "index"],
                                                                        {"song": self.polished_song_name(server["playlists"][playlist_number]["songs"][index]["file"],
                                                                                                         server["playlists"][playlist_number]["songs"][index]["name"]),
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
                    # a playlist name is entered, but a playlist of that name does not exist
                    except ValueError:
                        await context.followup.send(self.polished_message(strings["invalid_playlist"], ["playlist"], {"playlist": select}))
                        self.lock.release()
                        return
                else:
                    await context.followup.send(strings["invalid_command"])
                    self.lock.release()
                    return
                # modify the YAML file to reflect changes regarding playlists
                yaml.safe_dump(data, open(self.config, "w"), indent=4)

                break
        self.lock.release()

    @playlist_command.autocomplete("rename")
    @playlist_command.autocomplete("remove")
    @playlist_command.autocomplete("load")
    @playlist_command.autocomplete("select")
    async def playlist_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        self.initialize_servers()
        data = yaml.safe_load(open(self.config, "r"))
        playlists = []
        for server in data["servers"]:
            if server["id"] == context.guild.id:
                index = 1
                for playlist in server["playlists"]:
                    if (current == "" or current.lower() in playlist["name"].lower()) and len(playlists) < 25:
                        playlists.append(app_commands.Choice(name=self.polished_message(self.servers[data["servers"].index(server)]["strings"]["playlist"],
                                                                                        ["playlist", "playlist_index"],
                                                                                        {"playlist": playlist["name"], "playlist_index": index}),
                                                             value=str(index)))
                    index += 1
                break
        return playlists

    @playlist_command.autocomplete("action")
    async def playlist_action_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        return [app_commands.Choice(name="add", value="add"),
                app_commands.Choice(name="move", value="move"),
                app_commands.Choice(name="rename", value="rename"),
                app_commands.Choice(name="remove", value="remove"),
                app_commands.Choice(name="list", value="list")]

    @playlist_command.autocomplete("song_index")
    async def playlist_song_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        self.initialize_servers()
        data = yaml.safe_load(open(self.config, "r"))
        songs = []
        for server in data["servers"]:
            if server["id"] == context.guild.id:
                try:
                    index = 1
                    for song in server["playlists"][int(context.namespace.select) - 1]["songs"]:
                        if (current == "" or current.lower() in song["name"].lower()) and len(songs) < 25:
                            songs.append(app_commands.Choice(name=self.polished_message(self.servers[data["servers"].index(server)]["strings"]["song"],
                                                                                        ["song", "index"],
                                                                                        {"song": song["name"], "index": index}),
                                                             value=str(index)))
                        index += 1
                except: pass
                break
        return songs

    @app_commands.command(description="play_command_desc")
    async def play_command(self, context: discord.Interaction, file: discord.Attachment=None, url: str=None, new_name: str=None):
        await context.response.defer()
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.guild.id:
                if file is None and url is not None: await self.play_song(context, url, new_name)
                elif file is not None and url is None: await self.play_song(context, str(file), new_name)
                else: await context.followup.send(server["strings"]["invalid_command"])
                break

    async def play_song(self, context, url=None, name=None, playlist=[]):
        try:
            async def add_time(server, time): server["time"] += time
            for server in self.servers:
                if server["id"] == context.guild.id:
                    try: voice_channel = context.user.voice.channel
                    except: voice_channel = None
                    if voice_channel is None:
                        await context.followup.send(self.polished_message(server["strings"]["not_in_voice"], ["user"], {"user": context.user.mention}))
                    else:
                        if url is None:
                            message = ""
                            for song in playlist:
                                previous_message = "" + message
                                new_message = self.polished_message(server["strings"]["queue_add_song"] + "\n",
                                                                    ["song", "index"],
                                                                    {"song": self.polished_song_name(song["file"], song["name"]), "index": len(server["queue"]) + 1})
                                message += new_message
                                if len(message) > 2000:
                                    await context.followup.send(previous_message)
                                    message = new_message
                                # add the track to the queue
                                server["queue"].append(song)
                            await context.followup.send(message)
                        else:
                            try:
                                if name is None: name = self.get_metadata(url)["name"]
                            except:
                                await context.followup.send(self.polished_message(server["strings"]["invalid_url"], ["url"], {"url": url}))
                                return
                            response = requests.get(url, stream=True)
                            # verify that the URL file is a media container
                            if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                                await context.followup.send(self.polished_message(server["strings"]["invalid_song"],
                                                                                  ["song"],
                                                                                  {"song": self.polished_song_name(url, name)}))
                                return
                            await context.followup.send(self.polished_message(server["strings"]["queue_add_song"],
                                                                              ["song", "index"],
                                                                              {"song": self.polished_song_name(url, name), "index": len(server["queue"]) + 1}))
                            # add the track to the queue
                            try: server["queue"].append({"file": url, "name": name, "time": "0", "duration": self.get_metadata(url)["duration"], "silence": False})
                            except:
                                await context.followup.send(self.polished_message(server["strings"]["invalid_url"], ["url"], {"url": url}))
                                return
                        if server["connected"]: voice = context.guild.voice_client
                        else:
                            voice = await voice_channel.connect()
                            server["connected"] = True
                            await context.guild.change_voice_state(channel=voice_channel, self_mute=False, self_deaf=True)
                        if not voice.is_playing():
                            while server["index"] < len(server["queue"]):
                                if server["connected"]:
                                    if server["queue"][server["index"]]["silence"]: server["queue"][server["index"]]["silence"] = False
                                    else:
                                        await context.channel.send(self.polished_message(server["strings"]["now_playing"],
                                                                                         ["song", "index", "max"],
                                                                                         {"song": self.polished_song_name(server["queue"][server["index"]]["file"],
                                                                                                                          server["queue"][server["index"]]["name"]),
                                                                                          "index": server["index"] + 1,
                                                                                          "max": len(server["queue"])}))
                                        server["time"] = .0
                                # play the track
                                if not voice.is_playing():
                                    source = discord.FFmpegPCMAudio(source=server["queue"][server["index"]]["file"],
                                                                    before_options=f"-ss {server['queue'][server['index']]['time']}")
                                    source.read()
                                    voice.play(source)
                                    server["queue"][server["index"]]["time"] = "0"
                                    voice.source = discord.PCMVolumeTransformer(voice.source, volume = 1.0)
                                    voice.source.volume = server["volume"]
                                # ensure that the track plays completely or is skipped by command before proceeding
                                while voice.is_playing() or voice.is_paused():
                                    await asyncio.sleep(.1)
                                    if voice.is_playing(): await add_time(server, .1)

                                server["index"] += 1
                                if server["index"] == len(server["queue"]):
                                    if not server["repeat"]: await self.stop_music(context)
                                    server["index"] = 0
                    break
        except: pass

    @app_commands.command(description="insert_command_desc")
    async def insert_command(self, context: discord.Interaction, file: discord.Attachment=None, url: str=None, new_name: str=None, new_index: str=None):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.guild.id:
                if file is None and new_index is not None and url is not None: await self.insert_song(context, str(file), new_name, new_index)
                elif file is not None and new_index is not None and url is None: await self.insert_song(context, url, new_name, new_index)
                else: await context.response.send_message(server["strings"]["invalid_command"])
                break

    async def insert_song(self, context, url, name, index, time="0", duration=None, silence=False):
        try: voice_channel = context.user.voice.channel
        except: voice_channel = None
        if voice_channel is None: await context.response.send_message(self.polished_message(server["strings"]["not_in_voice"], ["user"], {"user": context.user.mention}))
        else:
            for server in self.servers:
                if server["id"] == context.guild.id:
                    if int(index) > 0 and int(index) < len(server["queue"]) + 2:
                        try:
                            if name is None: name = self.get_metadata(url)["name"]
                            if duration is None: duration = self.get_metadata(url)["duration"]
                        except:
                            await context.response.send_message(self.polished_message(server["strings"]["invalid_url"], ["url"], {"url": url}))
                            return
                        response = requests.get(url, stream=True)
                        # verify that the URL file is a media container
                        if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                            await context.response.send_message(self.polished_message(server["strings"]["invalid_song"],
                                                                                      ["song"],
                                                                                      {"song": self.polished_song_name(url, name)}))
                            return
                        # add the track to the queue
                        server["queue"].insert(int(index) - 1, {"file": url, "name": name, "time": time, "duration": duration, "silence": silence})
                        if int(index) - 1 <= server["index"]: server["index"] += 1
                        if not silence: await context.response.send_message(self.polished_message(server["strings"]["queue_insert_song"],
                                                                                                  ["song", "index"],
                                                                                                  {"song": self.polished_song_name(url, name), "index": index}))
                        break
                    else: await context.response.send_message(self.polished_message(server["strings"]["invalid_song_number"], ["index"], {"index": index}))

    @app_commands.command(description="move_command_desc")
    async def move_command(self, context: discord.Interaction, song_index: str, new_index: str):
        for server in self.servers:
            if server["id"] == context.guild.id:
                if int(song_index) > 0 and int(song_index) < len(server["queue"]) + 1:
                    if int(new_index) > 0 and int(new_index) < len(server["queue"]) + 1:
                        queue = server["queue"].copy()
                        server["queue"].remove(queue[int(song_index) - 1])
                        server["queue"].insert(int(new_index) - 1, queue[int(song_index) - 1])
                        await context.response.send_message(self.polished_message(server["strings"]["queue_move_song"],
                                                                                  ["song", "index"],
                                                                                  {"song": self.polished_song_name(queue[int(song_index) - 1]["file"],
                                                                                                                   queue[int(song_index) - 1]["name"]),
                                                                                   "index": new_index}))
                    if int(song_index) - 1 < server["index"] and int(new_index) - 1 >= server["index"]: server["index"] -= 1
                    elif int(song_index) - 1 > server["index"] and int(new_index) - 1 <= server["index"]: server["index"] += 1
                    elif int(song_index) - 1 == server["index"] and int(new_index) - 1 != server["index"]: server["index"] = int(new_index) - 1
                    else: await context.response.send_message(self.polished_message(server["strings"]["invalid_song_number"], ["index"], {"index": new_index}))
                else: await context.response.send_message(self.polished_message(server["strings"]["invalid_song_number"], ["index"], {"index": song_index}))

    @app_commands.command(description="rename_command_desc")
    async def rename_command(self, context: discord.Interaction, song_index: str, new_name: str):
        for server in self.servers:
            if server["id"] == context.guild.id:
                await context.response.send_message(self.polished_message(server["strings"]["queue_rename_song"],
                                                                          ["song", "index", "name"],
                                                                          {"song": self.polished_song_name(server["queue"][int(song_index) - 1]["file"],
                                                                                                           server["queue"][int(song_index) - 1]["name"]),
                                                                           "index": song_index,
                                                                           "name": new_name}))
                server["queue"][int(song_index) - 1]["name"] = new_name

    @app_commands.command(description="remove_command_desc")
    async def remove_command(self, context: discord.Interaction, song_index: str): await self.remove_song(context, song_index)

    async def remove_song(self, context, index, silence=False):
        for server in self.servers:
            if server["id"] == context.guild.id:
                if int(index) > 0 and int(index) < len(server["queue"]) + 1:
                    if not silence:
                        await context.response.send_message(self.polished_message(server["strings"]["queue_remove_song"],
                                                                                  ["song", "index"],
                                                                                  {"song": self.polished_song_name(server["queue"][int(index) - 1]["file"],
                                                                                                                   server["queue"][int(index) - 1]["name"]),
                                                                                   "index": index}))
                    # remove the track from the queue
                    server["queue"].remove(server["queue"][int(index) - 1])
                    # decrement the index of the current song to match its new position in the queue, should the removed song have been before it
                    if int(index) - 1 < server["index"]: server["index"] -= 1
                    # if the removed song is the current song, play the new song in its place in the queue
                    elif int(index) - 1 == server["index"]:
                        server["index"] -= 1
                        context.guild.voice_client.stop()
                    break
                else: await context.response.send_message(self.polished_message(server["strings"]["invalid_song_number"], ["index"], {"index": index}))

    @move_command.autocomplete("song_index")
    @rename_command.autocomplete("song_index")
    @remove_command.autocomplete("song_index")
    async def song_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        self.initialize_servers()
        songs = []
        for server in self.servers:
            if server["id"] == context.guild.id:
                index = 1
                for song in server["queue"]:
                    if (current == "" or current.lower() in song["name"].lower()) and len(songs) < 25:
                        songs.append(app_commands.Choice(name=self.polished_message(server["strings"]["song"], ["song", "index"], {"song": song["name"], "index": index}),
                                                         value=str(index)))
                    index += 1
                break
        return songs

    @app_commands.command(description="skip_command_desc")
    async def skip_command(self, context: discord.Interaction):
        await context.response.send_message("...")
        await context.delete_original_response()
        context.guild.voice_client.stop()

    @app_commands.command(description="previous_command_desc")
    async def previous_command(self, context: discord.Interaction):
        await context.response.send_message("...")
        await context.delete_original_response()
        for server in self.servers:
            if server["id"] == context.guild.id:
                if server["index"] > 0: server["index"] -= 2
                elif server["queue"]: server["index"] = len(server["queue"]) - 2
                context.guild.voice_client.stop()

    @app_commands.command(description="stop_command_desc")
    async def stop_command(self, context: discord.Interaction):
        await context.response.send_message("...")
        await context.delete_original_response()
        await self.stop_music(context)

    async def stop_music(self, context, leave=False, guild=None):
        try:
            if guild is None: id = context.guild.id
            else: id = guild.id
            for server in self.servers:
                if server["id"] == id:
                    server["queue"] = []
                    if context.guild.voice_client.is_playing():
                        server["index"] = -1
                        context.guild.voice_client.stop()
                    else: server["index"] = 0
                    if leave or not server["keep"]:
                        await context.guild.voice_client.disconnect()
                        server["connected"] = False
                    break
        except: pass

    @app_commands.command(description="pause_command_desc")
    async def pause_command(self, context: discord.Interaction):
        try:
            await context.response.send_message("...")
            await context.delete_original_response()
            if context.guild.voice_client.is_paused(): context.guild.voice_client.resume()
            else: context.guild.voice_client.pause()
        except: pass

    @app_commands.command(description="jump_command_desc")
    async def jump_command(self, context: discord.Interaction, time: str):
        await context.response.send_message("...")
        await context.delete_original_response()
        await self.jump_to(context, time)

    async def jump_to(self, context, time):
        self.initialize_servers()
        segments = []
        if ":" in time: segments = time.split(":")
        if len(segments) == 2: seconds = float(segments[0]) * 60 + float(segments[1])
        elif len(segments) == 3: seconds = float(segments[0]) * 3600 + float(segments[1]) * 60 + float(segments[2])
        else: seconds = float(time)
        for server in self.servers:
            if server["id"] == context.guild.id:
                if server["queue"]:
                    server["time"] = seconds
                    await self.insert_song(context,
                                           server["queue"][server["index"]]["file"],
                                           server["queue"][server["index"]]["name"],
                                           server["index"] + 2,
                                           seconds,
                                           server["queue"][server["index"]]["duration"],
                                           True)
                    await self.remove_song(context, server["index"] + 1, True)
                else: await context.response.send_message(server["strings"]["queue_no_songs"])
                break

    @app_commands.command(description="forward_command_desc")
    async def forward_command(self, context: discord.Interaction, time: str):
        await context.response.send_message("...")
        await context.delete_original_response()
        for server in self.servers:
            if server["id"] == context.guild.id: await self.jump_to(context, str(float(server["time"]) + float(time)))

    @app_commands.command(description="rewind_command_desc")
    async def rewind_command(self, context: discord.Interaction, time: str):
        await context.response.send_message("...")
        await context.delete_original_response()
        for server in self.servers:
            if server["id"] == context.guild.id: await self.jump_to(context, str(float(server["time"]) - float(time)))

    @app_commands.command(description="when_command_desc")
    async def when_command(self, context: discord.Interaction):
        def convert_to_time(number):
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
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.guild.id:
                if server["queue"]:
                    await context.response.send_message(convert_to_time(server["time"]) + " / " + convert_to_time(server["queue"][server["index"]]["duration"]))
                else: await context.response.send_message(server["strings"]["queue_no_songs"])

    @app_commands.command(description="loop_command_desc")
    async def loop_command(self, context: discord.Interaction):
        await self.lock.acquire()
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.guild.id:
                strings = server["strings"]
                break
        data = yaml.safe_load(open(self.config, "r"))
        for server in data["servers"]:
            if server["id"] == context.guild.id:
                repeat = not server["repeat"]
                server["repeat"] = repeat
                # modify the YAML file to reflect the change of whether playlists repeat
                yaml.safe_dump(data, open(self.config, "w"), indent=4)

                self.servers[data["servers"].index(server)]["repeat"] = repeat
                break
        if repeat: now_or_no_longer = strings["now"]
        else: now_or_no_longer = strings["no_longer"]
        await context.response.send_message(self.polished_message(strings["repeat"], ["now_or_no_longer"], {"now_or_no_longer": now_or_no_longer}))
        self.lock.release()

    @app_commands.command(description="queue_command_desc")
    async def queue_command(self, context: discord.Interaction):
        await context.response.defer()
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.guild.id:
                message = ""
                if server["queue"]: message += server["strings"]["queue_songs_header"] + "\n"
                else:
                    await context.followup.send(server["strings"]["queue_no_songs"])
                    return
                index = 0
                while index < len(server["queue"]):
                    previous_message = "" + message
                    new_message = self.polished_message(server["strings"]["song"] + "\n",
                                                        ["song", "index"],
                                                        {"song": self.polished_song_name(server["queue"][index]["file"], server["queue"][index]["name"]),
                                                         "index": index + 1})
                    message += new_message
                    if len(message) > 2000:
                        await context.followup.send(previous_message)
                        message = new_message
                    index += 1
                await context.followup.send(message)

    @app_commands.command(description="what_command_desc")
    async def what_command(self, context: discord.Interaction):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.guild.id:
                if server["queue"]: await context.response.send_message(self.polished_message(server["strings"]["now_playing"],
                                                                                              ["song", "index", "max"],
                                                                                              {"song": self.polished_song_name(server["queue"][server["index"]]["file"],
                                                                                                                               server["queue"][server["index"]]["name"]),
                                                                                               "index": server["index"] + 1,
                                                                                               "max": len(server['queue'])}))
                else: await context.response.send_message(server["strings"]["queue_no_songs"])

    @app_commands.command(description="volume_command_desc")
    async def volume_command(self, context: discord.Interaction, set: str=None):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.guild.id:
                if set is not None:
                    if set.endswith("%"): server["volume"] = float(set.replace("%", "")) / 100
                    else: server["volume"] = float(set)
                    if context.guild.voice_client is not None and context.guild.voice_client.is_playing(): context.guild.voice_client.source.volume = server["volume"]
                volume_percent = server["volume"] * 100
                if volume_percent == float(int(volume_percent)): volume_percent = int(volume_percent)
                if set is None: await context.response.send_message(self.polished_message(server["strings"]["volume"], ["volume"], {"volume": str(volume_percent) + "%"}))
                else: await context.response.send_message(self.polished_message(server["strings"]["volume_change"], ["volume"], {"volume": str(volume_percent) + "%"}))
                break

    @app_commands.command(description="keep_command_desc")
    async def keep_command(self, context: discord.Interaction):
        await self.lock.acquire()
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.guild.id:
                strings = server["strings"]
                break
        data = yaml.safe_load(open(self.config, "r"))
        for server in data["servers"]:
            if server["id"] == context.guild.id:
                keep = not server["keep"]
                server["keep"] = keep
                # modify the YAML file to reflect the change of whether to keep this bot in a voice call when no audio is playing
                yaml.safe_dump(data, open(self.config, "w"), indent=4)

                self.servers[data["servers"].index(server)]["keep"] = keep
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
        await context.response.send_message("...")
        await context.delete_original_response()
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.guild.id:
                try: voice_channel = context.user.voice.channel
                except:
                    await context.response.send_message(self.polished_message(server["strings"]["not_in_voice"], ["user"], {"user": context.user.mention}))
                    return
                if not server["connected"]:
                    await voice_channel.connect()
                    server["connected"] = True
                    await context.guild.change_voice_state(channel=voice_channel, self_mute=False, self_deaf=True)

    @app_commands.command(description="dismiss_command_desc")
    async def dismiss_command(self, context: discord.Interaction):    
        await context.response.send_message("...")
        await context.delete_original_response()
        await self.stop_music(context, True)

    # ensure that this bot disconnects from any empty voice channel it's in
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            if member.guild.voice_client.is_connected():
                for voice_channel in member.guild.voice_channels:
                    if voice_channel.voice_states and list(voice_channel.voice_states)[0] == self.bot.user.id and len(list(voice_channel.voice_states)) == 1:
                        await self.stop_music(member, True, member.guild)
                        break
        except: pass
