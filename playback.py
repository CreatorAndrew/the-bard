from asyncio import sleep
from random import randint
from yaml import safe_dump as dump
from io import BytesIO
from requests import get
from discord import FFmpegPCMAudio, PCMVolumeTransformer
from discord.app_commands import Choice
from utils import page_selector, polished_message, polished_url, VARIABLES

if VARIABLES["multimedia_backend"] == "lavalink":
    import pomice


def convert_to_seconds(time):
    segments = []
    if ":" in time:
        segments = time.split(":")
    if len(segments) == 2:
        seconds = float(segments[0]) * 60 + float(segments[1])
    elif len(segments) == 3:
        seconds = (
            float(segments[0]) * 3600 + float(segments[1]) * 60 + float(segments[2])
        )
    else:
        seconds = float(time)
    return seconds


def convert_to_time_marker(number):
    segments = []
    temp_number = number
    if temp_number >= 3600:
        segments.append(str(int(temp_number / 3600)))
        temp_number %= 3600
    else:
        segments.append("00")
    if temp_number >= 60:
        segments.append(str(int(temp_number / 60)))
        temp_number %= 60
    else:
        segments.append("00")
    segments.append(str(int(temp_number)))
    marker = ""
    for index, segment in enumerate(segments, 1):
        if len(segment) == 1:
            segment = "0" + segment
        marker += segment
        if index < len(segments):
            marker += ":"
    return marker


async def play_command(self, context, file, song_url, new_name):
    await context.response.defer()
    if file is None and song_url is not None:
        await self.play_song(context, song_url, new_name)
    elif file is not None and song_url is None:
        await self.play_song(context, str(file), new_name)
    else:
        await context.followup.delete_message(
            (await context.followup.send("...", silent=True)).id
        )
        await context.followup.send(
            self.guilds[str(context.guild.id)]["strings"]["invalid_command"],
            ephemeral=True,
        )


async def play_song(self, context, url, name, playlist):
    try:

        async def add_time(guild, time):
            guild["time"] += time

        guild = self.guilds[str(context.guild.id)]
        try:
            voice_channel = context.user.voice.channel
        except:
            voice_channel = None
        if voice_channel is None:
            await context.followup.delete_message(
                (await context.followup.send("...", silent=True)).id
            )
            await context.followup.send(
                polished_message(
                    guild["strings"]["not_in_voice"], {"user": context.user.mention}
                ),
                ephemeral=True,
            )
        else:
            if url is None:
                if playlist is None:
                    playlist = []
                for song in playlist:
                    # add the track to the queue
                    guild["queue"].append(
                        {
                            "file": song["file"],
                            "name": song["name"],
                            "time": "0",
                            "duration": song["duration"],
                            "silent": False,
                        }
                    )
            else:
                response = get(url, stream=True)
                try:
                    metadata = self.get_metadata(BytesIO(response.content), url)
                except:
                    await context.followup.delete_message(
                        (await context.followup.send("...", silent=True)).id
                    )
                    return await context.followup.send(
                        polished_message(guild["strings"]["invalid_url"], {"url": url}),
                        ephemeral=True,
                    )
                if name is None:
                    name = metadata["name"]

                # verify that the URL file is a media container
                if not any(
                    content_type in response.headers.get("Content-Type", "")
                    for content_type in ["audio", "video"]
                ):
                    await context.followup.delete_message(
                        (await context.followup.send("...", silent=True)).id
                    )
                    return await context.followup.send(
                        polished_message(
                            guild["strings"]["invalid_song"],
                            {"song": polished_url(url, name)},
                        ),
                        ephemeral=True,
                    )
                await context.followup.send(
                    polished_message(
                        guild["strings"]["queue_add_song"],
                        {
                            "song": polished_url(url, name),
                            "index": len(guild["queue"]) + 1,
                        },
                    )
                )
                # add the track to the queue
                guild["queue"].append(
                    {
                        "file": url,
                        "name": name,
                        "time": "0",
                        "duration": metadata["duration"],
                        "silent": False,
                    }
                )
            if guild["connected"]:
                voice = context.guild.voice_client
            else:
                voice = (
                    (await voice_channel.connect(cls=pomice.Player))
                    if self.use_lavalink
                    else await voice_channel.connect()
                )
                guild["connected"] = True
                await context.guild.change_voice_state(
                    channel=voice_channel, self_mute=False, self_deaf=True
                )
            if not (voice.is_playing if self.use_lavalink else voice.is_playing()):
                while guild["index"] < len(guild["queue"]):
                    if guild["connected"]:
                        if guild["queue"][guild["index"]]["silent"]:
                            guild["queue"][guild["index"]]["silent"] = False
                        else:
                            await context.channel.send(
                                polished_message(
                                    guild["strings"]["now_playing"],
                                    {
                                        "song": polished_url(
                                            guild["queue"][guild["index"]]["file"],
                                            guild["queue"][guild["index"]]["name"],
                                        ),
                                        "index": guild["index"] + 1,
                                        "max": len(guild["queue"]),
                                    },
                                )
                            )
                    # play the track
                    if self.use_lavalink and not voice.is_playing:
                        await voice.play(
                            (
                                await voice.get_tracks(
                                    guild["queue"][guild["index"]]["file"]
                                )
                            )[0],
                        )
                        await voice.set_volume(int(guild["volume"] * 100))
                    elif not voice.is_playing():
                        voice.play(
                            FFmpegPCMAudio(
                                source=guild["queue"][guild["index"]]["file"],
                                before_options=f"-re -ss {guild['queue'][guild['index']]['time']}",
                            )
                        )
                        guild["queue"][guild["index"]]["time"] = "0"
                        voice.source = PCMVolumeTransformer(voice.source, volume=1.0)
                        voice.source.volume = guild["volume"]
                    # ensure that the track plays completely or is skipped by command before proceeding
                    while (
                        (voice.is_playing or voice.is_paused)
                        if self.use_lavalink
                        else (voice.is_playing() or voice.is_paused())
                    ):
                        await sleep(0.1)
                        if not self.use_lavalink and voice.is_playing():
                            await add_time(guild, 0.1)

                    guild["index"] += 1
                    if guild["index"] == len(guild["queue"]):
                        if not guild["repeat"]:
                            await self.stop_music(context)
                        guild["index"] = 0
    except:
        pass


async def insert_command(self, context, file, song_url, new_name, new_index):
    if file is None and new_index is not None and song_url is not None:
        await self.insert_song(context, song_url, new_name, new_index)
    elif file is not None and new_index is not None and song_url is None:
        await self.insert_song(context, str(file), new_name, new_index)
    else:
        await context.response.send_message(
            self.guilds[str(context.guild.id)]["strings"]["invalid_command"]
        )


async def insert_song(self, context, url, name, index, time, duration, silent):
    guild = self.guilds[str(context.guild.id)]
    try:
        voice_channel = context.user.voice.channel
    except:
        voice_channel = None
    if voice_channel is None:
        await context.response.send_message(
            polished_message(
                guild["strings"]["not_in_voice"], {"user": context.user.mention}
            )
        )
    elif 0 < index < len(guild["queue"]) + 2:
        response = get(url, stream=True)
        try:
            if name is None or duration is None:
                metadata = self.get_metadata(BytesIO(response.content), url)
                if name is None:
                    name = metadata["name"]
                if duration is None:
                    duration = metadata["duration"]
        except:
            return await context.response.send_message(
                polished_message(guild["strings"]["invalid_url"], {"url": url})
            )
        # verify that the URL file is a media container
        if not any(
            content_type in response.headers.get("Content-Type", "")
            for content_type in ["audio", "video"]
        ):
            return await context.response.send_message(
                polished_message(
                    guild["strings"]["invalid_song"],
                    {"song": polished_url(url, name)},
                )
            )
        # add the track to the queue
        guild["queue"].insert(
            index - 1,
            {
                "file": url,
                "name": name,
                "time": time,
                "duration": duration,
                "silent": silent,
            },
        )
        if index - 1 <= guild["index"]:
            guild["index"] += 1
        if not silent:
            await context.response.send_message(
                polished_message(
                    guild["strings"]["queue_insert_song"],
                    {"song": polished_url(url, name), "index": index},
                )
            )
    else:
        await context.response.send_message(
            polished_message(guild["strings"]["invalid_song_number"], {"index": index})
        )


async def move_command(self, context, song_index, new_index):
    guild = self.guilds[str(context.guild.id)]
    if 0 < song_index < len(guild["queue"]) + 1:
        if 0 < new_index < len(guild["queue"]) + 1:
            queue = guild["queue"].copy()
            guild["queue"].remove(queue[song_index - 1])
            guild["queue"].insert(new_index - 1, queue[song_index - 1])
            await context.response.send_message(
                polished_message(
                    guild["strings"]["queue_move_song"],
                    {
                        "song": polished_url(
                            queue[song_index - 1]["file"],
                            queue[song_index - 1]["name"],
                        ),
                        "index": new_index,
                    },
                )
            )
        if song_index - 1 < guild["index"] and new_index - 1 >= guild["index"]:
            guild["index"] -= 1
        elif song_index - 1 > guild["index"] and new_index - 1 <= guild["index"]:
            guild["index"] += 1
        elif song_index - 1 == guild["index"] and new_index - 1 != guild["index"]:
            guild["index"] = new_index - 1
        else:
            await context.response.send_message(
                polished_message(
                    guild["strings"]["invalid_song_number"], {"index": new_index}
                )
            )
    else:
        await context.response.send_message(
            polished_message(
                guild["strings"]["invalid_song_number"], {"index": song_index}
            )
        )


async def rename_command(self, context, song_index, new_name):
    guild = self.guilds[str(context.guild.id)]
    await context.response.send_message(
        polished_message(
            guild["strings"]["queue_rename_song"],
            {
                "song": polished_url(
                    guild["queue"][song_index - 1]["file"],
                    guild["queue"][song_index - 1]["name"],
                ),
                "index": song_index,
                "name": new_name,
            },
        )
    )
    guild["queue"][song_index - 1]["name"] = new_name


async def remove_command(self, context, song_index):
    await self.remove_song(context, song_index)


async def remove_song(self, context, index, silent):
    guild = self.guilds[str(context.guild.id)]
    if 0 < index < len(guild["queue"]) + 1:
        if not silent:
            await context.response.send_message(
                polished_message(
                    guild["strings"]["queue_remove_song"],
                    {
                        "song": polished_url(
                            guild["queue"][index - 1]["file"],
                            guild["queue"][index - 1]["name"],
                        ),
                        "index": index,
                    },
                )
            )
        # remove the track from the queue
        guild["queue"].remove(guild["queue"][index - 1])
        # decrement the index of the current track to match its new position in the queue, should the removed track have been before it
        if index - 1 < guild["index"]:
            guild["index"] -= 1
        # if the removed track is the current track, play the new track in its place in the queue
        elif index - 1 == guild["index"]:
            guild["index"] -= 1
            if self.use_lavalink:
                await context.guild.voice_client.stop()
            else:
                context.guild.voice_client.stop()
    else:
        await context.response.send_message(
            polished_message(guild["strings"]["invalid_song_number"], {"index": index})
        )


async def song_autocompletion(self, context, current):
    guild = self.guilds[str(context.guild.id)]
    songs = []
    for index, song in enumerate(guild["queue"], 1):
        polished_song_name = polished_message(
            guild["strings"]["song"], {"song": song["name"], "index": index}
        )
        song["name"] = (
            song["name"][: 97 - len(polished_song_name) + len(song["name"])] + "..."
            if len(polished_song_name) > 100
            else song["name"]
        )
        if (current == "" or current.lower() in polished_song_name.lower()) and len(
            songs
        ) < 25:
            songs.append(Choice(name=polished_song_name, value=index))
    return songs


async def skip_command(self, context, by, to):
    guild = self.guilds[str(context.guild.id)]
    if guild["queue"]:
        if to is None:
            if guild["index"] + by < len(guild["queue"]) and by > 0:
                guild["index"] += by - 1
            else:
                return await context.response.send_message(
                    guild["strings"]["invalid_command"], ephemeral=True
                )
        else:
            if 0 < to <= len(guild["queue"]):
                guild["index"] = to - 2
            else:
                return await context.response.send_message(
                    guild["strings"]["invalid_command"], ephemeral=True
                )
        await context.response.send_message(
            polished_message(
                guild["strings"]["now_playing"],
                {
                    "song": polished_url(
                        guild["queue"][guild["index"] + 1]["file"],
                        guild["queue"][guild["index"] + 1]["name"],
                    ),
                    "index": guild["index"] + 2,
                    "max": len(guild["queue"]),
                },
            )
        )
        guild["queue"][guild["index"] + 1]["silent"] = True
        guild["time"] = 0.0
        if self.use_lavalink:
            await context.guild.voice_client.stop()
        else:
            context.guild.voice_client.stop()
    else:
        await context.response.send_message(
            guild["strings"]["queue_no_songs"], ephemeral=True
        )


async def previous_command(self, context, by):
    guild = self.guilds[str(context.guild.id)]
    if guild["queue"]:
        if guild["index"] - by >= 0 and by > 0:
            guild["index"] -= by + 1
        else:
            return await context.response.send_message(
                guild["strings"]["invalid_command"], ephemeral=True
            )
        await context.response.send_message(
            polished_message(
                guild["strings"]["now_playing"],
                {
                    "song": polished_url(
                        guild["queue"][guild["index"] + 1]["file"],
                        guild["queue"][guild["index"] + 1]["name"],
                    ),
                    "index": guild["index"] + 2,
                    "max": len(guild["queue"]),
                },
            )
        )
        guild["queue"][guild["index"] + 1]["silent"] = True
        guild["time"] = 0.0
        if self.use_lavalink:
            await context.guild.voice_client.stop()
        else:
            context.guild.voice_client.stop()
    else:
        await context.response.send_message(
            guild["strings"]["queue_no_songs"], ephemeral=True
        )


async def stop_command(self, context):
    await context.response.send_message(
        self.guilds[str(context.guild.id)]["strings"]["stop"]
    )
    await self.stop_music(context)


async def stop_music(self, context, leave, guild):
    if guild is None:
        id = context.guild.id
    else:
        id = guild.id
    guild = self.guilds[str(id)]
    guild["queue"] = []
    try:
        if (
            context.guild.voice_client.is_playing
            if self.use_lavalink
            else context.guild.voice_client.is_playing()
        ):
            guild["index"] = -1
            if self.use_lavalink:
                await context.guild.voice_client.stop()
            else:
                context.guild.voice_client.stop()
        else:
            guild["index"] = 0
        if leave or not guild["keep"]:
            guild["connected"] = False
            await context.guild.voice_client.disconnect()
    except:
        guild["index"] = 0
        guild["connected"] = False
        if self.use_lavalink:
            await context.guild.voice_client.destroy()
        else:
            await context.guild.voice_client.cleanup()


async def pause_command(self, context):
    guild = self.guilds[str(context.guild.id)]
    if guild["queue"]:
        if self.use_lavalink:
            await context.guild.voice_client.set_pause(
                not context.guild.voice_client.is_paused
            )
        else:
            if context.guild.voice_client.is_paused():
                context.guild.voice_client.resume()
            else:
                context.guild.voice_client.pause()
        now_or_no_longer = (
            guild["strings"]["now"]
            if (
                context.guild.voice_client.is_paused
                if self.use_lavalink
                else context.guild.voice_client.is_paused()
            )
            else guild["strings"]["no_longer"]
        )
        await context.response.send_message(
            polished_message(
                guild["strings"]["pause"], {"now_or_no_longer": now_or_no_longer}
            )
        )
    else:
        await context.response.send_message(
            guild["strings"]["queue_no_songs"], ephemeral=True
        )


async def jump_command(self, context, time):
    await self.jump_to(context, time)


async def jump_to(self, context, time):
    seconds = convert_to_seconds(time)
    guild = self.guilds[str(context.guild.id)]
    if guild["queue"]:
        await context.response.send_message(
            polished_message(
                guild["strings"]["jump"],
                {
                    "time": convert_to_time_marker(seconds),
                    "song": polished_url(
                        guild["queue"][guild["index"]]["file"],
                        guild["queue"][guild["index"]]["name"],
                    ),
                    "index": guild["index"] + 1,
                    "max": len(guild["queue"]),
                },
            )
        )
        if self.use_lavalink:
            await context.guild.voice_client.seek(int(seconds * 1000))
        else:
            guild["time"] = seconds
            await self.insert_song(
                context,
                guild["queue"][guild["index"]]["file"],
                guild["queue"][guild["index"]]["name"],
                guild["index"] + 2,
                seconds,
                guild["queue"][guild["index"]]["duration"],
                True,
            )
            await self.remove_song(context, guild["index"] + 1, True)
    else:
        await context.response.send_message(
            guild["strings"]["queue_no_songs"], ephemeral=True
        )


async def forward_command(self, context, time):
    if self.use_lavalink:
        await self.jump_to(
            context,
            str(context.guild.voice_client.position / 1000 + convert_to_seconds(time)),
        )
    else:
        await self.jump_to(
            context,
            str(
                float(self.guilds[str(context.guild.id)]["time"])
                + convert_to_seconds(time)
            ),
        )


async def rewind_command(self, context, time):
    if self.use_lavalink:
        await self.jump_to(
            context,
            str(context.guild.voice_client.position / 1000 - convert_to_seconds(time)),
        )
    else:
        await self.jump_to(
            context,
            str(
                float(self.guilds[str(context.guild.id)]["time"])
                - convert_to_seconds(time)
            ),
        )


async def when_command(self, context):
    guild = self.guilds[str(context.guild.id)]
    if guild["queue"]:
        await context.response.send_message(
            " / ".join(
                [
                    convert_to_time_marker(
                        (context.guild.voice_client.position / 1000)
                        if self.use_lavalink
                        else guild["time"]
                    ),
                    convert_to_time_marker(guild["queue"][guild["index"]]["duration"]),
                ]
            ),
            ephemeral=True,
        )
    else:
        await context.response.send_message(
            guild["strings"]["queue_no_songs"], ephemeral=True
        )


async def shuffle_command(self, context, restart):
    guild = self.guilds[str(context.guild.id)]
    if guild["queue"]:
        for index in range(len(guild["queue"])):
            temp_index = randint(0, len(guild["queue"]) - 1)
            temp_song = guild["queue"][index]
            guild["queue"][index] = guild["queue"][temp_index]
            guild["queue"][temp_index] = temp_song
            if index == guild["index"]:
                guild["index"] = temp_index
        await context.response.send_message(guild["strings"]["shuffle"])
        if bool(restart):
            guild["index"] = -1
            if self.use_lavalink:
                await context.guild.voice_client.stop()
            else:
                context.guild.voice_client.stop()
    else:
        await context.response.send_message(
            guild["strings"]["queue_no_songs"], ephemeral=True
        )


async def queue_command(self, context):
    await context.response.defer(ephemeral=True)
    guild = self.guilds[str(context.guild.id)]
    message = guild["strings"]["queue_songs_header"] + "\n"
    if not guild["queue"]:
        return await context.followup.send(guild["strings"]["queue_no_songs"])
    pages = []
    for index in range(len(guild["queue"])):
        previous_message = message
        new_message = polished_message(
            guild["strings"]["song"] + "\n",
            {
                "song": polished_url(
                    guild["queue"][index]["file"], guild["queue"][index]["name"]
                ),
                "index": index + 1,
            },
        )
        message += new_message
        if len(message) > 2000:
            pages.append(previous_message)
            message = guild["strings"]["queue_songs_header"] + "\n" + new_message
    pages.append(message)
    await page_selector(context, guild["strings"], pages, 0)


async def what_command(self, context):
    guild = self.guilds[str(context.guild.id)]
    if guild["queue"]:
        await context.response.send_message(
            polished_message(
                guild["strings"]["now_playing"],
                {
                    "song": polished_url(
                        guild["queue"][guild["index"]]["file"],
                        guild["queue"][guild["index"]]["name"],
                    ),
                    "index": guild["index"] + 1,
                    "max": len(guild["queue"]),
                },
            ),
            ephemeral=True,
        )
    else:
        await context.response.send_message(
            guild["strings"]["queue_no_songs"], ephemeral=True
        )


async def volume_command(self, context, set):
    guild = self.guilds[str(context.guild.id)]
    if set is not None:
        if set.endswith("%"):
            guild["volume"] = float(set.replace("%", "")) / 100
        else:
            guild["volume"] = float(set)
        if context.guild.voice_client is not None and (
            context.guild.voice_client.is_playing
            if self.use_lavalink
            else context.guild.voice_client.is_playing()
        ):
            if self.use_lavalink:
                await context.guild.voice_client.set_volume(int(guild["volume"] * 100))
            else:
                context.guild.voice_client.source.volume = guild["volume"]
    volume = guild["volume"] * 100
    if volume == float(int(volume)):
        volume = int(volume)
    if set is None:
        await context.response.send_message(
            polished_message(guild["strings"]["volume"], {"volume": str(volume) + "%"}),
            ephemeral=True,
        )
    else:
        await context.response.send_message(
            polished_message(
                guild["strings"]["volume_change"], {"volume": str(volume) + "%"}
            )
        )


async def recruit_command(self, context):
    guild = self.guilds[str(context.guild.id)]
    try:
        voice_channel = context.user.voice.channel
    except:
        return await context.response.send_message(
            polished_message(
                guild["strings"]["not_in_voice"], {"user": context.user.mention}
            )
        )
    if guild["connected"]:
        await context.response.send_message("...", ephemeral=True)
        await context.delete_original_response()
    else:
        await context.response.send_message(
            polished_message(
                guild["strings"]["recruit_or_dismiss"],
                {
                    "bot": self.bot.user.mention,
                    "voice": voice_channel.jump_url,
                    "now_or_no_longer": guild["strings"]["now"],
                },
            )
        )
        if self.use_lavalink:
            await voice_channel.connect(cls=pomice.Player)
        else:
            await voice_channel.connect()
        guild["connected"] = True
        await context.guild.change_voice_state(
            channel=voice_channel, self_mute=False, self_deaf=True
        )


async def dismiss_command(self, context):
    guild = self.guilds[str(context.guild.id)]
    try:
        voice_channel = context.user.voice.channel
    except:
        return await context.response.send_message(
            polished_message(
                guild["strings"]["not_in_voice"], {"user": context.user.mention}
            )
        )
    if guild["connected"]:
        await context.response.send_message(
            polished_message(
                guild["strings"]["recruit_or_dismiss"],
                {
                    "bot": self.bot.user.mention,
                    "voice": voice_channel.jump_url,
                    "now_or_no_longer": guild["strings"]["no_longer"],
                },
            )
        )
        await self.stop_music(context, True)
    else:
        await context.response.send_message("...", ephemeral=True)
        await context.delete_original_response()


async def disconnect_when_alone(self, member, before, after):
    try:
        # ensure that this bot disconnects from any empty voice channel it is in
        if (
            member.guild.voice_client.is_connected
            if self.use_lavalink
            else member.guild.voice_client.is_connected()
        ):
            for voice_channel in member.guild.voice_channels:
                if (
                    voice_channel.voice_states
                    and list(voice_channel.voice_states)[0] == self.bot.user.id
                    and len(list(voice_channel.voice_states)) == 1
                ):
                    await self.stop_music(member, True, member.guild)
                    break
        # ensure that this bot's connected status and the queue are reset if it is not properly disconnected
        elif member.id == self.bot.user.id:
            guild = self.guilds[str(member.guild.id)]
            if guild["connected"]:
                guild["index"] = 0
                guild["queue"] = []
                guild["connected"] = False
                if self.use_lavalink:
                    member.guild.voice_client.destroy()
                else:
                    member.guild.voice_client.cleanup()
    except:
        pass


async def keep_command(self, context, set):
    if VARIABLES["storage"] == "yaml":
        await self.lock.acquire()
    strings = self.guilds[str(context.guild.id)]["strings"]
    try:
        voice_channel = context.user.voice.channel.jump_url
    except:
        voice_channel = strings["whatever_voice"]
    if set is None:
        await context.response.send_message(
            polished_message(
                strings["keep"],
                {
                    "bot": self.bot.user.mention,
                    "voice": voice_channel,
                    "stay_in_or_leave": (
                        strings["stay_in"]
                        if self.guilds[str(context.guild.id)]["keep"]
                        else strings["leave"]
                    ),
                },
            ),
            ephemeral=True,
        )
        if VARIABLES["storage"] == "yaml":
            return self.lock.release()
        return
    else:
        keep = bool(set)
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == context.guild.id:
                    guild["keep"] = keep
                    # modify the flat file for guilds to reflect the change of whether to keep this bot in a voice call when no audio is playing
                    dump(self.data, open(self.flat_file, "w"), indent=4)

                    self.guilds[str(context.guild.id)]["keep"] = keep
                    break
        else:
            await self.cursor.execute(
                "update guilds_music set keep_in_voice = ? where guild_id = ?",
                (keep, context.guild.id),
            )
            await self.connection.commit()
            self.guilds[str(context.guild.id)]["keep"] = keep
    await context.response.send_message(
        polished_message(
            strings["keep_change"],
            {
                "bot": self.bot.user.mention,
                "voice": voice_channel,
                "now_or_no_longer": (strings["now"] if keep else strings["no_longer"]),
            },
        )
    )
    if VARIABLES["storage"] == "yaml":
        self.lock.release()


async def loop_command(self, context, set):
    if VARIABLES["storage"] == "yaml":
        await self.lock.acquire()
    strings = self.guilds[str(context.guild.id)]["strings"]
    if set is None:
        await context.response.send_message(
            polished_message(
                strings["repeat"],
                {
                    "do_not": (
                        ""
                        if self.guilds[str(context.guild.id)]["repeat"]
                        else strings["do_not"]
                    )
                },
            ),
            ephemeral=True,
        )
        if VARIABLES["storage"] == "yaml":
            return self.lock.release()
        return
    else:
        repeat = bool(set)
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == context.guild.id:
                    guild["repeat"] = repeat
                    # modify the flat file for guilds to reflect the change of whether playlists repeat
                    dump(self.data, open(self.flat_file, "w"), indent=4)

                    self.guilds[str(context.guild.id)]["repeat"] = repeat
                    break
        else:
            await self.cursor.execute(
                "update guilds_music set repeat_queue = ? where guild_id = ?",
                (repeat, context.guild.id),
            )
            await self.connection.commit()
            self.guilds[str(context.guild.id)]["repeat"] = repeat
    await context.response.send_message(
        polished_message(
            strings["repeat_change"],
            {"now_or_no_longer": (strings["now"] if repeat else strings["no_longer"])},
        )
    )
    if VARIABLES["storage"] == "yaml":
        self.lock.release()
