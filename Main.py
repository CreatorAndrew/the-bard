import os
import shutil
import requests
import yaml
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
    def __init__(self, bot, flat_file, data, language_directory, lock):
        self.bot = bot
        self.flat_file = flat_file
        self.data = data
        self.language_directory = language_directory
        self.lock = lock
        self.guilds = []
        self.set_language_options()

    def init_guilds(self):
        # add all guilds with this bot to memory that were not already
        if len(self.guilds) < len(self.data["guilds"]):
            ids = []
            for guild in self.data["guilds"]:
                for guild_searched in self.guilds: ids.append(guild_searched["id"])
                if guild["id"] not in ids: self.guilds.append({"id": guild["id"],
                                                               "language": guild["language"],
                                                               "strings": yaml.safe_load(open(f"{self.language_directory}/{guild['language']}.yaml", "r"))["strings"]})
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

    def set_language_options(self):
        self.language_options = []
        for language_file in sorted(os.listdir(self.language_directory)):
            if language_file.endswith(".yaml"):
                language = yaml.safe_load(open(f"{self.language_directory}/{language_file}", "r"))["strings"]["language"]
                self.language_options.append(app_commands.Choice(name=language, value=language_file.replace(".yaml", "")))

    @app_commands.command(description="language_command_desc")
    async def language_command(self, context: discord.Interaction, file: discord.Attachment=None, new_name: str=None):
        await self.lock.acquire()
        self.init_guilds()
        for guild in self.guilds:
            if guild["id"] == context.guild.id:
                current_language_file = guild["language"] + ".yaml"
                strings = guild["strings"]
                break
        if file is not None and new_name is None:
            file_name = str(file)[str(file).rindex("/") + 1:str(file).index("?")]
            if file_name.endswith(".yaml"):
                if not os.path.exists(f"{self.language_directory}/{file_name}"):
                    response = requests.get(str(file))
                    content = yaml.safe_load(response.content.decode("utf-8"))
                    try:
                        if content["strings"]: pass
                    except:
                        await context.response.send_message(content=strings["invalid_language_file"].replace("%{language_file}", file_name),
                                                            file=discord.File(open(f"{self.language_directory}/{current_language_file}", "r"),
                                                                              filename=current_language_file))
                        self.lock.release()
                        return
                    for string in yaml.safe_load(open("LanguageStringNames.yaml", "r"))["names"]:
                        try:
                            if content["strings"][string] is not None: pass
                        except:
                            await context.response.send_message(content=strings["invalid_language_file"].replace("%{language_file}", file_name),
                                                                file=discord.File(open(f"{self.language_directory}/{current_language_file}", "r"),
                                                                                  filename=current_language_file))
                            self.lock.release()
                            return
                    open(f"{self.language_directory}/{file_name}", "wb").write(response.content)
                else:
                    await context.response.send_message(strings["language_file_exists"].replace("%{language_file}", file_name))
                    self.lock.release()
                    return
                # ensure that the attached language file is fully transferred before the language is changed to it
                while not os.path.exists(f"{self.language_directory}/{file_name}"): await asyncio.sleep(.1)

                self.set_language_options()
                language = file_name.replace(".yaml", "")
        elif file is None and new_name is not None:
            language = new_name
            if not os.path.exists(f"{self.language_directory}/{language}.yaml"):
                await context.response.send_message(content=strings["invalid_language"].replace("%{language}", language).replace("%{bot}", self.bot.user.mention),
                                                    file=discord.File(open(f"{self.language_directory}/{current_language_file}", "r"), filename=current_language_file))
                self.lock.release()
                return
        else:
            await context.response.send_message(strings["invalid_command"])
            self.lock.release()
            return
        for guild in self.data["guilds"]:
            if guild["id"] == context.guild.id:
                language_data = yaml.safe_load(open(f"{self.language_directory}/{language}.yaml", "r"))
                self.guilds[self.data["guilds"].index(guild)]["strings"] = language_data["strings"]
                self.guilds[self.data["guilds"].index(guild)]["language"] = language
                guild["language"] = language
                # modify the flat file for guilds to reflect the change of language
                yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)

                await context.response.send_message(language_data["strings"]["language_change"].replace("%{language}", language_data["strings"]["language"]))
                break
        self.lock.release()

    @language_command.autocomplete("new_name")
    async def language_name_autocompletion(self, context: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        language_options = []
        for language_option in self.language_options:
            if (current == "" or current.lower() in language_option.name.lower()) and len(language_options) < 25: language_options.append(language_option)
        return language_options

    # add a guild that added this bot to the flat file for guilds
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.lock.acquire()
        ids = []
        for guild in self.data["guilds"]: ids.append(guild["id"])
        if guild.id not in ids: self.data["guilds"].append({"id": guild.id,
                                                            "language": "american_english",
                                                            "repeat": False,
                                                            "keep": False,
                                                            "playlists": []})
        yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
        self.lock.release()

    # remove a guild that removed this bot from the flat file for guilds
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.lock.acquire()
        ids = []
        for guild in self.data["guilds"]: ids.append(guild["id"])
        if guild.id in ids: self.data["guilds"].remove(self.data["guilds"][ids.index(guild.id)])
        yaml.safe_dump(self.data, open(self.flat_file, "w"), indent=4)
        self.lock.release()

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="+", intents=intents)
bot.remove_command("help")

flat_file = "Guilds.yaml"
if not os.path.exists(flat_file): shutil.copyfile(flat_file.replace(".yaml", "") + "Default.yaml", flat_file)
data = yaml.safe_load(open(flat_file, "r"))
language_directory = "Languages"
lock = asyncio.Lock()

@bot.event
async def on_ready(): print(f"Logged in as {bot.user}")

@bot.command()
async def sync(context):
    if context.author.id == yaml.safe_load(open("Variables.yaml", "r"))["master_id"]:
        await bot.tree.set_translator(CommandTranslator())
        synced = await bot.tree.sync()
        if len(synced) == 1: plural = ""
        else: plural = "s"
        await context.reply(f"Synced {len(synced)} command" + plural)

async def main():
    async with bot:
        await bot.add_cog(Main(bot, flat_file, data, language_directory, lock))
        await bot.add_cog(Music(bot, flat_file, data, language_directory, lock))
        await bot.start(yaml.safe_load(open("Variables.yaml", "r"))["token"])

asyncio.run(main())
