import requests
import yaml
import asyncio
import discord
from discord.ext import commands

class Music(commands.Cog):
    def __init__(self, bot, config, language_directory):
        self.bot = bot
        self.servers = []
        self.language_directory = language_directory
        self.config = config

    def polished_song_name(self, file, name):
        if name is not None: return name + " (" + file + ")"
        return file

    def polished_message(self, message, placeholders, replacements):
        for placeholder in placeholders:
            replacement = replacements[placeholder]
            message = message.replace("%{" + placeholder + "}", str(replacement))
        return message

    # initialize any registered Discord servers that weren't previously initialized
    def initialize_servers(self):
        with open(self.config, "r") as read_file: data = yaml.load(read_file, yaml.Loader)
        if len(self.servers) < len(data["servers"]):
            ids = []
            for server in data["servers"]:
                with open(f"{self.language_directory}/{server['language']}.yaml", "r") as read_file: language = yaml.load(read_file, yaml.Loader)
                for server_searched in self.servers: ids.append(server_searched["id"])
                if server["id"] not in ids: self.servers.append({"id": server["id"],
                                                                 "strings": language["strings"],
                                                                 "repeat": server["repeat"],
                                                                 "keep": server["keep"],
                                                                 "queue": [],
                                                                 "index": 0,
                                                                 "time": .0,
                                                                 "volume": 1.0,
                                                                 "connected": False})

    @commands.command()
    async def playlist(self, context, *args):
        def index_or_name(arg, playlists):
            try: return int(arg) - 1
            except ValueError: return playlists.index(arg)
        def add_song_index_or_name(arg, server, index):
            try: return {"name": None, "index": int(arg)}
            except ValueError: return {"name": arg, "index": len(server["playlists"][index]["songs"]) + 1}
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                strings = server["strings"]
                break
        with open(self.config, "r") as read_file: data = yaml.load(read_file, yaml.Loader)
        for server in data["servers"]:
            if server["id"] == context.message.guild.id:
                playlists = []
                if server["playlists"]:
                    for playlist in server["playlists"]: playlists.append(playlist["name"])
                if args[0] == "add":
                    if len(args) == 2:
                        server["playlists"].append({"name": args[1], "songs": []})
                        await context.reply(self.polished_message(message = strings["add_playlist"],
                                                                  placeholders = ["playlist", "playlist_index"],
                                                                  replacements = {"playlist": args[1],
                                                                                  "playlist_index": len(server["playlists"])}))
                    else:
                        await context.reply(strings["invalid_command"])
                        return
                elif args[0] == "rename":
                    if len(args) == 3:
                        index = index_or_name(args[1], playlists)
                        await context.reply(self.polished_message(message = strings["rename_playlist"],
                                                                  placeholders = ["playlist", "playlist_index"],
                                                                  replacements = {"playlist": playlists[index],
                                                                                  "playlist_index": index + 1,
                                                                                  "name": args[2]}))
                        server["playlists"][index]["name"] = args[2]
                    else:
                        await context.reply(strings["invalid_command"])
                        return
                elif args[0] == "remove":
                    if len(args) == 2:
                        index = index_or_name(args[1], playlists)
                        server["playlists"].remove(server["playlists"][index])
                        await context.reply(self.polished_message(message = strings["remove_playlist"],
                                                                  placeholders = ["playlist", "playlist_index"],
                                                                  replacements = {"playlist": playlists[index],
                                                                                  "playlist_index": index + 1}))
                    else:
                        await context.reply(strings["invalid_command"])
                        return
                elif args[0] == "load":
                    if len(args) == 2:
                        index = index_or_name(args[1], playlists)
                        await self.play_song(context, playlist = server["playlists"][index]["songs"])
                        return
                elif args[0] == "list":
                    message = ""
                    if server["playlists"]: message += strings["playlists_header"] + "\n"
                    else:
                        await context.reply(strings["no_playlists"])
                        return
                    index = 0
                    while index < len(server["playlists"]):
                        message += self.polished_message(message = strings["playlist"] + "\n",
                                                         placeholders = ["playlist", "playlist_index"],
                                                         replacements = {"playlist": playlists[index],
                                                                         "playlist_index": index + 1})
                        index += 1
                    await context.reply(message)
                    return
                else:
                    try:
                        if args[0] in playlists or int(args[0]) > 0:
                            try:
                                playlist_index = int(args[0]) - 1
                                if playlist_index >= len(server["playlists"]) or playlist_index < 0:
                                    await context.reply(self.polished_message(message = strings["invalid_playlist_number"],
                                                                              placeholders = ["playlist_index"],
                                                                              replacements = {"placeholders": playlist_index + 1}))
                                    return
                            except ValueError: playlist_index = playlists.index(args[0])
                            if args[1] == "add":
                                if len(args) >= 3 and len(args) <= 5 and not context.message.attachments: url = args[2]
                                elif len(args) < 5 and context.message.attachments: url = str(context.message.attachments[0])
                                else:
                                    await context.reply(strings["invalid_command"])
                                    return
                                if len(args) == 3 and context.message.attachments: playlist = add_song_index_or_name(args[2], server, playlist_index)
                                elif len(args) == 4 and not context.message.attachments: playlist = add_song_index_or_name(args[3], server, playlist_index)
                                elif len(args) == 4: playlist = {"name": args[2], "index": int(args[3])}
                                elif len(args) == 5: playlist = {"name": args[3], "index": int(args[4])}
                                response = requests.get(url, stream = True)
                                # verify that the URL file is a media container
                                if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                                    await context.reply(self.polished_message(message = strings["not_media"],
                                                                              placeholders = ["song"],
                                                                              replacements = {"song": self.polished_song_name(url, playlist["name"])}))
                                    return

                                server["playlists"][playlist_index]["songs"].insert(playlist["index"] - 1, {"file": url,
                                                                                                            "name": playlist["name"],
                                                                                                            "time": "0",
                                                                                                            "silence": False})
                                await context.reply(self.polished_message(message = strings["playlist_add_song"],
                                                                          placeholders = ["playlist", "playlist_index", "song", "index"],
                                                                          replacements = {"playlist": playlists[playlist_index],
                                                                                          "playlist_index": playlist_index + 1,
                                                                                          "song": self.polished_song_name(url, playlist["name"]),
                                                                                          "index": playlist["index"]}))
                            elif args[1] == "move":
                                if len(args) == 4:
                                    song = server["playlists"][playlist_index]["songs"][int(args[2]) - 1]
                                    server["playlists"][playlist_index]["songs"].remove(song)
                                    server["playlists"][playlist_index]["songs"].insert(int(args[3]) - 1, song)
                                    await context.reply(self.polished_message(message = strings["playlist_move_song"],
                                                                              placeholders = ["playlist", "playlist_index", "song", "index"],
                                                                              replacements = {"playlist": playlists[playlist_index],
                                                                                              "playlist_index": playlist_index + 1,
                                                                                              "song": self.polished_song_name(song["file"], song["name"]),
                                                                                              "index": args[3]}))
                                else:
                                    await context.reply(strings["invalid_command"])
                                    return
                            elif args[1] == "rename":
                                if len(args) == 4:
                                    song = server["playlists"][playlist_index]["songs"][int(args[2]) - 1]
                                    await context.reply(self.polished_message(message = strings["playlist_rename_song"],
                                                                              placeholders = ["playlist", "playlist_index", "song", "index", "name"],
                                                                              replacements = {"playlist": server["playlists"][playlist_index]["name"],
                                                                                              "playlist_index": playlist_index + 1,
                                                                                              "song": self.polished_song_name(song["file"], song["name"]),
                                                                                              "index": args[2],
                                                                                              "name": args[3]}))
                                    song["name"] = args[3]
                                else:
                                    await context.reply(strings["invalid_command"])
                                    return
                            elif args[1] == "remove":
                                if len(args) == 3:
                                    song = server["playlists"][playlist_index]["songs"][int(args[2]) - 1]
                                    server["playlists"][playlist_index]["songs"].remove(song)
                                    await context.reply(self.polished_message(message = strings["playlist_remove_song"],
                                                                              placeholders = ["playlist", "playlist_index", "song", "index"],
                                                                              replacements = {"playlist": server["playlists"][playlist_index]["name"],
                                                                                              "playlist_index": playlist_index + 1,
                                                                                              "song": self.polished_song_name(song["file"], song["name"]),
                                                                                              "index": args[2]}))
                                else:
                                    await context.reply(strings["invalid_command"])
                                    return
                            elif args[1] == "list":
                                message = ""
                                if server["playlists"][playlist_index]["songs"]:
                                    if server["playlists"][playlist_index]:
                                        message += self.polished_message(message = strings["playlist_songs_header"] + "\n",
                                                                         placeholders = ["playlist", "playlist_index"],
                                                                         replacements = {"playlist": playlists[playlist_index],
                                                                                         "playlist_index": playlist_index + 1})
                                    else:
                                        await context.reply(strings["no_playlists"])
                                        return
                                else:
                                    await context.reply(self.polished_message(message = strings["playlist_no_songs"],
                                                                              placeholders = ["playlist", "playlist_index"],
                                                                              replacements = {"playlist": playlists[playlist_index],
                                                                                              "playlist_index": playlist_index + 1}))
                                    return
                                index = 0
                                while index < len(server["playlists"][playlist_index]["songs"]):
                                    message += self.polished_message(message = strings["song"] + "\n",
                                                                     placeholders = ["song", "index"],
                                                                     replacements = {"song": self.polished_song_name(server["playlists"][playlist_index]
                                                                                                                           ["songs"][index]["file"],
                                                                                                                     server["playlists"][playlist_index]
                                                                                                                           ["songs"][index]["name"]),
                                                                                     "index": index + 1})
                                    index += 1
                                await context.reply(message)
                                return
                            else:
                                await context.reply(strings["invalid_command"])
                                return
                    except ValueError:
                        await context.reply(self.polished_message(message = strings["invalid_playlist"],
                                                                  placeholders = ["playlist"],
                                                                  replacements = {"playlist": args[0]}))
                        return
                # modify the YAML file to reflect changes regarding playlists
                with open(self.config, "w") as write_file: yaml.dump(data, write_file, yaml.Dumper, indent = 4)
                break

    @commands.command()
    async def play(self, context, *args):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                invalid_command = server["strings"]["invalid_command"]
                break
        if not args:
            if context.message.attachments: await self.play_song(context, str(context.message.attachments[0]))
            else: await context.reply(invalid_command)
        elif len(args) == 1:
            if context.message.attachments: await self.play_song(context, str(context.message.attachments[0]), args[0])
            else: await self.play_song(context, args[0])
        elif len(args) == 2: await self.play_song(context, args[0], args[1])
        else: await context.reply(invalid_command)

    async def play_song(self, context, url = None, name = None, playlist = []):
        async def add_time(server, time): server["time"] += time
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                try: voice_channel = context.message.author.voice.channel
                except: voice_channel = None
                if voice_channel is not None:
                    if url is not None:
                        response = requests.get(url, stream = True)
                        # verify that the URL file is a media container
                        if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                            await context.reply(self.polished_message(message = server["strings"]["not_media"],
                                                                      placeholders = ["song"],
                                                                      replacements = {"song": self.polished_song_name(url, name)}))
                            return
                        await context.reply(self.polished_message(message = server["strings"]["queue_add_song"],
                                                                  placeholders = ["song", "index"],
                                                                  replacements = {"song": self.polished_song_name(url, name),
                                                                                  "index": len(server['queue']) + 1}))
                        # add the song to the queue
                        server["queue"].append({"file": url, "name": name, "time": "0", "silence": False})
                    else:
                        message = ""
                        for song in playlist:
                            message += self.polished_message(message = server["strings"]["queue_add_song"] + "\n",
                                                             placeholders = ["song", "index"],
                                                             replacements = {"song": self.polished_song_name(song["file"], song["name"]),
                                                             "index": len(server['queue']) + 1})
                            # add the song to the queue
                            server["queue"].append(song)
                        await context.reply(message)
                    if not server["connected"]:
                        voice = await voice_channel.connect()
                        server["connected"] = True
                        await context.guild.change_voice_state(channel = voice_channel, self_mute = False, self_deaf = True)
                    else: voice = context.guild.voice_client
                    if not voice.is_playing():
                        while server["index"] < len(server["queue"]):
                            if server["connected"]:
                                if not server["queue"][server["index"]]["silence"]:
                                    await context.send(self.polished_message(message = server["strings"]["now_playing"],
                                                                             placeholders = ["song", "index", "max"],
                                                                             replacements = {"song": self.polished_song_name(server["queue"][server["index"]]["file"],
                                                                                                                             server["queue"][server["index"]]["name"]),
                                                                                             "index": server["index"] + 1,
                                                                                             "max": len(server['queue'])}))
                                    server["time"] = .0
                                else: server["queue"][server["index"]]["silence"] = False
                            # play the song
                            if not voice.is_playing():
                                source = discord.FFmpegPCMAudio(source = server["queue"][server["index"]]["file"],
                                                                before_options = f"-ss {server['queue'][server['index']]['time']}")
                                source.read()
                                voice.play(source)
                                server["queue"][server["index"]]["time"] = "0"
                                voice.source = discord.PCMVolumeTransformer(voice.source, volume = 1.0)
                                voice.source.volume = server["volume"]
                            # ensure that the song plays completely or is skipped by command before proceeding
                            while voice.is_playing() or voice.is_paused():
                                await asyncio.sleep(.1)
                                if voice.is_playing(): await add_time(server, .1)

                            server["index"] += 1
                            if server["index"] == len(server["queue"]):
                                if not server["repeat"]: await self.stop_music(context)
                                server["index"] = 0
                else: await context.reply(self.polished_message(message = server["strings"]["not_in_voice"],
                                                                placeholders = ["user"],
                                                                replacements = {"user": context.message.author.mention}))
                break

    @commands.command()
    async def insert(self, context, *args):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                invalid_command = server["strings"]["invalid_command"]
                break
        if len(args) == 1:
            if context.message.attachments: await self.insert_song(context, str(context.message.attachments[0]), None, args[0])
            else: await context.reply(invalid_command)
        elif len(args) == 2:
            if context.message.attachments: await self.insert_song(context, str(context.message.attachments[0]), args[0], args[1])
            else: await self.insert_song(context, args[0], None, args[1])
        elif len(args) == 3: await self.insert_song(context, args[0], args[1], args[2])
        else: await context.reply(invalid_command)

    async def insert_song(self, context, url, name, index, time = "0", silence = False):
        try: voice_channel = context.message.author.voice.channel
        except: voice_channel = None
        if voice_channel is not None:
            for server in self.servers:
                if server["id"] == context.message.guild.id:
                    if int(index) > 0 and int(index) < len(server["queue"]) + 2:
                        response = requests.get(url, stream = True)
                        # verify that the URL file is a media container
                        if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                            await context.reply(self.polished_message(message = server["strings"]["not_media"],
                                                                      placeholders = ["song"],
                                                                      replacements = {"song": self.polished_song_name(url, name)}))
                            return
                        # add the song to the queue
                        server["queue"].insert(int(index) - 1, {"file": url, "name": name, "time": time, "silence": silence})
                        if int(index) - 1 <= server["index"]: server["index"] += 1
                        if not silence: await context.reply(self.polished_message(message = server["strings"]["queue_insert_song"],
                                                                                  placeholders = ["song", "index"],
                                                                                  replacements = {"song": self.polished_song_name(url, name),
                                                                                                  "index": index}))
                        break
                    else: await context.reply(self.polished_message(message = server["strings"]["invalid_song_number"],
                                                                    placeholders = ["index"],
                                                                    replacements = {"index": index}))
        else: await context.reply(self.polished_message(message = server["strings"]["not_in_voice"],
                                                        placeholders = ["user"],
                                                        replacements = {"user": context.message.author.mention}))

    @commands.command()
    async def move(self, context, index, move_to_index):
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                if int(index) > 0 and int(index) < len(server["queue"]) + 1:
                    if int(move_to_index) > 0 and int(move_to_index) < len(server["queue"]) + 1:
                        queue = server["queue"].copy()
                        server["queue"].remove(queue[int(index) - 1])
                        server["queue"].insert(int(move_to_index) - 1, queue[int(index) - 1])
                        await context.reply(self.polished_message(message = server["strings"]["queue_move_song"],
                                                                  placeholders = ["song", "index"],
                                                                  replacements = {"song": self.polished_song_name(queue[int(index) - 1]['file'],
                                                                                                                  queue[int(index) - 1]['name']),
                                                                                  "index": move_to_index}))
                    if int(index) - 1 < server["index"] and int(move_to_index) - 1 >= server["index"]: server["index"] -= 1
                    elif int(index) - 1 > server["index"] and int(move_to_index) - 1 <= server["index"]: server["index"] += 1
                    elif int(index) - 1 == server["index"] and int(move_to_index) - 1 != server["index"]: server["index"] = int(move_to_index) - 1
                    else: await context.reply(self.polished_message(message = server["strings"]["invalid_song_number"],
                                                                    placeholders = ["index"],
                                                                    replacements = {"index": move_to_index}))
                else: await context.reply(self.polished_message(message = server["strings"]["invalid_song_number"],
                                                                placeholders = ["index"],
                                                                replacements = {"index": index}))

    @commands.command()
    async def rename(self, context, index, name):
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                await context.reply(self.polished_message(message = server["strings"]["queue_rename_song"],
                                                          placeholders = ["song", "index", "name"],
                                                          replacements = {"song": self.polished_song_name(server["queue"][int(index) - 1]["file"],
                                                                                                          server["queue"][int(index) - 1]["name"]),
                                                                          "index": index,
                                                                          "name": name}))
                server["queue"][int(index) - 1]["name"] = name

    @commands.command()
    async def remove(self, context, index): await self.remove_song(context, index)
    
    async def remove_song(self, context, index, silence = False):
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                if int(index) > 0 and int(index) < len(server["queue"]) + 1:
                    if not silence: await context.reply(self.polished_message(message = server["strings"]["queue_remove_song"],
                                                                              placeholders = ["song", "index"],
                                                                              replacements = {"song": self.polished_song_name(server["queue"][int(index) - 1]["file"],
                                                                                                                              server["queue"][int(index) - 1]["name"]),
                                                                                              "index": index}))
                    # remove the song from the queue
                    server["queue"].remove(server["queue"][int(index) - 1])
                    if int(index) - 1 < server["index"]: server["index"] -= 1
                    elif int(index) - 1 == server["index"]:
                        server["index"] -= 1
                        context.voice_client.stop()
                    break
                else: await context.reply(self.polished_message(message = server["strings"]["invalid_song_number"],
                                                                placeholders = ["index"],
                                                                replacements = {"index": index}))

    @commands.command()
    async def skip(self, context): context.voice_client.stop()

    @commands.command()
    async def previous(self, context):
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                if server["index"] > 0: server["index"] -= 2
                elif server["queue"]: server["index"] = len(server["queue"]) - 2
                context.voice_client.stop()

    @commands.command()
    async def stop(self, context): await self.stop_music(context)

    async def stop_music(self, context, leave = False, guild = None):
        if guild is None: id = context.message.guild.id
        else: id = guild.id
        # remove all the songs by the calling Discord server
        for server in self.servers:
            if server["id"] == id:
                while server["queue"]:
                    # remove the song from the queue
                    server["queue"].remove(server["queue"][0])
                if context.voice_client.is_playing():
                    server["index"] = -1
                    context.voice_client.stop()
                else: server["index"] = 0
                if leave or not server["keep"]:
                    await context.voice_client.disconnect()
                    server["connected"] = False
                break

    @commands.command()
    async def pause(self, context):
        if context.voice_client.is_paused(): context.voice_client.resume()
        else: context.voice_client.pause()

    @commands.command()
    async def jump(self, context, time): await self.jump_to(context, time)

    async def jump_to(self, context, time):
        self.initialize_servers()
        segments = []
        if ":" in time: segments = time.split(":")
        if len(segments) == 2: seconds = float(segments[0]) * 60 + float(segments[1])
        elif len(segments) == 3: seconds = float(segments[0]) * 60 + float(segments[1]) * 60 + float(segments[2])
        else: seconds = float(time)
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                    if server["queue"]:
                        server["time"] = seconds
                        await self.insert_song(context,
                                               server["queue"][server["index"]]["file"],
                                               server["queue"][server["index"]]["name"],
                                               server["index"] + 2, seconds,
                                               True)
                        await self.remove_song(context, server["index"] + 1, True)
                    else: await context.reply(server["strings"]["queue_no_songs"])
                    break

    @commands.command()
    async def forward(self, context, time):
        for server in self.servers:
            if server["id"] == context.message.guild.id: await self.jump_to(context, str(float(server["time"]) + float(time)))

    @commands.command()
    async def rewind(self, context, time):
        for server in self.servers:
            if server["id"] == context.message.guild.id: await self.jump_to(context, str(float(server["time"]) - float(time)))

    @commands.command()
    async def when(self, context):
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
            if server["id"] == context.message.guild.id:
                if server["queue"]: await context.reply(convert_to_time(server["time"]))
                else: await context.reply(server["strings"]["queue_no_songs"])

    @commands.command()
    async def loop(self, context):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                strings = server["strings"]
                break
        with open(self.config, "r") as read_file: data = yaml.load(read_file, yaml.Loader)
        for server in data["servers"]:
            if server["id"] == context.message.guild.id:
                repeat = not server["repeat"]
                server["repeat"] = repeat
                # modify the YAML file to reflect the change of whether playlist looping is enabled or disabled
                with open(self.config, "w") as write_file: yaml.dump(data, write_file, yaml.Dumper, indent = 4)

                if self.servers: self.servers[data["servers"].index(server)]["repeat"] = repeat
                break
        if repeat: now_or_no_longer = strings["now"]
        else: now_or_no_longer = strings["no_longer"]
        await context.reply(self.polished_message(message = strings["repeat"],
                                                  placeholders = ["now_or_no_longer"],
                                                  replacements = {"now_or_no_longer": now_or_no_longer}))

    @commands.command()
    async def queue(self, context):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                queue_no_songs = server["strings"]["queue_no_songs"]
                message = ""
                if server["queue"]: message += server["strings"]["queue_songs_header"] + "\n"
                else:
                    await context.reply(queue_no_songs)
                    return
                index = 0
                while index < len(server["queue"]):
                    message += self.polished_message(message = server["strings"]["song"] + "\n",
                                                     placeholders = ["song", "index"],
                                                     replacements = {"song": self.polished_song_name(server["queue"][index]["file"], server["queue"][index]["name"]),
                                                                     "index": index + 1})
                    index += 1
                await context.reply(message)

    @commands.command()
    async def volume(self, context, *args):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                if args:
                    if args[0].endswith("%"): server["volume"] = float(args[0].replace("%", "")) / 100
                    else: server["volume"] = float(args[0])
                    if context.voice_client is not None:
                        if context.voice_client.is_playing(): context.voice_client.source.volume = server["volume"]
                volume_percent = server["volume"] * 100
                if volume_percent == float(int(volume_percent)): volume_percent = int(volume_percent)
                if args: await context.reply(self.polished_message(message = server["strings"]["volume_change"],
                                                                   placeholders = ["volume"],
                                                                   replacements = {"volume": str(volume_percent) + "%"}))
                else: await context.reply(self.polished_message(message = server["strings"]["volume"],
                                                                placeholders = ["volume"],
                                                                replacements = {"volume": str(volume_percent) + "%"}))
                break

    @commands.command()
    async def keep(self, context):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                strings = server["strings"]
                break
        with open(self.config, "r") as read_file: data = yaml.load(read_file, yaml.Loader)
        for server in data["servers"]:
            if server["id"] == context.message.guild.id:
                keep = not server["keep"]
                server["keep"] = keep
                # modify the YAML file to reflect the change of whether to keep this bot in a voice call when no music is playing
                with open(self.config, "w") as write_file: yaml.dump(data, write_file, yaml.Dumper, indent = 4)

                if self.servers: self.servers[data["servers"].index(server)]["keep"] = keep
                break
        try: voice_channel = context.message.author.voice.channel.jump_url
        except: voice_channel = strings["whatever_voice"]
        if keep: now_or_no_longer = strings["now"]
        else: now_or_no_longer = strings["no_longer"]
        await context.reply(self.polished_message(message = strings["keep"],
                                                  placeholders = ["bot", "voice", "now_or_no_longer"],
                                                  replacements = {"bot": self.bot.user.mention,
                                                                  "voice": voice_channel,
                                                                  "now_or_no_longer": now_or_no_longer}))

    @commands.command()
    async def dismiss(self, context): await self.stop_music(context, True)

    # ensure that this bot disconnects from any empty voice channel it's in
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.guild.voice_client.is_connected():
            for voice_channel in member.guild.voice_channels:
                if voice_channel.voice_states:
                    if list(voice_channel.voice_states)[0] == self.bot.user.id and len(list(voice_channel.voice_states)) == 1:
                        await self.stop_music(member.guild, True, member.guild)
                        break
