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

    def polished_message(self, message, user = None, bot = None, voice = None, playlist = None, playlist_index = None, song = None, 
                         index = None, maximum = None, name = None, volume = None, now = None, no_longer = None, enabled = False):
        if user is not None: message = message.replace("%{user}", user)
        if bot is not None: message = message.replace("%{bot}", bot)
        if voice is not None: message = message.replace("%{voice}", voice)
        if playlist is not None: message = message.replace("%{playlist}", playlist)
        if playlist_index is not None: message = message.replace("%{playlist_index}", str(playlist_index))
        if song is not None: message = message.replace("%{song}", song)
        if index is not None: message = message.replace("%{index}", str(index))
        if maximum is not None: message = message.replace("%{max}", str(maximum))
        if name is not None: message = message.replace("%{name}", name)
        if volume is not None: message = message.replace("%{volume}", volume)
        if now is not None and enabled: message = message.replace("%{now_or_no_longer}", now)
        if no_longer is not None and not enabled: message = message.replace("%{now_or_no_longer}", no_longer)
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
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                invalid_command = server["strings"]["invalid_command"]
                no_playlists = server["strings"]["no_playlists"]
                playlists_header = server["strings"]["playlists_header"]
                add_playlist = server["strings"]["add_playlist"]
                rename_playlist = server["strings"]["rename_playlist"]
                remove_playlist = server["strings"]["remove_playlist"]
                playlist_no_songs = server["strings"]["playlist_no_songs"]
                playlist_songs_header = server["strings"]["playlist_songs_header"]
                playlist_add_song = server["strings"]["playlist_add_song"]
                playlist_move_song = server["strings"]["playlist_move_song"]
                playlist_rename_song = server["strings"]["playlist_rename_song"]
                playlist_remove_song = server["strings"]["playlist_remove_song"]
                playlist_listing = server["strings"]["playlist"]
                invalid_playlist = server["strings"]["invalid_playlist"]
                invalid_playlist_number = server["strings"]["invalid_playlist_number"]
                song_listing = server["strings"]["song"]
                not_media = server["strings"]["not_media"]
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
                        await context.reply(self.polished_message(message = add_playlist, playlist = args[1], playlist_index = len(server["playlists"])))
                    else:
                        await context.reply(invalid_command)
                        return
                elif args[0] == "rename":
                    if len(args) == 3:
                        try: index = int(args[1]) - 1
                        except ValueError: index = playlists.index(args[1])
                        await context.reply(self.polished_message(message = rename_playlist,
                                                                  playlist = playlists[index],
                                                                  playlist_index = index + 1,
                                                                  name = args[2]))
                        server["playlists"][index]["name"] = args[2]
                    else:
                        await context.reply(invalid_command)
                        return
                elif args[0] == "remove":
                    if len(args) == 2:
                        try: index = int(args[1]) - 1
                        except ValueError: index = playlists.index(args[1])
                        server["playlists"].remove(server["playlists"][index])
                        await context.reply(self.polished_message(message = remove_playlist, playlist = playlists[index], playlist_index = index + 1))
                    else:
                        await context.reply(invalid_command)
                        return
                elif args[0] == "load":
                    if len(args) == 2:
                        try: index = int(args[1]) - 1
                        except ValueError: index = playlists.index(args[1])
                        await self.play_song(context, playlist = server["playlists"][index]["songs"])
                        return
                elif args[0] == "list":
                    message = ""
                    if server["playlists"]: message += playlists_header + "\n"
                    else:
                        await context.reply(no_playlists)
                        return
                    index = 0
                    while index < len(server["playlists"]):
                        message += self.polished_message(message = playlist_listing, playlist = playlists[index], playlist_index = index + 1) + "\n"
                        index += 1
                    await context.reply(message)
                    return
                else:
                    try:
                        if args[0] in playlists or int(args[0]) > 0:
                            try:
                                playlist_index = int(args[0]) - 1
                                if playlist_index >= len(server["playlists"]) or playlist_index < 0:
                                    await context.reply(self.polished_message(message = invalid_playlist_number, playlist_index = playlist_index + 1))
                                    return
                            except ValueError: playlist_index = playlists.index(args[0])
                            if args[1] == "add":
                                if len(args) >= 3 and len(args) <= 5 and not context.message.attachments: url = args[2]
                                elif len(args) < 5 and context.message.attachments: url = str(context.message.attachments[0])
                                else:
                                    await context.reply(invalid_command)
                                    return
                                name = None
                                index = len(server["playlists"][playlist_index]["songs"]) + 1
                                if len(args) == 3 and context.message.attachments:
                                    try: index = int(args[2])
                                    except ValueError:
                                        index = len(server["playlists"][playlist_index]["songs"]) + 1
                                        name = args[2]
                                elif len(args) == 4 and not context.message.attachments:
                                    try: index = int(args[3])
                                    except ValueError:
                                        index = len(server["playlists"][playlist_index]["songs"]) + 1
                                        name = args[3]
                                elif len(args) == 4:
                                    name = args[2]
                                    index = int(args[3])
                                elif len(args) == 5:
                                    name = args[3] 
                                    index = int(args[4])
                                response = requests.get(url, stream = True)
                                # verify that the URL file is a media container
                                if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                                    await context.reply(self.polished_message(message = not_media, song = self.polished_song_name(url, name)))
                                    return

                                server["playlists"][playlist_index]["songs"].insert(index - 1, {"file": url, "name": name, "time": "00:00:00.00", "silence": False})
                                await context.reply(self.polished_message(message = playlist_add_song,
                                                                          playlist = playlists[playlist_index],
                                                                          playlist_index = playlist_index + 1,
                                                                          song = self.polished_song_name(url, name),
                                                                          index = index))
                            elif args[1] == "move":
                                if len(args) == 4:
                                    song = server["playlists"][playlist_index]["songs"][int(args[2]) - 1]
                                    server["playlists"][playlist_index]["songs"].remove(song)
                                    server["playlists"][playlist_index]["songs"].insert(int(args[3]) - 1, song)
                                    await context.reply(self.polished_message(message = playlist_move_song,
                                                                              playlist = playlists[playlist_index],
                                                                              playlist_index = playlist_index + 1,
                                                                              song = self.polished_song_name(song["file"], song["name"]),
                                                                              index = args[3]))
                                else:
                                    await context.reply(invalid_command)
                                    return
                            elif args[1] == "rename":
                                if len(args) == 4:
                                    song = server["playlists"][playlist_index]["songs"][int(args[2]) - 1]
                                    await context.reply(self.polished_message(message = playlist_rename_song,
                                                                              playlist = server["playlists"][playlist_index]["name"],
                                                                              playlist_index = playlist_index + 1,
                                                                              song = self.polished_song_name(song["file"], song["name"]),
                                                                              index = args[2],
                                                                              name = args[3]))
                                    song["name"] = args[3]
                                else:
                                    await context.reply(invalid_command)
                                    return
                            elif args[1] == "remove":
                                if len(args) == 3:
                                    song = server["playlists"][playlist_index]["songs"][int(args[2]) - 1]
                                    server["playlists"][playlist_index]["songs"].remove(song)
                                    await context.reply(self.polished_message(message = playlist_remove_song,
                                                                              playlist = server["playlists"][playlist_index]["name"],
                                                                              playlist_index = playlist_index + 1,
                                                                              song = self.polished_song_name(song["file"], song["name"]),
                                                                              index = args[2]))
                                else:
                                    await context.reply(invalid_command)
                                    return
                            elif args[1] == "list":
                                message = ""
                                if server["playlists"][playlist_index]["songs"]:
                                    if server["playlists"][playlist_index]:
                                        message += self.polished_message(message = playlist_songs_header,
                                                                         playlist = playlists[playlist_index],
                                                                         playlist_index = playlist_index + 1) + "\n"
                                    else:
                                        await context.reply(no_playlists)
                                        return
                                else:
                                    await context.reply(self.polished_message(message = playlist_no_songs,
                                                                              playlist = playlists[playlist_index],
                                                                              playlist_index = playlist_index + 1))
                                    return
                                index = 0
                                while index < len(server["playlists"][playlist_index]["songs"]):
                                    message += self.polished_message(message = song_listing + "\n",
                                                                     song = self.polished_song_name(server["playlists"][playlist_index]["songs"][index]["file"],
                                                                                                    server["playlists"][playlist_index]["songs"][index]["name"]),
                                                                     index = index + 1)
                                    index += 1
                                await context.reply(message)
                                return
                            else:
                                await context.reply(invalid_command)
                                return
                    except ValueError:
                        await context.reply(self.polished_message(message = invalid_playlist, playlist = args[0]))
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
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                try: voice_channel = context.message.author.voice.channel
                except: voice_channel = None
                if voice_channel is not None:
                    if url is not None:
                        response = requests.get(url, stream = True)
                        # verify that the URL file is a media container
                        if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                            await context.reply(self.polished_message(message = server["strings"]["not_media"], song = self.polished_song_name(url, name)))
                            return
                        await context.reply(self.polished_message(message = server["strings"]["queue_add_song"],
                                                                  song = self.polished_song_name(url, name),
                                                                  index = str(len(server['queue']) + 1)))
                        # add the song to the queue
                        server["queue"].append({"file": url, "name": name, "time": "00:00:00.00", "silence": False})
                    else:
                        for song in playlist:
                            await context.reply(self.polished_message(message = server["strings"]["queue_add_song"],
                                                                      song = self.polished_song_name(song["file"], song["name"]),
                                                                      index = str(len(server['queue']) + 1)))
                            # add the song to the queue
                            server["queue"].append(song)
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
                                                                             song = self.polished_song_name(server["queue"][server["index"]]["file"],
                                                                                                            server["queue"][server["index"]]["name"]),
                                                                             index = str(server["index"] + 1),
                                                                             maximum = str(len(server['queue']))))
                                    server["time"] = .0
                                else: server["queue"][server["index"]]["silence"] = False
                            # play the song
                            if not voice.is_playing():
                                voice.play(discord.FFmpegPCMAudio(source = server["queue"][server["index"]]["file"],
                                                                  before_options = f"-ss {server['queue'][server['index']]['time']}"))
                                
                                server["queue"][server["index"]]["time"] = "00:00:00.00"
                                voice.source = discord.PCMVolumeTransformer(voice.source, volume = 1.0)
                                voice.source.volume = server["volume"]
                            # ensure that the song plays completely or is skipped by command before proceeding
                            while voice.is_playing() or voice.is_paused():
                                await asyncio.sleep(.1)
                                if voice.is_playing(): await self.add_time(context, .1)

                            server["index"] += 1
                            if server["index"] == len(server["queue"]):
                                if not server["repeat"]: await self.stop_music(context)
                                server["index"] = 0
                else: await context.reply(self.polished_message(message = server["strings"]["not_in_voice"], user = str(context.message.author.mention)))
                break

    async def add_time(self, context, time):
        for server in self.servers:
            if server["id"] == context.message.guild.id: server["time"] += time

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

    async def insert_song(self, context, url, name, index, time = "00:00:00.00", silence = False):
        try: voice_channel = context.message.author.voice.channel
        except: voice_channel = None
        if voice_channel is not None:
            for server in self.servers:
                if server["id"] == context.message.guild.id:
                    if int(index) > 0 and int(index) < len(server["queue"]) + 2:
                        response = requests.get(url, stream = True)
                        # verify that the URL file is a media container
                        if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                            await context.reply(self.polished_message(message = server["strings"]["not_media"], song = self.polished_song_name(url, name)))
                            return
                        # add the song to the queue
                        server["queue"].insert(int(index) - 1, {"file": url, "name": name, "time": time, "silence": silence})
                        if int(index) - 1 <= server["index"]: server["index"] += 1
                        if not silence: await context.reply(self.polished_message(message = server["strings"]["queue_insert_song"],
                                                                                  song = self.polished_song_name(url, name),
                                                                                  index = index))
                        break
                    else: await context.reply(self.polished_message(message = server["strings"]["invalid_song_number"], index = index))
        else: await context.reply(self.polished_message(message = server["strings"]["not_in_voice"], user = str(context.message.author.mention)))

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
                                                                  song = self.polished_song_name(queue[int(index) - 1]['file'],
                                                                                                 queue[int(index) - 1]['name']),
                                                                  index = move_to_index))
                    if int(index) - 1 < server["index"] and int(move_to_index) - 1 >= server["index"]: server["index"] -= 1
                    elif int(index) - 1 > server["index"] and int(move_to_index) - 1 <= server["index"]: server["index"] += 1
                    elif int(index) - 1 == server["index"] and int(move_to_index) - 1 != server["index"]: server["index"] = int(move_to_index) - 1
                    else: await context.reply(self.polished_message(message = server["strings"]["invalid_song_number"], index = move_to_index))
                else: await context.reply(self.polished_message(message = server["strings"]["invalid_song_number"], index = index))

    @commands.command()
    async def rename(self, context, index, name):
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                await context.reply(self.polished_message(message = server["strings"]["queue_rename_song"],
                                                          song = self.polished_song_name(server["queue"][int(index) - 1]["file"],
                                                                                         server["queue"][int(index) - 1]["name"]),
                                                          name = name,
                                                          index = index))
                server["queue"][int(index) - 1]["name"] = name

    @commands.command()
    async def remove(self, context, index): await self.remove_song(context, index)
    
    async def remove_song(self, context, index, silence = False):
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                if int(index) > 0 and int(index) < len(server["queue"]) + 1:
                    if not silence: await context.reply(self.polished_message(message = server["strings"]["queue_remove_song"],
                                                                              song = self.polished_song_name(server["queue"][int(index) - 1]["file"],
                                                                                                             server["queue"][int(index) - 1]["name"]),
                                                                              index = index))
                    # remove the song from the queue
                    server["queue"].remove(server["queue"][int(index) - 1])
                    if int(index) - 1 < server["index"]: server["index"] -= 1
                    elif int(index) - 1 == server["index"]:
                        server["index"] -= 1
                        context.voice_client.stop()
                    break
                else: await context.reply(self.polished_message(message = server["strings"]["invalid_song_number"], index = index))

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
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                if server["queue"]: await context.reply(self.convert_to_time(server["time"]))
                else: await context.reply(server["strings"]["queue_no_songs"])

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

    @commands.command()
    async def loop(self, context):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                repeat_message = server["strings"]["repeat"]
                now = server["strings"]["now"]
                no_longer = server["strings"]["no_longer"]
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
        await context.reply(self.polished_message(message = repeat_message, now = now, no_longer = no_longer, enabled = repeat))

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
                                                     song = self.polished_song_name(server["queue"][index]["file"], server["queue"][index]["name"]),
                                                     index = index + 1)
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
                if args: await context.reply(self.polished_message(message = server["strings"]["volume_change"], volume = str(volume_percent) + "%"))
                else: await context.reply(self.polished_message(message = server["strings"]["volume"], volume = str(volume_percent) + "%"))
                break

    @commands.command()
    async def keep(self, context):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                keep_message = server["strings"]["keep"]
                now = server["strings"]["now"]
                no_longer = server["strings"]["no_longer"]
                whatever = server["strings"]["whatever_voice"]
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
        except: voice_channel = whatever
        await context.reply(self.polished_message(message = keep_message,
                                                  bot = self.bot.user.mention,
                                                  voice = voice_channel,
                                                  now = now,
                                                  no_longer = no_longer,
                                                  enabled = keep))

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
