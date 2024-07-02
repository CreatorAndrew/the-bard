from os import listdir
from os.path import exists
from asyncio import sleep
from typing import List
import requests
from yaml import safe_dump as dump, safe_load as load
from discord import Attachment, File, Interaction
from discord.app_commands import Choice, command
from discord.ext.commands import Cog, command as message_command
from utils import LANGUAGE_DIRECTORY, variables


class Main(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.connection = bot.connection
        self.cursor = bot.cursor
        self.data = bot.data
        self.default_language = "american_english"
        self.flat_file = bot.flat_file
        self.guilds = bot.guilds_
        self.init_guilds(bot.main_init_guilds)
        self.lock = bot.lock
        self.set_language_options()

    def init_guilds(self, guilds=None):
        if self.cursor is None:
            guilds = self.data["guilds"]
            id = "id"
            language = "language"
        else:
            id = 0
            language = 1
        for guild in guilds:
            self.guilds[str(guild[id])] = {
                "language": guild[language],
                "strings": load(
                    open(f"{LANGUAGE_DIRECTORY}/{guild[language]}.yaml", "r")
                )["strings"],
            }

    def set_language_options(self):
        self.language_options = []
        for language_file in sorted(listdir(LANGUAGE_DIRECTORY)):
            if language_file.endswith(".yaml"):
                language = load(open(f"{LANGUAGE_DIRECTORY}/{language_file}", "r"))[
                    "name"
                ]
                self.language_options.append(
                    Choice(name=language, value=language_file.replace(".yaml", ""))
                )

    @command(description="language_command_desc")
    async def language_command(
        self, context: Interaction, set: str = None, add: Attachment = None
    ):
        await self.lock.acquire()
        guild = self.guilds[str(context.guild.id)]
        current_language_file = guild["language"] + ".yaml"
        strings = guild["strings"]
        if add is not None and set is None:
            file_name = str(add)[str(add).rindex("/") + 1 : str(add).index("?")]
            if file_name.endswith(".yaml"):
                if not exists(f"{LANGUAGE_DIRECTORY}/{file_name}"):
                    response = requests.get(str(add))
                    content = load(response.content.decode("utf-8"))
                    try:
                        if content["strings"]:
                            pass
                    except:
                        await context.response.send_message(
                            strings["invalid_language_file"].replace(
                                "%{language_file}", file_name
                            ),
                            file=File(
                                open(
                                    f"{LANGUAGE_DIRECTORY}/{current_language_file}", "r"
                                ),
                                filename=current_language_file,
                            ),
                            ephemeral=True,
                        )
                        self.lock.release()
                        return
                    for string in list(
                        map(
                            lambda line: line.replace("\r\n", "").replace("\n", ""),
                            open("language_strings_names.txt", "r").readlines(),
                        )
                    ):
                        try:
                            if content["strings"][string]:
                                pass
                        except:
                            await context.response.send_message(
                                strings["invalid_language_file"].replace(
                                    "%{language_file}", file_name
                                ),
                                file=File(
                                    open(
                                        f"{LANGUAGE_DIRECTORY}/{current_language_file}",
                                        "r",
                                    ),
                                    filename=current_language_file,
                                ),
                                ephemeral=True,
                            )
                            self.lock.release()
                            return
                    open(f"{LANGUAGE_DIRECTORY}/{file_name}", "wb").write(
                        response.content
                    )
                else:
                    await context.response.send_message(
                        strings["language_file_exists"].replace(
                            "%{language_file}", file_name
                        )
                    )
                    self.lock.release()
                    return
                # ensure that the attached language file is fully transferred before the language is changed to it
                while not exists(f"{LANGUAGE_DIRECTORY}/{file_name}"):
                    await sleep(0.1)

                self.set_language_options()
                language = file_name.replace(".yaml", "")
        elif add is None and set is not None:
            language = set
            if not exists(f"{LANGUAGE_DIRECTORY}/{language}.yaml"):
                await context.response.send_message(
                    strings["invalid_language"]
                    .replace("%{language}", language)
                    .replace("%{bot}", self.bot.user.mention),
                    file=File(
                        open(f"{LANGUAGE_DIRECTORY}/{current_language_file}", "r"),
                        filename=current_language_file,
                    ),
                    ephemeral=True,
                )
                self.lock.release()
                return
        elif add is None and set is None:
            await context.response.send_message(
                strings["language"].replace(
                    "%{language}",
                    load(open(f"{LANGUAGE_DIRECTORY}/{current_language_file}", "r"))[
                        "name"
                    ],
                ),
                ephemeral=True,
            )
            self.lock.release()
            return
        else:
            await context.response.send_message(
                strings["invalid_command"], ephemeral=True
            )
            self.lock.release()
            return
        language_data = load(open(f"{LANGUAGE_DIRECTORY}/{language}.yaml", "r"))
        guild["strings"] = language_data["strings"]
        guild["language"] = language
        if self.cursor is None:
            for guild_searched in self.data["guilds"]:
                if guild_searched["id"] == context.guild.id:
                    guild_searched["language"] = language
                    # modify the flat file for guilds to reflect the change of language
                    dump(self.data, open(self.flat_file, "w"), indent=4)

                    break
        else:
            await self.cursor.execute(
                "update guilds set guild_lang = ? where guild_id = ?",
                (language, context.guild.id),
            )
            await self.connection.commit()
        await context.response.send_message(
            language_data["strings"]["language_change"].replace(
                "%{language}", language_data["name"]
            )
        )
        self.lock.release()

    @language_command.autocomplete("set")
    async def language_name_autocompletion(
        self, context: Interaction, current: str
    ) -> List[Choice[str]]:
        language_options = []
        for language_option in self.language_options:
            if (
                current == "" or current.lower() in language_option.name.lower()
            ) and len(language_options) < 25:
                language_options.append(language_option)
        return language_options

    # add a guild that added this bot to the database or flat file for guilds
    @Cog.listener()
    async def on_guild_join(self, guild):
        await self.lock.acquire()
        await self.add_guild(guild)
        self.bot.dispatch("bard_guild_join")
        self.lock.release()

    # remove a guild that removed this bot from the database or flat file for guilds
    @Cog.listener()
    async def on_guild_remove(self, guild):
        await self.lock.acquire()
        if self.cursor is None:
            ids = []
            for guild_searched in self.data["guilds"]:
                ids.append(guild_searched["id"])
            if guild.id in ids:
                self.data["guilds"].remove(self.data["guilds"][ids.index(guild.id)])
            dump(self.data, open(self.flat_file, "w"), indent=4)
        else:
            await self.remove_guild_from_database(guild.id)
        del self.guilds[str(guild.id)]
        self.bot.dispatch("bard_guild_remove")
        self.lock.release()

    # add a user that joined a guild with this bot to the database or flat file for guilds
    @Cog.listener()
    async def on_member_join(self, member):
        if member.id != self.bot.user.id:
            await self.lock.acquire()
            if self.cursor is None:
                for guild in self.data["guilds"]:
                    if guild["id"] == member.guild.id:
                        await self.add_user(guild, member)
                        break
                dump(self.data, open(self.flat_file, "w"), indent=4)
            else:
                await self.add_user(member.guild, member)
                await self.connection.commit()
            self.bot.dispatch("bard_member_join")
            self.lock.release()

    # remove a user that left a guild with this bot from the database or flat file for guilds
    @Cog.listener()
    async def on_member_remove(self, member):
        if member.id != self.bot.user.id:
            await self.lock.acquire()
            if self.cursor is None:
                for guild in self.data["guilds"]:
                    if guild["id"] == member.guild.id:
                        ids = []
                        for user in guild["users"]:
                            ids.append(user["id"])
                        if member.id in ids:
                            guild["users"].remove(guild["users"][ids.index(member.id)])
                        break
                dump(self.data, open(self.flat_file, "w"), indent=4)
            else:
                await self.cursor.execute(
                    "delete from guild_users where user_id = ? and guild_id = ?",
                    (member.guild.id, member.id),
                )
                await self.cursor.execute(
                    "delete from users where user_id not in (select user_id from guild_users)"
                )
                await self.connection.commit()
            self.bot.dispatch("bard_member_remove")
            self.lock.release()

    @message_command()
    async def sync_guilds(self, context):
        if context.author.id == variables["master_id"]:
            await self.lock.acquire()
            if self.cursor is None:
                guild_count = len(self.data["guilds"])
            else:
                await self.cursor.execute("select count(guild_id) from guilds")
                guild_count = (await self.cursor.fetchone())[0]
            if len(self.bot.guilds) > guild_count:
                async for guild in self.bot.fetch_guilds():
                    await self.add_guild(guild)
            elif len(self.bot.guilds) < guild_count:
                ids = []
                async for guild in self.bot.fetch_guilds():
                    ids.append(guild.id)
                if self.cursor is None:
                    index = 0
                    while index < len(self.data["guilds"]):
                        if self.data["guilds"][index]["id"] not in ids:
                            del self.guilds[str(self.data["guilds"][index]["id"])]
                            self.data["guilds"].remove(self.data["guilds"][index])
                            index -= 1
                        index += 1
                    dump(self.data, open(self.flat_file, "w"), indent=4)
                else:
                    await self.cursor.execute("select guild_id from guilds")
                    for id in await self.cursor.fetchall():
                        if id[0] not in ids:
                            del self.guilds[str(id[0])]
                            await self.remove_guild_from_database(id[0])
            await context.reply("Synced all guilds")
            self.lock.release()

    @message_command()
    async def sync_users(self, context):
        if context.author.id == variables["master_id"]:
            await self.lock.acquire()
            async for guild in self.bot.fetch_guilds():
                if self.cursor is None:
                    for guild_searched in self.data["guilds"]:
                        if guild_searched["id"] == guild.id:
                            guild_index = self.data["guilds"].index(guild_searched)
                            user_count = len(guild_searched["users"])
                            break
                else:
                    await self.cursor.execute(
                        "select count(user_id) from guild_users where guild_id = ?",
                        (guild.id,),
                    )
                    user_count = (await self.cursor.fetchone())[0]
                # subtract 1 from the member count to exclude the bot itself
                if len(guild.members) - 1 > user_count:
                    async for user in guild.fetch_members(limit=guild.member_count):
                        if user.id != self.bot.user.id:
                            await self.add_user(
                                (
                                    self.data["guilds"][guild_index]["users"]
                                    if self.cursor is None
                                    else guild
                                ),
                                user,
                            )
                # subtract 1 from the member count to exclude the bot itself
                elif len(guild.members) - 1 < user_count:
                    ids = []
                    async for user in guild.fetch_members(limit=guild.member_count):
                        if user.id != self.bot.user.id:
                            ids.append(user.id)
                    if self.cursor is None:
                        index = 0
                        while index < len(self.data["guilds"][guild_index]["users"]):
                            if (
                                self.data["guilds"][guild_index]["users"][index]["id"]
                                not in ids
                            ):
                                self.data["guilds"][guild_index]["users"].remove(
                                    self.data["guilds"][guild_index]["users"][index]
                                )
                                index -= 1
                            index += 1
                    else:
                        await self.cursor.execute(
                            "select user_id from guild_users where guild_id = ?",
                            (guild.id,),
                        )
                        for id in await self.cursor.fetchall():
                            if id[0] not in ids:
                                await self.cursor.execute(
                                    "delete from guild_users where guild_id = ? and user_id = ?",
                                    (guild.id, id[0]),
                                )
                        await self.cursor.execute(
                            "delete from users where user_id not in (select user_id from guild_users)"
                        )
            if self.cursor is None:
                dump(self.data, open(self.flat_file, "w"), indent=4)
            else:
                await self.connection.commit()
            await context.reply("Synced all users")
            self.lock.release()

    async def add_guild(self, guild):
        init_guild = False
        if self.cursor is None:
            ids = []
            for guild_searched in self.data["guilds"]:
                ids.append(guild_searched["id"])
            if guild.id not in ids:
                self.data["guilds"].append(
                    {
                        "id": guild.id,
                        "language": self.default_language,
                        "users": [],
                    }
                )
                async for user in guild.fetch_members(limit=guild.member_count):
                    if user.id != self.bot.user.id:
                        await self.add_user(
                            self.data["guilds"][len(self.data["guilds"]) - 1], user
                        )
                dump(self.data, open(self.flat_file, "w"), indent=4)
                init_guild = True
        else:
            try:
                await self.cursor.execute(
                    "insert into guilds values(?, ?)",
                    (guild.id, self.default_language),
                )
                async for user in guild.fetch_members(limit=guild.member_count):
                    if user.id != self.bot.user.id:
                        await self.add_user(guild, user)
                await self.connection.commit()
                init_guild = True
            except:
                pass
        if init_guild:
            self.guilds[str(guild.id)] = {
                "language": self.default_language,
                "strings": load(
                    open(f"{LANGUAGE_DIRECTORY}/{self.default_language}.yaml", "r")
                )["strings"],
            }
        try:
            self.bot.dispatch("bard_add_guild", guild)
        except:
            pass

    async def remove_guild_from_database(self, id):
        await self.cursor.execute("delete from guilds where guild_id = ?", (id,))
        await self.cursor.execute(
            "delete from users where user_id not in (select user_id from guild_users)"
        )
        await self.connection.commit()
        self.bot.dispatch("bard_remove_guild_from_database")

    async def add_user(self, guild, user):
        if self.cursor is None:
            ids = []
            for user_searched in guild["users"]:
                ids.append(user_searched["id"])
            if user.id not in ids:
                guild["users"].append({"id": user.id})
        else:
            try:
                await self.cursor.execute("insert into users values(?)", (user.id,))
            except:
                pass
            try:
                await self.cursor.execute(
                    "insert into guild_users values(?, ?)", (guild.id, user.id)
                )
            except:
                pass
        self.bot.dispatch("bard_add_user", guild, user)


async def setup(bot):
    bot.main_init_guilds = None
    if bot.cursor is not None:
        await bot.cursor.execute("select guild_id, guild_lang from guilds")
        bot.main_init_guilds = await bot.cursor.fetchall()
    await bot.add_cog(Main(bot))
