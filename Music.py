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

    def polished_message(self, message, user = None, bot = None, voice = None, song = None, index = None,
                         maximum = None, volume = None, now = None, no_longer = None, enabled = False):
        if user is not None: message = message.replace("%{user}", user)
        if bot is not None: message = message.replace("%{bot}", bot)
        if voice is not None: message = message.replace("%{voice}", voice)
        if song is not None: message = message.replace("%{song}", song)
        if index is not None: message = message.replace("%{index}", str(index))
        if maximum is not None: message = message.replace("%{max}", str(maximum))
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
                                                                 "volume": 1.0,
                                                                 "repeat": server["repeat"],
                                                                 "keep": server["keep"],
                                                                 "queue": [],
                                                                 "index": 0,
                                                                 "connected": False,
                                                                 "strings": language["strings"]})

    @commands.command()
    async def play(self, context, *args):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                invalid_command = server["strings"]["invalid_command"]
                break
        if not args:
            if context.message.attachments: await self.play_song(context, str(context.message.attachments[0]))
            else: await context.reply(self.polished_message(invalid_command))
        elif len(args) == 1:
            if context.message.attachments: await self.play_song(context, str(context.message.attachments[0]), args[0])
            else: await self.play_song(context, args[0])
        elif len(args) == 2: await self.play_song(context, args[0], args[1])
        else: await context.reply(self.polished_message(invalid_command))

    async def play_song(self, context, url, name = None):
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                try: voice_channel = context.message.author.voice.channel
                except Exception: voice_channel = None
                if voice_channel is not None:
                    request = requests.get(url, stream = True)
                    # verify that the url file is a media container
                    if "audio" not in request.headers.get("Content-Type", "") and "video" not in request.headers.get("Content-Type", ""):
                        await context.reply(self.polished_message(message = server["strings"]["not_media"], song = self.polished_song_name(url, name)))
                        return
                    # add the attached file to the queue
                    await context.reply(self.polished_message(message = server["strings"]["play"],
                                                              song = self.polished_song_name(url, name),
                                                              index = str(len(server['queue']) + 1)))

                    server["queue"].append({"file": url, "name": name})
                    if not server["connected"]:
                        voice = await voice_channel.connect()
                        server["connected"] = True
                        await context.guild.change_voice_state(channel = voice_channel, self_mute = False, self_deaf = True)
                    else: voice = context.guild.voice_client
                    if not voice.is_playing():
                        while server["index"] < len(server["queue"]):
                            if server["connected"]:
                                await context.send(self.polished_message(message = server["strings"]["now_playing"],
                                                                         song = self.polished_song_name(server["queue"][server["index"]]["file"],
                                                                                                        server["queue"][server["index"]]["name"]),
                                                                         index = str(server["index"] + 1),
                                                                         maximum = str(len(server['queue']))))
                            # play the attached audio file
                            if not voice.is_playing():
                                source = discord.FFmpegPCMAudio(url)
                                source.read()
                                voice.play(source)
                                voice.source = discord.PCMVolumeTransformer(voice.source, volume = 1.0)
                                voice.source.volume = server["volume"]
                            # ensure that the audio file plays completely or is skipped by command before proceeding
                            while voice.is_playing() or voice.is_paused(): await asyncio.sleep(.1)

                            server["index"] += 1
                            if server["index"] == len(server["queue"]):
                                if not server["repeat"]: await self.stop_music(context)
                                server["index"] = 0
                else: await context.reply(self.polished_message(message = server["strings"]["not_in_voice"], user = str(context.message.author.mention)))
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
            else: await context.reply(self.polished_message(invalid_command))
        elif len(args) == 2:
            if context.message.attachments: await self.insert_song(context, str(context.message.attachments[0]), args[0], args[1])
            else: await self.insert_song(context, args[0], None, args[1])
        elif len(args) == 3: await self.insert_song(context, args[0], args[1], args[2])
        else: await context.reply(self.polished_message(invalid_command))

    async def insert_song(self, context, url, name, index):
        try: voice_channel = context.message.author.voice.channel
        except Exception: voice_channel = None
        if voice_channel is not None:
            for server in self.servers:
                if server["id"] == context.message.guild.id:
                    if int(index) > 0 and int(index) < len(server["queue"]) + 1:
                        request = requests.get(url, stream = True)
                        # verify that the url file is a media container
                        if "audio" not in request.headers.get("Content-Type", "") and "video" not in request.headers.get("Content-Type", ""):
                            await context.reply(self.polished_message(message = server["strings"]["not_media"], song = self.polished_song_name(url, name)))
                            return
                        # add the attached file to the queue
                        server["queue"].insert(int(index) - 1, {"file": url, "name": name})
                        if int(index) - 1 <= server["index"]: server["index"] += 1
                        await context.reply(self.polished_message(message = server["strings"]["insert"],
                                                                  song = self.polished_song_name(url, name),
                                                                  index = index))
                        break
                    else: await context.reply(self.polished_message(message = server["strings"]["invalid_index"], index = index))
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
                        await context.reply(self.polished_message(message = server["strings"]["move"],
                                                                  song = self.polished_song_name(queue[int(index) - 1]['file'],
                                                                                                 queue[int(index) - 1]['name']),
                                                                  index = move_to_index))
                    if int(index) - 1 < server["index"] and int(move_to_index) - 1 >= server["index"]: server["index"] -= 1
                    elif int(index) - 1 > server["index"] and int(move_to_index) - 1 <= server["index"]: server["index"] += 1
                    elif int(index) - 1 == server["index"] and int(move_to_index) - 1 != server["index"]: server["index"] = int(move_to_index) - 1
                    else: await context.reply(self.polished_message(message = server["strings"]["invalid_index"], index = move_to_index))
                else: await context.reply(self.polished_message(message = server["strings"]["invalid_index"], index = index))

    @commands.command()
    async def remove(self, context, index):
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                if int(index) > 0 and int(index) < len(server["queue"]) + 1:
                    await context.reply(self.polished_message(message = server["strings"]["remove"],
                                                              song = self.polished_song_name(server["queue"][int(index) - 1]["file"],
                                                                                             server["queue"][int(index) - 1]["name"]),
                                                              index = index))
                    # remove the audio file from the queue
                    server["queue"].remove(server["queue"][int(index) - 1])
                    if int(index) - 1 < server["index"]: server["index"] -= 1
                    elif int(index) - 1 == server["index"]:
                        server["index"] -= 1
                        context.voice_client.stop()
                    break
                else: await context.reply(self.polished_message(message = server["strings"]["invalid_index"], index = index))

    @commands.command()
    async def skip(self, context): context.voice_client.stop()

    @commands.command()
    async def previous(self, context):
        for server in self.servers:
            if server["index"] > 0: server["index"] -= 2
            elif server["queue"]: server["index"] = len(server["queue"]) - 2
            context.voice_client.stop()

    @commands.command()
    async def stop(self, context): await self.stop_music(context)

    async def stop_music(self, context, leave = False, guild = None):
        if guild is None: id = context.message.guild.id
        else: id = guild.id
        # remove all the files by the calling Discord server
        for server in self.servers:
            if server["id"] == id:
                while server["queue"]:
                    # remove the audio file from the queue
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
    async def volume(self, context, volume):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                if volume.endswith("%"): server["volume"] = float(volume.replace("%", "")) / 100
                else: server["volume"] = float(volume)
                if context.voice_client is not None:
                    if context.voice_client.is_playing(): context.voice_client.source.volume = server["volume"]
                volume_percent = server["volume"] * 100
                if volume_percent == float(int(volume_percent)): volume_percent = int(volume_percent)
                await context.reply(self.polished_message(message = server["strings"]["volume"], volume = str(volume_percent) + "%"))
                break

    @commands.command()
    async def loop(self, context):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                now = server["strings"]["now"]
                no_longer = server["strings"]["no_longer"]
                repeat_message = server["strings"]["repeat"]
                break
        with open(self.config, "r") as read_file: data = yaml.load(read_file, yaml.Loader)
        for server in data["servers"]:
            if server["id"] == context.message.guild.id:
                repeat = not server["repeat"]
                server["repeat"] = repeat
                # modify the YAML file to reflect the change in whether playlist looping is enabled or disabled
                with open(self.config, "w") as write_file: yaml.dump(data, write_file, yaml.Dumper, indent = 4)

                if self.servers: self.servers[data["servers"].index(server)]["repeat"] = repeat
                break
        await context.reply(self.polished_message(message = repeat_message, now = now, no_longer = no_longer, enabled = repeat))

    @commands.command()
    async def queue(self, context):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                no_songs_message = server["strings"]["no_songs"]
                message = ""
                if len(server["queue"]): message += self.polished_message(server["strings"]["queue"]) + "\n"
                else: await context.reply(self.polished_message(no_songs_message))
                index = 0
                while index < len(server["queue"]):
                    message += self.polished_message(message = server["strings"]["song"] + "\n",
                                                     song = self.polished_song_name(server["queue"][index]["file"], server["queue"][index]["name"]),
                                                     index = index + 1)
                    index += 1
                await context.reply(message)
        if not self.servers: await context.reply(self.polished_message(no_songs_message))

    @commands.command()
    async def keep(self, context):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                now = server["strings"]["now"]
                no_longer = server["strings"]["no_longer"]
                keep_message = server["strings"]["keep"]
                whatever = server["strings"]["whatever_voice"]
                break
        with open(self.config, "r") as read_file: data = yaml.load(read_file, yaml.Loader)
        for server in data["servers"]:
            if server["id"] == context.message.guild.id:
                keep = not server["keep"]
                server["keep"] = keep
                # modify the YAML file to reflect the change in whether keeping this bot in a voice call when no music is playing is enabled or disabled
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