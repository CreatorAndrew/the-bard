import os
import requests
import yaml
import sqlite3
import asyncio
import typing
import discord
from discord import app_commands
from discord.ext import commands
from Music import Music

class CommandTranslator(app_commands.Translator):
    async def translate(self, string: app_commands.locale_str, locale: discord.Locale, context: app_commands.TranslationContext) -> "str | None":
        try:
            if os.path.exists(f"{language_directory}/{locale.name}.yaml"):
                return yaml.safe_load(open(f"{language_directory}/{locale.name}.yaml", "r"))["strings"][str(string)]
            return None
        except: return None

class Main(commands.Cog):
    def __init__(self, bot, connection, cursor, data, flat_file, language_directory, lock):
        self.bot = bot
        self.connection = connection
        self.cursor = cursor
        self.data = data
        self.flat_file = flat_file
        self.language_directory = language_directory
        self.lock = lock
        self.guilds = []
        self.set_language_options()

    async def init_guilds(self):
        await self.lock.acquire()
        if self.cursor is None:
            guilds = self.data["guilds"]
            id = "id"
            language = "language"
        else:
            self.cursor.execute("select guild_id, guild_lang from guilds")
            guilds = self.cursor.fetchall()
            id = 0
            language = 1
        # add all guilds with this bot to memory that were not already
        if len(self.guilds) < len(guilds):
            ids = []
            for guild in guilds:
                for guild_searched in self.guilds: ids.append(guild_searched["id"])
                if guild[id] not in ids: self.guilds.append({"id": guild[id],
                                                             "language": guild[language],
                                                             "strings": yaml.safe_load(open(f"{self.language_directory}/{guild[language]}.yaml", "r"))["strings"]})
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

        self.lock.release()

    def set_language_options(self):
        self.language_options = []
        for language_file in sorted(os.listdir(self.language_directory)):
            if language_file.endswith(".yaml"):
                language = yaml.safe_load(open(f"{self.language_directory}/{language_file}", "r"))["name"]
                self.language_options.append(app_commands.Choice(name=language, value=language_file.replace(".yaml", "")))

    @app_commands.command(description="language_command_desc")
    async def language_command(self, context: discord.Interaction, set: str=None, add: discord.Attachment=None):
        await self.init_guilds()
        if self.cursor is None: await self.lock.acquire()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                current_language_file = guild["language"] + ".yaml"
                strings = guild["strings"]
                guild_index = self.guilds.index(guild)
                break
        if add is not None and set is None:
            file_name = str(add)[str(add).rindex("/") + 1:str(add).index("?")]
            if file_name.endswith(".yaml"):
                if not os.path.exists(f"{self.language_directory}/{file_name}"):
                    response = requests.get(str(add))
                    content = yaml.safe_load(response.content.decode("utf-8"))
                    try:
                        if content["strings"]: pass
                    except:
                        await context.response.send_message(content=strings["invalid_language_file"].replace("%{language_file}", file_name),
                                                            file=discord.File(open(f"{self.language_directory}/{current_language_file}", "r"),
                                                                              filename=current_language_file))
                        if self.cursor is None: self.lock.release()
                        return
                    for string in yaml.safe_load(open("LanguageStringNames.yaml", "r"))["names"]:
                        try:
                            if content["strings"][string] is not None: pass
                        except:
                            await context.response.send_message(content=strings["invalid_language_file"].replace("%{language_file}", file_name),
                                                                file=discord.File(open(f"{self.language_directory}/{current_language_file}", "r"),
                                                                                  filename=current_language_file))
                            if self.cursor is None: self.lock.release()
                            return
                    open(f"{self.language_directory}/{file_name}", "wb").write(response.content)
                else:
                    await context.response.send_message(strings["language_file_exists"].replace("%{language_file}", file_name))
                    if self.cursor is None: self.lock.release()
                    return
                # ensure that the attached language file is fully transferred before the language is changed to it
                while not os.path.exists(f"{self.language_directory}/{file_name}"): await asyncio.sleep(.1)

                self.set_language_options()
                language = file_name.replace(".yaml", "")
        elif add is None and set is not None:
            language = set
            if not os.path.exists(f"{self.language_directory}/{language}.yaml"):
                await context.response.send_message(content=strings["invalid_language"].replace("%{language}", language).replace("%{bot}", self.bot.user.mention),
                                                    file=discord.File(open(f"{self.language_directory}/{current_language_file}", "r"), filename=current_language_file))
                if self.cursor is None: self.lock.release()
                return
        elif add is None and set is None:
            await context.response.send_message(strings["language"].replace("%{language}",
                                                                            yaml.safe_load(open(f"{self.language_directory}/{current_language_file}", "r"))["name"]))
            if self.cursor is None: self.lock.release()
            return
        else:
            await context.response.send_message(strings["invalid_command"])
            if self.cursor is None: self.lock.release()
            return
        language_data = yaml.safe_load(open(f"{self.language_directory}/{language}.yaml", "r"))
        self.guilds[guild_index]["strings"] = language_data["strings"]
        self.guilds[guild_index]["language"] = language
        if self.cursor is None:
            for guild in self.data["guilds"]:
                if guild["id"] == context.guild.id:
                    guild["language"] = language
                    # modify the flat file for guilds to reflect the change of language
                    yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)

                    break
            self.lock.release()
        else:
            self.cursor.execute("update guilds set guild_lang = ? where guild_id = ?", (language, context.guild.id))
            self.connection.commit()
        await context.response.send_message(language_data["strings"]["language_change"].replace("%{language}", language_data["name"]))

    @language_command.autocomplete("new_name")
    async def language_name_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        language_options = []
        for language_option in self.language_options:
            if (current == "" or current.lower() in language_option.name.lower()) and len(language_options) < 25: language_options.append(language_option)
        return language_options

    # add a guild that added this bot to the database or flat file for guilds
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.lock.acquire()
        if self.cursor is None:
            users = []
            async for user in guild.fetch_members(limit=guild.member_count):
                if user.id != self.bot.user.id: users.append({"id": user.id})
            ids = []
            for guild_searched in self.data["guilds"]: ids.append(guild_searched["id"])
            if guild.id not in ids: self.data["guilds"].append({"id": guild.id,
                                                                "language": "american_english",
                                                                "repeat": False,
                                                                "keep": False,
                                                                "playlists": [],
                                                                "users": users})
            yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
        else:
            try:
                self.cursor.execute("insert into guilds values(?, ?, ?, ?, ?)", (guild.id, "american_english", None, False, False))
                async for user in guild.fetch_members(limit=guild.member_count):
                    if user.id != self.bot.user.id:
                        try: self.cursor.execute("insert into users values (?)", (user.id,))
                        except: pass
                        self.cursor.execute("insert into guild_users values (?, ?)", (guild.id, user.id))
                self.connection.commit()
            except: pass
        self.lock.release()

    # remove a guild that removed this bot from the database or flat file for guilds
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.lock.acquire()
        if self.cursor is None:
            ids = []
            for guild_searched in self.data["guilds"]: ids.append(guild_searched["id"])
            if guild.id in ids: self.data["guilds"].remove(self.data["guilds"][ids.index(guild.id)])
            yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
        else:
            self.cursor.execute("delete from guild_users where guild_id = ?", (guild.id,))
            self.cursor.execute("delete from users where user_id not in (select user_id from guild_users)")
            self.cursor.execute("delete from songs where pl_id in (select pl_id from playlists where guild_id = ?)", (guild.id,))
            self.cursor.execute("delete from playlists where guild_id = ?", (guild.id,))
            self.cursor.execute("delete from guilds where guild_id = ?", (guild.id,))
            self.connection.commit()
        self.lock.release()

    # add a user that joined a guild with this bot to the database or flat file for guilds
    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.lock.acquire()
        if member.id != self.bot.user.id:
            if self.cursor is None:
                for guild in self.data["guilds"]:
                    if guild["id"] == member.guild.id:
                        ids = []
                        for user in guild["users"]: ids.append(user["id"])
                        if member.id not in ids: guild["users"].append({"id": member.id})
                        break
                yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
            else:
                try: self.cursor.execute("insert into users values (?)", (member.id,))
                except: pass
                self.cursor.execute("insert into guild_users values (?, ?)", (member.guild.id, member.id))
                self.connection.commit()
        self.lock.release()

    # remove a user that left a guild with this bot from the database or flat file for guilds
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.lock.acquire()
        if member.id != self.bot.user.id:
            if self.cursor is None:
                for guild in self.data["guilds"]:
                    if guild["id"] == member.guild.id:
                        ids = []
                        for user in guild["users"]: ids.append(user["id"])
                        if member.id in ids: guild["users"].remove(guild["users"][ids.index(member.id)])
                        break
                yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
            else:
                self.cursor.execute("delete from guild_users where user_id = ? and guild_id = ?", (member.guild.id, member.id))
                self.cursor.execute("delete from users where user_id not in (select user_id from guild_users)")
                self.connection.commit()
        self.lock.release()

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="+", intents=intents)
bot.remove_command("help")

variables = yaml.safe_load(open("Variables.yaml", "r"))

if variables["use_flat_file"]:
    connection = None
    cursor = None
    flat_file = "Guilds.yaml"
    if not os.path.exists(flat_file): yaml.safe_dump({"guilds": []}, open(flat_file, "w"), indent=4)
    data = yaml.safe_load(open(flat_file, "r"))
else:
    data = None
    flat_file = None
    database = "Guilds.db"
    database_exists = os.path.exists(database)
    connection = sqlite3.connect(database)
    cursor = connection.cursor()
    if not database_exists:
        cursor.execute("""create table guilds(guild_id integer not null,
                                              guild_lang text not null,
                                              working_thread_id integer null,
                                              keep_in_voice boolean not null,
                                              repeat_queue boolean not null,
                                              primary key (guild_id))""")
        cursor.execute("""create table playlists(pl_id integer not null,
                                                 pl_name text not null,
                                                 guild_id integer not null,
                                                 guild_pl_id integer not null,
                                                 primary key (pl_id),
                                                 foreign key (guild_id) references guilds(guild_id))""")
        cursor.execute("""create table songs(song_id integer not null,
                                             song_name text not null,
                                             song_url text not null,
                                             song_duration float not null,
                                             pl_id integer not null,
                                             pl_song_id integer not null,
                                             primary key (song_id),
                                             foreign key (pl_id) references playlists(pl_id))""")
        cursor.execute("create table users(user_id integer not null, primary key (user_id))")
        cursor.execute("""create table guild_users(guild_id integer not null,
                                                   user_id integer not null,
                                                   primary key (guild_id, user_id),
                                                   foreign key (guild_id) references guilds(guild_id),
                                                   foreign key (user_id) references users(user_id))""")

language_directory = "Languages"
lock = asyncio.Lock()

@bot.event
async def on_ready(): print(f"Logged in as {bot.user}")

@bot.command()
async def sync_commands(context):
    if context.author.id == variables["master_id"]:
        await bot.tree.set_translator(CommandTranslator())
        synced = await bot.tree.sync()
        await context.reply(f"Synced {len(synced)} command{'' if len(synced) == 1 else 's'}")

@bot.command()
async def sync_guilds(context):
    if context.author.id == variables["master_id"]:
        await lock.acquire()
        if cursor is None: guild_count = len(data["guilds"])
        else:
            cursor.execute("select count(guild_id) from guilds")
            guild_count = cursor.fetchone()[0]
        if len(bot.guilds) > guild_count:
            async for guild in bot.fetch_guilds():
                if cursor is None:
                    users = []
                    async for user in guild.fetch_members(limit=guild.member_count):
                        if user.id != bot.user.id: users.append({"id": user.id})
                    ids = []
                    for guild_searched in data["guilds"]: ids.append(guild_searched["id"])
                    if guild.id not in ids: data["guilds"].append({"id": guild.id,
                                                                   "language": "american_english",
                                                                   "repeat": False,
                                                                   "keep": False,
                                                                   "playlists": [],
                                                                   "users": users})
                else:
                    try:
                        cursor.execute("insert into guilds values(?, ?, ?, ?, ?)", (guild.id, "american_english", None, False, False))
                        async for user in guild.fetch_members(limit=guild.member_count):
                            if user.id != bot.user.id:
                                try: cursor.execute("insert into users values (?)", (user.id,))
                                except: pass
                                cursor.execute("insert into guild_users values (?, ?)", (guild.id, user.id))
                    except: pass
        elif len(bot.guilds) < guild_count:
            ids = []
            async for guild in bot.fetch_guilds(): ids.append(guild.id)
            if cursor is None:
                index = 0
                while index < len(data["guilds"]):
                    if data["guilds"]["id"] not in ids:
                        data["guilds"].remove(data["guilds"][index]) 
                        index -= 1
                    index += 1
            else:
                cursor.execute("select guild_id from guilds")
                for id in cursor.fetchall():
                    if id[0] not in ids:
                        cursor.execute("delete from guild_users where guild_id = ?", id)
                        cursor.execute("delete from guilds where guild_id = ?", id)
                cursor.execute("delete from users where user_id not in (select user_id from guild_users)")
        if cursor is None: yaml.safe_dump(data, open(flat_file, "w"), indent=4)
        else: connection.commit()
        await context.reply(f"Synced all guilds")
        lock.release()

@bot.command()
async def sync_users(context):
    if context.author.id == variables["master_id"]:
        await lock.acquire()
        async for guild in bot.fetch_guilds():
            if cursor is None:
                for guild_searched in data["guilds"]:
                    if guild_searched["id"] == guild.id:
                        guild_index = data["guilds"].index(guild_searched)
                        user_count = len(guild_searched["users"])
                        break
            else:
                cursor.execute("select count(user_id) from guild_users where guild_id = ?", (guild.id,))
                user_count = cursor.fetchone()[0]
            # subtract 1 from the member count to exclude the bot itself
            if len(guild.members) - 1 > user_count:
                async for user in guild.fetch_members(limit=guild.member_count):
                    if user.id != bot.user.id:
                        if cursor is None:
                            ids = []
                            for user_searched in data["guilds"][guild_index]["users"]: ids.append(user_searched["id"])
                            if user.id not in ids: data["guilds"][guild_index]["users"].append({"id": user.id})
                        else:
                            try: cursor.execute("insert into users values (?)", (user.id,))
                            except: pass
                            try: cursor.execute("insert into guild_users values (?, ?)", (guild.id, user.id))
                            except: pass
            # subtract 1 from the member count to exclude the bot itself
            elif len(guild.members) - 1 < user_count:
                ids = []
                async for user in guild.fetch_members(limit=guild.member_count):
                    if user.id != bot.user.id: ids.append(user.id)
                if cursor is None:
                    index = 0
                    while index < len(data["guilds"][guild_index]["users"]):
                        if data["guilds"][guild_index]["users"][index]["id"] not in ids:
                            data["guilds"][guild_index]["users"].remove(data["guilds"][guild_index]["users"][index]) 
                            index -= 1
                        index += 1
                else:
                    cursor.execute("select user_id from guild_users where guild_id = ?", (guild.id,))
                    for id in cursor.fetchall():
                        if id[0] not in ids: cursor.execute("delete from guild_users where guild_id = ? and user_id = ?", (guild.id, id[0]))
                    cursor.execute("delete from users where user_id not in (select user_id from guild_users)")
        if cursor is None: yaml.safe_dump(data, open(flat_file, "w"), indent=4)
        else: connection.commit()
        await context.reply(f"Synced all users")
        lock.release()

async def main():
    async with bot:
        await bot.add_cog(Main(bot, connection, cursor, data, flat_file, language_directory, lock))
        await bot.add_cog(Music(bot, connection, cursor, data, flat_file, language_directory, lock))
        await bot.start(variables["token"])

asyncio.run(main())

connection.close()
