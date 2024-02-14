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
    def __init__(self, bot, connection, cursor, data, flat_file, language_directory, lock):
        self.bot = bot
        self.connection = connection
        self.cursor = cursor
        self.data = data
        self.flat_file = flat_file
        self.language_directory = language_directory
        self.lock = lock
        self.music_directory = "Media"
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

    def polished_message(self, message, replacements):
        for placeholder, replacement in replacements.items(): message = message.replace("%{" + placeholder + "}", str(replacement))
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

    async def init_guilds(self, set_languages=True):
        await self.lock.acquire()
        if self.cursor is None:
            guilds = self.data["guilds"]
            id = "id"
            language = "language"
            repeat = "repeat"
            keep = "keep"
        else:
            guilds = self.cursor.execute("select guild_id, guild_lang, repeat_queue, keep_in_voice from guilds").fetchall()
            id = 0
            language = 1
            repeat = 2
            keep = 3
        # add all guilds with this bot to memory that were not already
        if len(self.guilds) < len(guilds):
            ids = []
            for guild in guilds:
                for guild_searched in self.guilds: ids.append(guild_searched["id"])
                if guild[id] not in ids: self.guilds.append({"id": guild[id],
                                                             "strings": yaml.safe_load(open(f"{self.language_directory}/{guild[language]}.yaml", "r"))["strings"],
                                                             "repeat": guild[repeat],
                                                             "keep": guild[keep],
                                                             "queue": [],
                                                             "index": 0,
                                                             "time": .0,
                                                             "volume": 1.0,
                                                             "connected": False})
        # remove any guilds from memory that had removed this bot
        elif len(self.guilds) > len(guilds):
            index = 0
            while index < len(self.guilds):
                try:
                    if self.guilds[index]["id"] != guilds[index][id]:
                        self.guilds.remove(self.guilds[index])
                        index -= 1
                except: self.guilds.remove(self.guilds[index])
                index += 1

        if set_languages:
            for guild in guilds:
                self.guilds[guilds.index(guild)]["strings"] = yaml.safe_load(open(f"{self.language_directory}/{guild[language]}.yaml", "r"))["strings"]
        self.lock.release()

    # return a list of playlists for the calling guild
    @app_commands.command(description="playlists_command_desc")
    async def playlists_command(self, context: discord.Interaction):
        await context.response.defer()
        await self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if self.cursor is None: playlists = []
                else: playlists = self.cursor.execute("select pl_name from playlists where guild_id = ? order by guild_pl_id", (guild["id"],)).fetchall()
                message = ""
                if playlists or (self.cursor is None and self.data["guilds"][self.guilds.index(guild)]["playlists"]):
                    message += guild["strings"]["playlists_header"] + "\n"
                else:
                    await context.followup.send(guild["strings"]["no_playlists"])
                    return
                index = 0
                while index < len(self.data["guilds"][self.guilds.index(guild)]["playlists"] if self.cursor is None else playlists):
                    previous_message = message
                    new_message = self.polished_message(guild["strings"]["playlist"] + "\n",
                                                        {"playlist": self.data["guilds"][self.guilds.index(guild)]["playlists"][index]["name"]
                                                                     if self.cursor is None else playlists[index][0],
                                                         "playlist_index": index + 1})
                    message += new_message
                    if len(message) > 2000:
                        await context.followup.send(previous_message)
                        message = new_message
                    index += 1
                await context.followup.send(message)
                break

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
        await context.response.defer()
        await self.init_guilds()
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
                await context.followup.send(self.polished_message(strings["invalid_url"], {"url": url}))
                return
            response = requests.get(url, stream=True)
            # verify that the URL file is a media container
            if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                await context.followup.send(self.polished_message(strings["invalid_song"], {"song": self.polished_song_name(url, song["name"])}))
                return
        await self.lock.acquire()
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == context.guild.id:
                    # import a playlist
                    if from_guild is not None:
                        for guild_searched in self.data["guilds"]:
                            if guild_searched["id"] == int(from_guild):
                                from_guild_playlists = guild_searched["playlists"]
                                break
                        if transfer is None or transfer < 1 or transfer > len(from_guild_playlists):
                            await context.followup.send(strings["invalid_command"])
                            self.lock.release()
                            return
                        if new_name is None: new_name = from_guild_playlists[transfer - 1]["name"]
                        if new_index is None: new_index = len(guild["playlists"]) + 1
                        elif new_index < 1 or new_index > len(guild["playlists"]) + 1:
                            await context.followup.send(strings["invalid_command"])
                            self.lock.release()
                            return
                        guild["playlists"].insert(new_index - 1, {"name": new_name, "songs": from_guild_playlists[transfer - 1]["songs"].copy()})
                        await context.followup.send(self.polished_message(strings["clone_playlist"],
                                                                          {"playlist": from_guild_playlists[transfer - 1]["name"],
                                                                           "playlist_index": transfer,
                                                                           "into_playlist": new_name,
                                                                           "into_playlist_index": new_index}))
                    # add a playlist
                    elif add is not None:
                        if new_index is None: new_index = len(guild["playlists"]) + 1
                        elif new_index < 1 or new_index > len(guild["playlists"]) + 1:
                            await context.followup.send(strings["invalid_command"])
                            self.lock.release()
                            return
                        guild["playlists"].insert(new_index - 1, {"name": add, "songs": []})
                        await context.followup.send(self.polished_message(strings["add_playlist"], {"playlist": add, "playlist_index": new_index}))
                    # clone a playlist or copy its tracks into another playlist
                    elif clone is not None and clone > 0 and clone <= len(guild["playlists"]):
                        # clone a playlist
                        if into is None or into < 1 or into > len(guild["playlists"]):
                            if new_name is None: new_name = guild["playlists"][clone - 1]["name"]
                            if new_index is None: new_index = len(guild["playlists"]) + 1
                            elif new_index < 1 or new_index > len(guild["playlists"]) + 1:
                                await context.followup.send(strings["invalid_command"])
                                self.lock.release()
                                return
                            guild["playlists"].insert(new_index - 1, {"name": new_name, "songs": guild["playlists"][clone - 1]["songs"].copy()})
                            await context.followup.send(self.polished_message(strings["clone_playlist"],
                                                                              {"playlist": guild["playlists"][clone - 1]["name"],
                                                                               "playlist_index": clone,
                                                                               "into_playlist": new_name,
                                                                               "into_playlist_index": new_index}))
                        # copy a playlist's tracks into another playlist
                        else:
                            guild["playlists"][into - 1]["songs"] += guild["playlists"][clone - 1]["songs"]
                            await context.followup.send(self.polished_message(strings["clone_playlist"],
                                                                              {"playlist": guild["playlists"][clone - 1]["name"],
                                                                               "playlist_index": clone,
                                                                               "into_playlist": guild["playlists"][into - 1]["name"],
                                                                               "into_playlist_index": into}))
                    # change a playlist's position in the order of playlists
                    elif move is not None and move > 0 and move <= len(guild["playlists"]):
                        if new_index is None or new_index < 1 or new_index > len(guild["playlists"]):
                            await context.followup.send(strings["invalid_command"])
                            self.lock.release()
                            return
                        playlists = guild["playlists"].copy()
                        guild["playlists"].remove(playlists[move - 1])
                        guild["playlists"].insert(new_index - 1, playlists[move - 1])
                        await context.followup.send(self.polished_message(strings["move_playlist"],
                                                                          {"playlist": playlists[move - 1]["name"], "playlist_index": new_index}))
                    # rename a playlist
                    elif rename is not None and rename > 0 and rename <= len(guild["playlists"]):
                        if new_name is None:
                            await context.followup.send(strings["invalid_command"])
                            self.lock.release()
                            return
                        await context.followup.send(self.polished_message(strings["rename_playlist"],
                                                                          {"playlist": guild["playlists"][rename - 1]["name"],
                                                                           "playlist_index": rename,
                                                                           "name": new_name}))
                        guild["playlists"][rename - 1]["name"] = new_name
                    # remove a playlist
                    elif remove is not None and remove > 0 and remove <= len(guild["playlists"]):
                        await context.followup.send(self.polished_message(strings["remove_playlist"],
                                                                          {"playlist": guild["playlists"][remove - 1]["name"], "playlist_index": remove}))
                        guild["playlists"].remove(guild["playlists"][remove - 1])
                    # load a playlist
                    elif load is not None and load > 0 and load <= len(guild["playlists"]):
                        self.lock.release()
                        if guild["playlists"][load - 1]["songs"]:
                            await context.followup.send(self.polished_message(strings["load_playlist"],
                                                                              {"playlist": guild["playlists"][load - 1]["name"], "playlist_index": load}))
                            await self.play_song(context, playlist=guild["playlists"][load - 1]["songs"])
                        else: await context.followup.send(self.polished_message(strings["playlist_no_songs"],
                                                                                {"playlist": guild["playlists"][load - 1]["name"], "playlist_index": load}))
                        return
                    # select a playlist to modify or show the contents of
                    elif select is not None and action is not None:
                        if select > 0 and select <= len(guild["playlists"]):
                            # add a track to the playlist
                            if action == "add":
                                if new_name is None: new_name = metadata["name"]
                                if new_index is None: new_index = len(guild["playlists"][select - 1]["songs"]) + 1
                                elif new_index < 1 or new_index > len(guild["playlists"][select - 1]["songs"]):
                                    await context.followup.send(strings["invalid_command"])
                                    self.lock.release()
                                    return
                                song = {"name": new_name, "index": new_index, "duration": metadata["duration"]}
                                guild["playlists"][select - 1]["songs"].insert(song["index"] - 1, {"file": url, "name": song["name"], "duration": song["duration"]})
                                await context.followup.send(self.polished_message(strings["playlist_add_song"],
                                                                                  {"playlist": guild["playlists"][select - 1]["name"],
                                                                                   "playlist_index": select,
                                                                                   "song": self.polished_song_name(url, song["name"]),
                                                                                   "index": song["index"]}))
                                if file is not None: await self.renew_attachment(guild["id"], select - 1, song["index"] - 1)
                            # change the position of a track within the playlist
                            elif action == "move":
                                if (song_index is None or
                                    song_index < 1 or
                                    song_index > len(guild["playlists"][select - 1]["songs"]) or
                                    new_index is None or
                                    new_index < 1 or
                                    new_index > len(guild["playlists"][select - 1]["songs"])):
                                    await context.followup.send(strings["invalid_command"])
                                    self.lock.release()
                                    return
                                song = guild["playlists"][select - 1]["songs"][song_index - 1]
                                guild["playlists"][select - 1]["songs"].remove(song)
                                guild["playlists"][select - 1]["songs"].insert(new_index - 1, song)
                                await context.followup.send(self.polished_message(strings["playlist_move_song"],
                                                                                  {"playlist": guild["playlists"][select - 1]["name"],
                                                                                   "playlist_index": select,
                                                                                   "song": self.polished_song_name(song["file"], song["name"]),
                                                                                   "index": new_index}))
                            # rename a track in the playlist
                            elif action == "rename":
                                if song_index is None or song_index < 1 or song_index > len(guild["playlists"][select - 1]["songs"]) or new_name is None:
                                    await context.followup.send(strings["invalid_command"])
                                    self.lock.release()
                                    return
                                song = guild["playlists"][select - 1]["songs"][song_index - 1]
                                await context.followup.send(self.polished_message(strings["playlist_rename_song"],
                                                                                  {"playlist": guild["playlists"][select - 1]["name"],
                                                                                   "playlist_index": select,
                                                                                   "song": self.polished_song_name(song["file"], song["name"]),
                                                                                   "index": song_index,
                                                                                   "name": new_name}))
                                song["name"] = new_name
                            # remove a track from the playlist
                            elif action == "remove":
                                if song_index is None or song_index < 1 or song_index > len(guild["playlists"][select - 1]["songs"]):
                                    await context.followup.send(strings["invalid_command"])
                                    self.lock.release()
                                    return
                                song = guild["playlists"][select - 1]["songs"][song_index - 1]
                                guild["playlists"][select - 1]["songs"].remove(song)
                                await context.followup.send(self.polished_message(strings["playlist_remove_song"],
                                                                                  {"playlist": guild["playlists"][select - 1]["name"],
                                                                                   "playlist_index": select,
                                                                                   "song": self.polished_song_name(song["file"], song["name"]),
                                                                                   "index": song_index}))
                            # return a list of tracks in the playlist
                            elif action == "list":
                                message = ""
                                if guild["playlists"][select - 1]["songs"]: message += self.polished_message(strings["playlist_songs_header"] + "\n",
                                                                                                             {"playlist": guild["playlists"][select - 1]["name"],
                                                                                                              "playlist_index": select})
                                else:
                                    await context.followup.send(self.polished_message(strings["playlist_no_songs"],
                                                                                      {"playlist": guild["playlists"][select - 1]["name"], "playlist_index": select}))
                                    self.lock.release()
                                    return
                                index = 0
                                while index < len(guild["playlists"][select - 1]["songs"]):
                                    previous_message = message
                                    new_message = self.polished_message(strings["song"] + "\n",
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
                            await context.followup.send(self.polished_message(strings["invalid_playlist_number"], {"playlist_index": select}))
                            self.lock.release()
                            return
                    else:
                        await context.followup.send(strings["invalid_command"])
                        self.lock.release()
                        return
                    # modify the flat file for guilds to reflect changes regarding playlists
                    yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)

                    break
        else:
            playlist_count = self.cursor.execute("select count(pl_id) from playlists where guild_id = ?", (context.guild.id,)).fetchone()[0]
            # import a playlist
            if from_guild is not None:
                from_guild_playlist_count = self.cursor.execute("select count(pl_id) from playlists where guild_id = ?", (int(from_guild),)).fetchone()[0]
                if transfer is None or transfer < 1 or transfer > from_guild_playlist_count:
                    await context.followup.send(strings["invalid_command"])
                    self.lock.release()
                    return
                songs = (self.cursor.execute("""select song_name, song_url, song_duration from songs
                                                left outer join playlists on playlists.pl_id = songs.pl_id
                                                where playlists.guild_id = ? and playlists.guild_pl_id = ?
                                                order by songs.pl_song_id""",
                                             (int(from_guild), transfer - 1))
                                    .fetchall())
                if new_name is None: new_name = (self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                                                                     (int(from_guild), transfer - 1))
                                                            .fetchone()[0])
                if new_index is not None and (new_index < 1 or new_index > playlist_count + 1):
                    await context.followup.send(strings["invalid_command"])
                    self.lock.release()
                    return
                self.cursor.execute("""insert into playlists values((select count(pl_id) from playlists),
                                                                    ?,
                                                                    ?,
                                                                    (select count(pl_id) from playlists where guild_id = ?))""",
                                    (new_name, context.guild.id, context.guild.id))
                for song in songs:
                    self.cursor.execute("""insert into songs values((select count(song_id) from songs),
                                                                    ?,
                                                                    ?,
                                                                    ?,
                                                                    (select count(pl_id) from playlists) - 1,
                                                                    (select count(song_id) from songs where pl_id = (select count(pl_id) from playlists) - 1))""",
                                        (song[0], song[1], song[2]))
                if new_index is None: new_index = playlist_count + 1
                else:
                    self.cursor.execute("update playlists set guild_pl_id = guild_pl_id + 1 where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?",
                                        (new_index - 1, playlist_count, context.guild.id))
                    self.cursor.execute("update playlists set guild_pl_id = ? where pl_id = (select count(pl_id) from playlists) - 1", (new_index - 1,))
                await context.followup.send(self.polished_message(strings["clone_playlist"],
                                                                  {"playlist": self.cursor.execute("""select pl_name from playlists
                                                                                                      where guild_id = ? and guild_pl_id = ?""",
                                                                                                   (int(from_guild), transfer - 1))
                                                                                          .fetchone()[0],
                                                                   "playlist_index": transfer,
                                                                   "into_playlist": new_name,
                                                                   "into_playlist_index": new_index}))
            # add a playlist
            elif add is not None:
                if new_index is not None and (new_index < 1 or new_index > playlist_count + 1):
                    await context.followup.send(strings["invalid_command"])
                    self.lock.release()
                    return
                self.cursor.execute("""insert into playlists values((select count(pl_id) from playlists),
                                                                    ?,
                                                                    ?,
                                                                    (select count(pl_id) from playlists where guild_id = ?))""",
                                    (add, context.guild.id, context.guild.id))
                if new_index is None: new_index = playlist_count + 1
                else:
                    self.cursor.execute("update playlists set guild_pl_id = guild_pl_id + 1 where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?",
                                        (new_index - 1, playlist_count, context.guild.id))
                    self.cursor.execute("update playlists set guild_pl_id = ? where pl_id = (select count(pl_id) from playlists) - 1", (new_index - 1,))
                await context.followup.send(self.polished_message(strings["add_playlist"], {"playlist": add, "playlist_index": new_index}))
            # clone a playlist or copy its tracks into another playlist
            elif clone is not None and clone > 0 and clone <= playlist_count:
                # clone a playlist
                songs = (self.cursor.execute("""select song_name, song_url, song_duration from songs
                                                left outer join playlists on playlists.pl_id = songs.pl_id
                                                where playlists.guild_id = ? and playlists.guild_pl_id = ?
                                                order by songs.pl_song_id""",
                                             (context.guild.id, clone - 1))
                                    .fetchall())
                if into is None or into < 1 or into > playlist_count:
                    if new_name is None: new_name = (self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                                                                         (context.guild.id, clone - 1))
                                                                .fetchone()[0])
                    if new_index is not None and (new_index < 1 or new_index > playlist_count + 1):
                        await context.followup.send(strings["invalid_command"])
                        self.lock.release()
                        return
                    self.cursor.execute("""insert into playlists values((select count(pl_id) from playlists),
                                                                        ?,
                                                                        ?,
                                                                        (select count(pl_id) from playlists where guild_id = ?))""",
                                        (new_name, context.guild.id, context.guild.id))
                    for song in songs:
                        self.cursor.execute("""insert into songs values((select count(song_id) from songs),
                                                                        ?,
                                                                        ?,
                                                                        ?,
                                                                        (select count(pl_id) from playlists) - 1,
                                                                        (select count(song_id) from songs where pl_id = (select count(pl_id) from playlists) - 1))""",
                                            (song[0], song[1], song[2]))
                    if new_index is None: new_index = playlist_count + 1
                    else:
                        self.cursor.execute("update playlists set guild_pl_id = guild_pl_id + 1 where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?",
                                            (new_index - 1, playlist_count, context.guild.id))
                        self.cursor.execute("update playlists set guild_pl_id = ? where pl_id = (select count(pl_id) from playlists) - 1", (new_index - 1,))
                    await context.followup.send(self.polished_message(strings["clone_playlist"],
                                                                      {"playlist": self.cursor.execute("""select pl_name from playlists
                                                                                                          where guild_id = ? and guild_pl_id = ?""",
                                                                                                       (context.guild.id, clone - 1))
                                                                                              .fetchone()[0],
                                                                       "playlist_index": clone,
                                                                       "into_playlist": new_name,
                                                                       "into_playlist_index": new_index}))
                # copy a playlist's tracks into another playlist
                else:
                    for song in songs: self.cursor.execute("""insert into songs values((select count(song_id) from songs),
                                                                                       ?,
                                                                                       ?,
                                                                                       ?,
                                                                                       (select pl_id from playlists where guild_id = ? and guild_pl_id = ?),
                                                                                       (select count(song_id) from songs
                                                                                        left outer join playlists on playlists.pl_id = songs.pl_id
                                                                                        where playlists.guild_id = ? and playlists.guild_pl_id = ?))""",
                                                           (song[0], song[1], song[2], context.guild.id, into - 1, context.guild.id, into - 1))
                    await context.followup.send(self.polished_message(strings["clone_playlist"],
                                                                      {"playlist": self.cursor.execute("""select pl_name from playlists
                                                                                                          where guild_id = ? and guild_pl_id = ?""",
                                                                                                       (context.guild.id, clone - 1))
                                                                                              .fetchone()[0],
                                                                       "playlist_index": clone,
                                                                       "into_playlist": self.cursor.execute("""select pl_name from playlists
                                                                                                               where guild_id = ? and guild_pl_id = ?""",
                                                                                                            (context.guild.id, into - 1))
                                                                                                   .fetchone()[0],
                                                                       "into_playlist_index": into}))
            # change a playlist's position in the order of playlists
            elif move is not None and move > 0 and move <= playlist_count:
                playlist_copies = self.cursor.execute("select pl_id, pl_name from playlists where guild_id = ? order by guild_pl_id", (context.guild.id,)).fetchall()
                if new_index is None or new_index < 1 or new_index > playlist_count:
                    await context.followup.send(strings["invalid_command"])
                    self.lock.release()
                    return
                elif new_index > move: self.cursor.execute("""update playlists set guild_pl_id = guild_pl_id - 1
                                                              where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?""",
                                                           (move - 1, new_index - 1, context.guild.id))
                elif new_index < move: self.cursor.execute("""update playlists set guild_pl_id = guild_pl_id + 1
                                                              where guild_pl_id >= ? and guild_pl_id <= ? and guild_id = ?""",
                                                           (new_index - 1, move - 1, context.guild.id))
                self.cursor.execute("update playlists set guild_pl_id = ? where pl_id = ?", (new_index - 1, playlist_copies[move - 1][0]))
                await context.followup.send(self.polished_message(strings["move_playlist"], {"playlist": playlist_copies[move - 1][1], "playlist_index": new_index}))
            # rename a playlist
            elif rename is not None and rename > 0 and rename <= playlist_count:
                if new_name is None:
                    await context.followup.send(strings["invalid_command"])
                    self.lock.release()
                    return
                await context.followup.send(self.polished_message(strings["rename_playlist"],
                                                                  {"playlist": self.cursor.execute("""select pl_name from playlists
                                                                                                      where guild_id = ? and guild_pl_id = ?""",
                                                                                                   (context.guild.id, rename - 1))
                                                                                          .fetchone()[0],
                                                                   "playlist_index": rename,
                                                                   "name": new_name}))
                self.cursor.execute("update playlists set pl_name = ? where guild_id = ? and guild_pl_id = ?", (new_name, context.guild.id, rename - 1))
            # remove a playlist
            elif remove is not None and remove > 0 and remove <= playlist_count:
                await context.followup.send(self.polished_message(strings["remove_playlist"],
                                                                  {"playlist": self.cursor.execute("""select pl_name from playlists
                                                                                                      where guild_id = ? and guild_pl_id = ?""",
                                                                                                   (context.guild.id, remove - 1))
                                                                                          .fetchone()[0],
                                                                   "playlist_index": remove}))
                self.cursor.execute("delete from songs where pl_id = (select pl_id from playlists where guild_id = ? and guild_pl_id = ?)",
                                    (context.guild.id, remove - 1))
                self.cursor.execute("delete from playlists where guild_id = ? and guild_pl_id = ?", (context.guild.id, remove - 1))
                self.cursor.execute("update playlists set guild_pl_id = guild_pl_id - 1 where guild_pl_id >= ? and guild_id = ?", (remove - 1, context.guild.id))
            # load a playlist
            elif load is not None and load > 0 and load <= playlist_count:
                self.lock.release()
                songs = (self.cursor.execute("""select song_name, song_url, song_duration from songs
                                                left outer join playlists on playlists.pl_id = songs.pl_id
                                                where playlists.guild_id = ? and playlists.guild_pl_id = ?
                                                order by songs.pl_song_id""",
                                             (context.guild.id, load - 1))
                                    .fetchall())
                if songs:
                    proper_songs = []
                    for song in songs: proper_songs.append({"name": song[0], "file": song[1], "duration": song[2]})
                    await context.followup.send(self.polished_message(strings["load_playlist"],
                                                                      {"playlist": self.cursor.execute("""select pl_name from playlists
                                                                                                          where guild_id = ? and guild_pl_id = ?""",
                                                                                                       (context.guild.id, load - 1))
                                                                                              .fetchone()[0],
                                                                       "playlist_index": load}))
                    await self.play_song(context, playlist=proper_songs)
                else: await context.followup.send(self.polished_message(strings["playlist_no_songs"],
                                                                        {"playlist": self.cursor.execute("""select pl_name from playlists
                                                                                                            where guild_id = ? and guild_pl_id = ?""",
                                                                                                         (context.guild.id, load - 1))
                                                                                                .fetchone()[0],
                                                                         "playlist_index": load}))
                return
            # select a playlist to modify or show the contents of
            elif select is not None and action is not None:
                if select > 0 and select <= playlist_count:
                    global_playlist_id, playlist, song_count = (self.cursor.execute("""select songs.pl_id, playlists.pl_name, count(song_id) from songs
                                                                                       left outer join playlists on playlists.pl_id = songs.pl_id
                                                                                       where playlists.guild_id = ? and playlists.guild_pl_id = ?""",
                                                                                    (context.guild.id, select - 1))
                                                                           .fetchone())
                    # add a track to the playlist
                    if action == "add":
                        if new_name is None: new_name = metadata["name"]
                        if new_index is not None and (new_index < 1 or new_index > song_count + 1):
                            await context.followup.send(strings["invalid_command"])
                            self.lock.release()
                            return
                        self.cursor.execute("""insert into songs values((select count(song_id) from songs),
                                                                        ?,
                                                                        ?,
                                                                        ?,
                                                                        (select pl_id from playlists where guild_id = ? and guild_pl_id = ?),
                                                                        (select count(song_id) from songs
                                                                         left outer join playlists on playlists.pl_id = songs.pl_id
                                                                         where playlists.guild_id = ? and playlists.guild_pl_id = ?))""",
                                            (new_name, url, metadata["duration"], context.guild.id, select - 1, context.guild.id, select - 1))
                        if new_index is None: new_index = song_count + 1
                        else:
                            self.cursor.execute("update songs set pl_song_id = pl_song_id + 1 where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?",
                                                (new_index - 1, song_count, global_playlist_id))
                            self.cursor.execute("update songs set pl_song_id = ? where song_id = (select count(song_id) from songs) - 1", (new_index - 1,))
                        await context.followup.send(self.polished_message(strings["playlist_add_song"],
                                                                          {"playlist": playlist,
                                                                           "playlist_index": select,
                                                                           "song": self.polished_song_name(url, new_name),
                                                                           "index": new_index}))
                        if file is not None:
                            self.lock.release()
                            await self.renew_attachment(context.guild.id,
                                                        select - 1,
                                                        new_index - 1,
                                                        self.cursor.execute("select count(song_id) from songs").fetchone()[0] - 1)
                            return
                    # change the position of a track within the playlist
                    elif action == "move":
                        song_copies = (self.cursor.execute("""select song_id, song_url, song_name from songs
                                                              left outer join playlists on playlists.pl_id = songs.pl_id
                                                              where playlists.guild_id = ? and playlists.guild_pl_id = ?
                                                              order by songs.pl_song_id""",
                                                           (context.guild.id, select - 1))
                                                  .fetchall())
                        if song_index is None or song_index < 1 or song_index > song_count or new_index is None or new_index < 1 or new_index > song_count:
                            await context.followup.send(strings["invalid_command"])
                            self.lock.release()
                            return
                        elif new_index > song_index: self.cursor.execute("""update songs set pl_song_id = pl_song_id - 1
                                                                            where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?""",
                                                                         (song_index - 1, new_index - 1, global_playlist_id))
                        elif new_index < song_index: self.cursor.execute("""update songs set pl_song_id = pl_song_id + 1
                                                                            where pl_song_id >= ? and pl_song_id <= ? and pl_id = ?""",
                                                                         (new_index - 1, song_index - 1, global_playlist_id))
                        self.cursor.execute("update songs set pl_song_id = ? where song_id = ?", (new_index - 1, song_copies[song_index - 1][0]))
                        await context.followup.send(self.polished_message(strings["playlist_move_song"],
                                                                          {"playlist": playlist,
                                                                           "playlist_index": select,
                                                                           "song": self.polished_song_name(song_copies[song_index - 1][1],
                                                                                                           song_copies[song_index - 1][2]),
                                                                           "index": new_index}))
                    # rename a track in the playlist
                    elif action == "rename":
                        if song_index is None or song_index < 1 or song_index > song_count or new_name is None:
                            await context.followup.send(strings["invalid_command"])
                            self.lock.release()
                            return
                        song_id, song_name, song_file = (self.cursor.execute("""select song_id, song_name, song_url from songs
                                                                                left outer join playlists on playlists.pl_id = songs.pl_id
                                                                                where playlists.guild_id = ? and playlists.guild_pl_id = ? and songs.pl_song_id = ?""",
                                                                             (context.guild.id, select - 1, song_index - 1))
                                                                    .fetchone())
                        await context.followup.send(self.polished_message(strings["playlist_rename_song"],
                                                                          {"playlist": playlist,
                                                                           "playlist_index": select,
                                                                           "song": self.polished_song_name(song_file, song_name),
                                                                           "index": song_index,
                                                                           "name": new_name}))
                        self.cursor.execute("update songs set song_name = ? where song_id = ?", (new_name, song_id))
                    # remove a track from the playlist
                    elif action == "remove":
                        if song_index is None or song_index < 1 or song_index > song_count:
                            await context.followup.send(strings["invalid_command"])
                            self.lock.release()
                            return
                        song_id, song_name, song_file = (self.cursor.execute("""select song_id, song_name, song_url from songs
                                                                                left outer join playlists on playlists.pl_id = songs.pl_id
                                                                                where playlists.guild_id = ? and playlists.guild_pl_id = ? and songs.pl_song_id = ?""",
                                                                             (context.guild.id, select - 1, song_index - 1))
                                                                    .fetchone())
                        self.cursor.execute("delete from songs where song_id = ?", (song_id,))
                        self.cursor.execute("update songs set pl_song_id = pl_song_id - 1 where pl_song_id >= ? and pl_id = ?", (song_index - 1, global_playlist_id))
                        await context.followup.send(self.polished_message(strings["playlist_remove_song"],
                                                                          {"playlist": playlist,
                                                                           "playlist_index": select,
                                                                           "song": self.polished_song_name(song_file, song_name),
                                                                           "index": song_index}))
                    # return a list of tracks in the playlist
                    elif action == "list":
                        message = ""
                        songs = (self.cursor.execute("""select song_url, song_name from songs
                                                        left outer join playlists on playlists.pl_id = songs.pl_id
                                                        where playlists.guild_id = ? and playlists.guild_pl_id = ?
                                                        order by songs.pl_song_id""",
                                                     (context.guild.id, select - 1))
                                            .fetchall())
                        if songs: message += self.polished_message(strings["playlist_songs_header"] + "\n", {"playlist": playlist, "playlist_index": select})
                        else:
                            await context.followup.send(self.polished_message(strings["playlist_no_songs"], {"playlist": playlist, "playlist_index": select}))
                            self.lock.release()
                            return
                        index = 0
                        while index < len(songs):
                            previous_message = message
                            new_message = self.polished_message(strings["song"] + "\n",
                                                                {"song": self.polished_song_name(songs[index][0], songs[index][1]), "index": index + 1})
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
                    await context.followup.send(self.polished_message(strings["invalid_playlist_number"], {"playlist_index": select}))
                    self.lock.release()
                    return
            else:
                await context.followup.send(strings["invalid_command"])
                self.lock.release()
                return
            self.connection.commit()
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
        else: guild_ids = self.cursor.execute("select guild_id from guild_users where user_id = ?", (context.user.id,)).fetchall()
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
        await self.init_guilds(False)
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                strings = guild["strings"]
                break
        playlists = []
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == (context.guild.id if context.namespace.from_guild is None else int(context.namespace.from_guild)):
                    index = 1
                    for playlist in guild["playlists"]:
                        polished_playlist_name = self.polished_message(strings["playlist"], {"playlist": playlist["name"], "playlist_index": index})
                        playlist["name"] = (playlist["name"][:97 - len(polished_playlist_name) + len(playlist["name"])] + "..."
                                            if len(polished_playlist_name) > 100 else playlist["name"])
                        if (current == "" or current.lower() in polished_playlist_name.lower()) and len(playlists) < 25:
                            playlists.append(app_commands.Choice(name=polished_playlist_name, value=index))
                        index += 1
                    break
        else:
            if context.namespace.from_guild is None:
                playlist_names = list(self.cursor.execute("select pl_name from playlists where guild_id = ? order by guild_pl_id",
                                                          (context.guild.id,))
                                                 .fetchall())
            else: playlist_names = list(self.cursor.execute("select pl_name from playlists where guild_id = ? order by guild_pl_id",
                                                            (int(context.namespace.from_guild),))
                                                   .fetchall())
            index = 1
            for playlist in playlist_names:
                playlist_name = list(playlist)
                polished_playlist_name = self.polished_message(strings["playlist"], {"playlist": playlist_name[0], "playlist_index": index})
                playlist_name[0] = (playlist_name[0][:97 - len(polished_playlist_name) + len(playlist_name[0])] + "..."
                                    if len(polished_playlist_name) > 100 else playlist_name[0])
                if (current == "" or current.lower() in polished_playlist_name.lower()) and len(playlists) < 25:
                    playlists.append(app_commands.Choice(name=polished_playlist_name, value=index))
                index += 1
        return playlists

    @playlist_command.autocomplete("action")
    async def playlist_action_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        await self.init_guilds(False)
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
        await self.init_guilds(False)
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                strings = guild["strings"]
                break
        songs = []
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == context.guild.id:
                    try:
                        index = 1
                        for song in guild["playlists"][context.namespace.select - 1]["songs"]:
                            polished_song_name = self.polished_message(strings["song"], {"song": song["name"], "index": index})
                            song["name"] = song["name"][:97 - len(polished_song_name) + len(song["name"])] + "..." if len(polished_song_name) > 100 else song["name"]
                            if (current == "" or current.lower() in polished_song_name.lower()) and len(songs) < 25:
                                songs.append(app_commands.Choice(name=polished_song_name, value=index))
                            index += 1
                    except: pass
                    break
        else:
            try:
                song_names = list(self.cursor.execute("""select song_name from songs
                                                         left outer join playlists on playlists.pl_id = songs.pl_id
                                                         where playlists.guild_id = ? and playlists.guild_pl_id = ?
                                                         order by songs.pl_song_id""",
                                                      (context.guild.id, context.namespace.select - 1))
                                             .fetchall())
                index = 1
                for song in song_names:
                    song_name = list(song)
                    polished_song_name = self.polished_message(strings["song"], {"song": song_name[0], "index": index})
                    song_name[0] = song_name[0][:97 - len(polished_song_name) + len(song_name[0])] + "..." if len(polished_song_name) > 100 else song_name[0]
                    if (current == "" or current.lower() in polished_song_name.lower()) and len(songs) < 25:
                        songs.append(app_commands.Choice(name=polished_song_name, value=index))
                    index += 1
            except: pass
        return songs

    async def playlist_add_files(self, context: discord.Interaction, message_regarded: discord.Message):
        await context.response.defer()
        await self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                strings = guild["strings"]
                # show a dropdown menu of all the playlists for the calling guild
                playlist_options = [discord.SelectOption(label=strings["cancel_option"])]
                index = 1
                if self.cursor is None:
                    for playlist in self.data["guilds"][self.guilds.index(guild)]["playlists"]:
                        playlist_options.append(discord.SelectOption(label=self.polished_message(strings["playlist"],
                                                                                                 {"playlist": playlist["name"], "playlist_index": index}),
                                                                     value=str(index)))
                        index += 1
                else:
                    for playlist in self.cursor.execute("select pl_name from playlists where guild_id = ? order by guild_pl_id", (guild["id"],)).fetchall():
                        playlist_options.append(discord.SelectOption(label=self.polished_message(strings["playlist"],
                                                                                                 {"playlist": playlist[0], "playlist_index": index}),
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
                await context.followup.send(self.polished_message(strings["invalid_url"], {"url": str(url)}))
                return
            response = requests.get(str(url), stream=True)
            # verify that the URL file is a media container
            if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                await context.followup.send(self.polished_message(strings["invalid_song"], {"song": self.polished_song_name(str(url), song["name"])}))
                return

            playlist.append({"file": str(url), "name": song["name"], "duration": song["duration"]})
        await self.lock.acquire()
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == context.guild.id:
                    message = ""
                    for song in playlist:
                        guild["playlists"][index - 1]["songs"].append({"file": song["file"], "name": song["name"], "duration": song["duration"]})
                        previous_message = message
                        new_message = self.polished_message(strings["playlist_add_song"] + "\n",
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
        else:
            message = ""
            for song in playlist:
                self.cursor.execute("""insert into songs values((select count(song_id) from songs),
                                                                ?,
                                                                ?,
                                                                ?,
                                                                (select pl_id from playlists where guild_id = ? and guild_pl_id = ?),
                                                                (select count(song_id) from songs
                                                                 left outer join playlists on playlists.pl_id = songs.pl_id
                                                                 where playlists.guild_id = ? and playlists.guild_pl_id = ?))""",
                                    (song["name"], song["file"], song["duration"], context.guild.id, index - 1, context.guild.id, index - 1))
                previous_message = message
                new_message = self.polished_message(strings["playlist_add_song"] + "\n",
                                                    {"playlist": self.cursor.execute("select pl_name from playlists where guild_id = ? and guild_pl_id = ?",
                                                                                     (context.guild.id, index - 1))
                                                                            .fetchone()[0],
                                                     "playlist_index": index,
                                                     "song": self.polished_song_name(song["file"], song["name"]),
                                                     "index": self.cursor.execute("""select count(song_id) from songs
                                                                                     left outer join playlists on playlists.pl_id = songs.pl_id
                                                                                     where playlists.guild_id = ? and playlists.guild_pl_id = ?""",
                                                                                  (context.guild.id, index - 1))
                                                                         .fetchone()[0]})
                message += new_message
                if len(message) > 2000:
                    await context.followup.send(previous_message)
                    message = new_message
            await context.followup.send(message)
            self.connection.commit()
        self.lock.release()

    @app_commands.command(description="play_command_desc")
    async def play_command(self, context: discord.Interaction, file: discord.Attachment=None, song_url: str=None, new_name: str=None):
        await context.response.defer()
        await self.init_guilds()
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
                        await context.followup.send(self.polished_message(guild["strings"]["not_in_voice"], {"user": context.user.mention}))
                    else:
                        if url is None:
                            for song in playlist:
                                # add the track to the queue
                                guild["queue"].append({"file": song["file"], "name": song["name"], "time": "0", "duration": song["duration"], "silence": False})
                        else:
                            try: metadata = self.get_metadata(url)
                            except:
                                await context.followup.send(self.polished_message(guild["strings"]["invalid_url"], {"url": url}))
                                return
                            if name is None: name = metadata["name"]
                            response = requests.get(url, stream=True)
                            # verify that the URL file is a media container
                            if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                                await context.followup.send(self.polished_message(guild["strings"]["invalid_song"], {"song": self.polished_song_name(url, name)}))
                                return
                            await context.followup.send(self.polished_message(guild["strings"]["queue_add_song"],
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
                    break
        except: pass

    @app_commands.command(description="insert_command_desc")
    async def insert_command(self, context: discord.Interaction, file: discord.Attachment=None, song_url: str=None, new_name: str=None, new_index: int=None):
        await self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if file is None and new_index is not None and song_url is not None: await self.insert_song(context, song_url, new_name, new_index)
                elif file is not None and new_index is not None and song_url is None: await self.insert_song(context, str(file), new_name, new_index)
                else: await context.response.send_message(guild["strings"]["invalid_command"])
                break

    async def insert_song(self, context, url, name, index, time="0", duration=None, silence=False):
        try: voice_channel = context.user.voice.channel
        except: voice_channel = None
        if voice_channel is None: await context.response.send_message(self.polished_message(guild["strings"]["not_in_voice"], {"user": context.user.mention}))
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
                            await context.response.send_message(self.polished_message(guild["strings"]["invalid_url"], {"url": url}))
                            return
                        response = requests.get(url, stream=True)
                        # verify that the URL file is a media container
                        if "audio" not in response.headers.get("Content-Type", "") and "video" not in response.headers.get("Content-Type", ""):
                            await context.response.send_message(self.polished_message(guild["strings"]["invalid_song"], {"song": self.polished_song_name(url, name)}))
                            return
                        # add the track to the queue
                        guild["queue"].insert(index - 1, {"file": url, "name": name, "time": time, "duration": duration, "silence": silence})
                        if index - 1 <= guild["index"]: guild["index"] += 1
                        if not silence: await context.response.send_message(self.polished_message(guild["strings"]["queue_insert_song"],
                                                                                                  {"song": self.polished_song_name(url, name), "index": index}))
                    else: await context.response.send_message(self.polished_message(guild["strings"]["invalid_song_number"], {"index": index}))
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
                                                                                  {"song": self.polished_song_name(queue[song_index - 1]["file"],
                                                                                                                   queue[song_index - 1]["name"]),
                                                                                   "index": new_index}))
                    if song_index - 1 < guild["index"] and new_index - 1 >= guild["index"]: guild["index"] -= 1
                    elif song_index - 1 > guild["index"] and new_index - 1 <= guild["index"]: guild["index"] += 1
                    elif song_index - 1 == guild["index"] and new_index - 1 != guild["index"]: guild["index"] = new_index - 1
                    else: await context.response.send_message(self.polished_message(guild["strings"]["invalid_song_number"], {"index": new_index}))
                else: await context.response.send_message(self.polished_message(guild["strings"]["invalid_song_number"], {"index": song_index}))
                break

    @app_commands.command(description="rename_command_desc")
    async def rename_command(self, context: discord.Interaction, song_index: int, new_name: str):
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                await context.response.send_message(self.polished_message(guild["strings"]["queue_rename_song"],
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
                else: await context.response.send_message(self.polished_message(guild["strings"]["invalid_song_number"], {"index": index}))
                break

    @move_command.autocomplete("song_index")
    @rename_command.autocomplete("song_index")
    @remove_command.autocomplete("song_index")
    async def song_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[int]]:
        await self.init_guilds(False)
        songs = []
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                index = 1
                for song in guild["queue"]:
                    polished_song_name = self.polished_message(guild["strings"]["song"], {"song": song["name"], "index": index})
                    song["name"] = song["name"][:97 - len(polished_song_name) + len(song["name"])] + "..." if len(polished_song_name) > 100 else song["name"]
                    if (current == "" or current.lower() in polished_song_name.lower()) and len(songs) < 25:
                        songs.append(app_commands.Choice(name=polished_song_name, value=index))
                    index += 1
                break
        return songs

    @app_commands.command(description="skip_command_desc")
    async def skip_command(self, context: discord.Interaction, by: int=1, to: int=None):
        await self.init_guilds()
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
                                                                              {"song": self.polished_song_name(guild["queue"][guild["index"] + 1]["file"],
                                                                                                               guild["queue"][guild["index"] + 1]["name"]),
                                                                               "index": guild["index"] + 2,
                                                                               "max": len(guild["queue"])}))
                    guild["queue"][guild["index"] + 1]["silence"] = True
                    guild["time"] = .0
                    context.guild.voice_client.stop()
                else:
                    await context.response.send_message(guild["strings"]["queue_no_songs"])
                    return
                break

    @app_commands.command(description="previous_command_desc")
    async def previous_command(self, context: discord.Interaction, by: int=1):
        await self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if guild["queue"]:
                    if guild["index"] - by >= 0 and by > 0: guild["index"] -= by + 1
                    else:
                        await context.response.send_message(guild["strings"]["invalid_command"])
                        return
                    await context.response.send_message(self.polished_message(guild["strings"]["now_playing"],
                                                                              {"song": self.polished_song_name(guild["queue"][guild["index"] + 1]["file"],
                                                                                                               guild["queue"][guild["index"] + 1]["name"]),
                                                                               "index": guild["index"] + 2,
                                                                               "max": len(guild["queue"])}))
                    guild["queue"][guild["index"] + 1]["silence"] = True
                    guild["time"] = .0
                    context.guild.voice_client.stop()
                else:
                    await context.response.send_message(guild["strings"]["queue_no_songs"])
                    return
                break

    @app_commands.command(description="stop_command_desc")
    async def stop_command(self, context: discord.Interaction):
        await self.init_guilds()
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
        await self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if guild["queue"]:
                    if context.guild.voice_client.is_paused():
                        context.guild.voice_client.resume()
                        now_or_no_longer = guild["strings"]["no_longer"]
                    else:
                        context.guild.voice_client.pause()
                        now_or_no_longer = guild["strings"]["now"]
                    await context.response.send_message(self.polished_message(guild["strings"]["pause"], {"now_or_no_longer": now_or_no_longer}))
                else:
                    await context.response.send_message(guild["strings"]["queue_no_songs"])
                    return
                break

    @app_commands.command(description="jump_command_desc")
    async def jump_command(self, context: discord.Interaction, time: str): await self.jump_to(context, time)

    async def jump_to(self, context, time):
        await self.init_guilds()
        seconds = self.convert_to_seconds(time)
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if guild["queue"]:
                    await context.response.send_message(self.polished_message(guild["strings"]["jump"],
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
        await self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if guild["queue"]:
                    await context.response.send_message(self.convert_to_time(guild["time"]) + " / " + self.convert_to_time(guild["queue"][guild["index"]]["duration"]))
                else: await context.response.send_message(guild["strings"]["queue_no_songs"])
                break

    @app_commands.command(description="loop_command_desc")
    async def loop_command(self, context: discord.Interaction, set: typing.Literal[0, 1]=None):
        await self.init_guilds()
        if self.cursor is None: await self.lock.acquire()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                strings = guild["strings"]
                guild_index = self.guilds.index(guild)
                break
        if set is None:
            await context.response.send_message(self.polished_message(strings["repeat"], {"do_not": "" if self.guilds[guild_index]["repeat"] else strings["do_not"]}))
            if self.cursor is None: self.lock.release()
            return
        else:
            repeat = bool(set)
            if self.cursor is None:
                for guild in self.data["guilds"]:
                    if guild["id"] == context.guild.id:
                        guild["repeat"] = repeat
                        # modify the flat file for guilds to reflect the change of whether playlists repeat
                        yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)

                        self.guilds[guild_index]["repeat"] = repeat
                        break
            else:
                self.cursor.execute("update guilds set repeat_queue = ? where guild_id = ?", (repeat, context.guild.id))
                self.connection.commit()
                self.guilds[guild_index]["repeat"] = repeat
        await context.response.send_message(self.polished_message(strings["repeat_change"], {"now_or_no_longer": strings["now"] if repeat else strings["no_longer"]}))
        if self.cursor is None: self.lock.release()

    @app_commands.command(description="shuffle_command_desc")
    async def shuffle_command(self, context: discord.Interaction, restart: typing.Literal[0, 1]=1):
        await self.init_guilds()
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
        await self.init_guilds()
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
        await self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if guild["queue"]: await context.response.send_message(self.polished_message(guild["strings"]["now_playing"],
                                                                                             {"song": self.polished_song_name(guild["queue"][guild["index"]]["file"],
                                                                                                                              guild["queue"][guild["index"]]["name"]),
                                                                                              "index": guild["index"] + 1,
                                                                                              "max": len(guild["queue"])}))
                else: await context.response.send_message(guild["strings"]["queue_no_songs"])
                break

    @app_commands.command(description="volume_command_desc")
    async def volume_command(self, context: discord.Interaction, set: str=None):
        await self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                if set is not None:
                    if set.endswith("%"): guild["volume"] = float(set.replace("%", "")) / 100
                    else: guild["volume"] = float(set)
                    if context.guild.voice_client is not None and context.guild.voice_client.is_playing(): context.guild.voice_client.source.volume = guild["volume"]
                volume_percent = guild["volume"] * 100
                if volume_percent == float(int(volume_percent)): volume_percent = int(volume_percent)
                if set is None: await context.response.send_message(self.polished_message(guild["strings"]["volume"], {"volume": str(volume_percent) + "%"}))
                else: await context.response.send_message(self.polished_message(guild["strings"]["volume_change"], {"volume": str(volume_percent) + "%"}))
                break

    @app_commands.command(description="keep_command_desc")
    async def keep_command(self, context: discord.Interaction, set: typing.Literal[0, 1]=None):
        await self.init_guilds()
        if self.cursor is None: await self.lock.acquire()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                strings = guild["strings"]
                guild_index = self.guilds.index(guild)
                break
        try: voice_channel = context.user.voice.channel.jump_url
        except: voice_channel = strings["whatever_voice"]
        if set is None:
            await context.response.send_message(self.polished_message(strings["keep"],
                                                                      {"bot": self.bot.user.mention,
                                                                       "voice": voice_channel,
                                                                       "stay_in_or_leave": strings["stay_in"] if self.guilds[guild_index]["keep"] else strings["leave"]}))
            if self.cursor is None: self.lock.release()
            return
        else:
            keep = bool(set)
            if self.cursor is None:
                for guild in self.data["guilds"]:
                    if guild["id"] == context.guild.id:
                        guild["keep"] = keep
                        # modify the flat file for guilds to reflect the change of whether to keep this bot in a voice call when no audio is playing
                        yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)

                        self.guilds[guild_index]["keep"] = keep
                        break
            else:
                self.cursor.execute("update guilds set keep_in_voice = ? where guild_id = ?", (keep, context.guild.id))
                self.connection.commit()
                self.guilds[guild_index]["keep"] = keep
        await context.response.send_message(self.polished_message(strings["keep_change"],
                                                                  {"bot": self.bot.user.mention,
                                                                   "voice": voice_channel,
                                                                   "now_or_no_longer": strings["now"] if keep else strings["no_longer"]}))
        if self.cursor is None: self.lock.release()

    @app_commands.command(description="recruit_command_desc")
    async def recruit_command(self, context: discord.Interaction):
        await self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                try: voice_channel = context.user.voice.channel
                except:
                    await context.response.send_message(self.polished_message(guild["strings"]["not_in_voice"], {"user": context.user.mention}))
                    return
                if guild["connected"]:
                    await context.response.send_message("...")
                    await context.delete_original_response()
                else:
                    await context.response.send_message(self.polished_message(guild["strings"]["recruit_or_dismiss"],
                                                                              {"bot": self.bot.user.mention,
                                                                               "voice": voice_channel.jump_url,
                                                                               "now_or_no_longer": guild["strings"]["now"]}))
                    await voice_channel.connect()
                    guild["connected"] = True
                    await context.guild.change_voice_state(channel=voice_channel, self_mute=False, self_deaf=True)
                break

    @app_commands.command(description="dismiss_command_desc")
    async def dismiss_command(self, context: discord.Interaction):
        await self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                try: voice_channel = context.user.voice.channel
                except:
                    await context.response.send_message(self.polished_message(guild["strings"]["not_in_voice"], {"user": context.user.mention}))
                    return
                if guild["connected"]:
                    await context.response.send_message(self.polished_message(guild["strings"]["recruit_or_dismiss"],
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
        await self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                strings = guild["strings"]
                break
        if self.cursor is None:
            await self.lock.acquire()
            for guild in self.data["guilds"]:
                if guild["id"] == context.guild.id:
                    if set is None:
                        try: await context.response.send_message(self.polished_message(strings["working_thread"],
                                                                                       {"bot": self.bot.user.mention,
                                                                                        "thread": self.bot.get_guild(guild["id"])
                                                                                                          .get_thread(guild["working_thread_id"])
                                                                                                          .jump_url}))
                        except: await context.response.send_message(self.polished_message(strings["working_thread_not_assigned"], {"bot": self.bot.user.mention}))
                        break
                    thread_nonexistent = True
                    for thread in context.guild.threads:
                        if set == thread.name:
                            guild["working_thread_id"] = thread.id
                            yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
                            await context.response.send_message(self.polished_message(strings["working_thread_change"],
                                                                                      {"bot": self.bot.user.mention, "thread": thread.jump_url}))
                            thread_nonexistent = False
                            break
                    if thread_nonexistent: await context.response.send_message(strings["invalid_command"])
                    break
            self.lock.release()
        else:
            if set is None:
                working_thread_id = self.cursor.execute("select working_thread_id from guilds where guild_id = ?", (context.guild.id,)).fetchone()[0]
                try: await context.response.send_message(self.polished_message(strings["working_thread"],
                                                                               {"bot": self.bot.user.mention,
                                                                                "thread": self.bot.get_guild(context.guild.id).get_thread(working_thread_id).jump_url}))
                except: await context.response.send_message(self.polished_message(strings["working_thread_not_assigned"], {"bot": self.bot.user.mention}))
            thread_nonexistent = True
            for thread in context.guild.threads:
                if set == thread.name:
                    self.cursor.execute("update guilds set working_thread_id = ? where guild_id = ?", (thread.id, context.guild.id))
                    self.connection.commit()
                    await context.response.send_message(self.polished_message(strings["working_thread_change"],
                                                                              {"bot": self.bot.user.mention, "thread": thread.jump_url}))
                    thread_nonexistent = False
                    break
            if thread_nonexistent: await context.response.send_message(strings["invalid_command"])

    @working_thread_command.autocomplete("set")
    async def working_thread_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        threads = []
        for thread in context.guild.threads:
            if (current == "" or current.lower() in thread.name.lower()) and len(threads) < 25: threads.append(app_commands.Choice(name=thread.name, value=thread.name))
        return threads

    async def renew_attachment(self, guild_id, playlist_index, song_index, song_id=None):
        if not os.path.exists(self.music_directory): os.mkdir(self.music_directory)
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == guild_id:
                    file = f"{self.music_directory}/{self.get_file_name(guild['playlists'][playlist_index]['songs'][song_index]['file'])}"
                    open(file, "wb").write(requests.get(guild["playlists"][playlist_index]["songs"][song_index]["file"]).content)
                    while not os.path.exists(file): await asyncio.sleep(.1)
                    try: await self.bot.get_guild(guild_id).get_thread(guild["working_thread_id"]).send(yaml.safe_dump({"playlist_index": playlist_index,
                                                                                                                        "song_index": song_index}),
                                                                                                        files=[discord.File(file)])
                    except: pass
                    break
        else:
            url = self.cursor.execute("select song_url from songs where songs.song_id = ?", (song_id,)).fetchone()[0]
            working_thread_id = self.cursor.execute("select working_thread_id from guilds where guild_id = ?", (guild_id,)).fetchone()[0]
            file = f"{self.music_directory}/{self.get_file_name(url)}"
            open(file, "wb").write(requests.get(url).content)
            while not os.path.exists(file): await asyncio.sleep(.1)
            try: await self.bot.get_guild(guild_id).get_thread(working_thread_id).send(yaml.safe_dump({"song_id": song_id}), files=[discord.File(file)])
            except: pass

    @commands.Cog.listener("on_message")
    async def renew_attachment_from_message(self, message: discord.Message):
        try:
            if message.author.id != self.bot.user.id: return
            content = yaml.safe_load(message.content)
            if self.cursor is None:
                for guild in self.data["guilds"]:
                    if guild["id"] == message.guild.id:                    
                        if self.get_file_name(guild["playlists"][content["playlist_index"]]["songs"][content["song_index"]]["file"]) == message.attachments[0].filename:
                            guild["playlists"][content["playlist_index"]]["songs"][content["song_index"]]["file"] = str(message.attachments[0])
                        break
                yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
            else:
                self.cursor.execute("update songs set song_url = ? where song_id = ?", (str(message.attachments[0]), content["song_id"]))
                self.connection.commit()
            try: os.remove(f"{self.music_directory}/{message.attachments[0].filename}")
            except: pass
        except: pass
