import os
import shutil
import requests
import yaml
import asyncio
import discord
from discord.ext import commands
from Music import Music

class Main(commands.Cog):
    def __init__(self, bot, config, language_directory, lock):
        self.lock = lock
        self.bot = bot
        self.servers = []
        self.config = config
        self.language_directory = language_directory
        if not os.path.exists(self.config): shutil.copyfile(self.config.replace(".yaml", "") + "Default.yaml", self.config)

    # initialize any registered Discord servers that weren't previously initialized
    def initialize_servers(self):
        with open(self.config, "r") as read_file: data = yaml.safe_load(read_file)
        if len(self.servers) < len(data["servers"]):
            ids = []
            for server in data["servers"]:
                with open(f"{self.language_directory}/{server['language']}.yaml", "r") as read_file: language = yaml.safe_load(read_file)
                for server_searched in self.servers: ids.append(server_searched["id"])
                if server["id"] not in ids: self.servers.append({"id": server["id"], "language": server["language"], "strings": language["strings"]})
        elif len(self.servers) > len(data["servers"]):
            index = 0
            while index < len(self.servers):
                try:
                    if self.servers[index]["id"] != data["servers"][index]["id"]:
                        self.servers.remove(self.servers[index])
                        index -= 1
                except: self.servers.remove(self.servers[index])
                index += 1

    @commands.command()
    async def language(self, context, name=None):
        await self.lock.acquire()
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                current_language_file = server["language"] + ".yaml"
                strings = server["strings"]
                break
        if context.message.attachments:
            attachment = context.message.attachments[0]
            file = str(attachment)[str(attachment).rindex("/") + 1:str(attachment).index("?")].replace("_", " ")
            if file.endswith(".yaml"):
                if not os.path.exists(f"{self.language_directory}/{file}"):
                    response = requests.get(str(attachment))
                    content = yaml.safe_load(response.content.decode("utf-8"))
                    try:
                        if content["strings"]: pass
                    except:
                        await context.reply(content=strings["invalid_language_file"].replace("%{language}", file),
                                            file=discord.File(read_file, filename=current_language_file))
                        self.lock.release()
                        return
                    with open("LanguageStringNames.yaml", "r") as read_file: language_strings = yaml.safe_load(read_file)
                    for string in language_strings["names"]:
                        try:
                            if content["strings"][string] is not None: pass
                        except:
                            with open(f"{self.language_directory}/{current_language_file}", "r") as read_file:
                                await context.reply(content=strings["invalid_language_file"].replace("%{language}", file),
                                                    file=discord.File(read_file, filename=current_language_file))
                            self.lock.release()
                            return
                    open(f"{self.language_directory}/{file}", "wb").write(response.content)
                else:
                    await context.reply(strings["language_file_exists"].replace("%{language}", file))
                    self.lock.release()
                    return
                # ensure that the attached YAML file is fully transferred before the language is changed to it
                while not os.path.exists(f"{self.language_directory}/{file}"): await asyncio.sleep(.1)

                language = file.replace(".yaml", "")
        elif name is not None:
            language = name
            if not os.path.exists(f"{self.language_directory}/{language}.yaml"):
                with open(f"{self.language_directory}/{current_language_file}", "r") as read_file:
                    await context.reply(content=strings["invalid_language"].replace("%{language}", language).replace("%{bot}", self.bot.user.mention),
                                        file=discord.File(read_file, filename=current_language_file))
                self.lock.release()
                return
        else:
            with open(f"{self.language_directory}/{current_language_file}", "r") as read_file: await context.reply(strings["invalid_command"])
            self.lock.release()
            return
        with open(self.config, "r") as read_file: data = yaml.safe_load(read_file)
        for server in data["servers"]:
            if server["id"] == context.message.guild.id:
                with open(f"{self.language_directory}/{language}.yaml", "r") as read_file: language_data = yaml.safe_load(read_file)
                self.servers[data["servers"].index(server)]["strings"] = language_data["strings"]
                self.servers[data["servers"].index(server)]["language"] = language
                server["language"] = language
                # modify the YAML file to reflect the change of language
                with open(self.config, "w") as write_file: yaml.safe_dump(data, write_file, indent=4)

                language_message = self.servers[data["servers"].index(server)]["strings"]["language"]
                break
        await context.reply(language_message.replace("%{language}", language))
        self.lock.release()

    @commands.command()
    async def help(self, context):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id: 
                await context.send(server["strings"]["help"].replace("%{bot}", self.bot.user.mention))
                return

    # add a Discord server that added this bot to the YAML file
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.lock.acquire()
        with open(self.config, "r") as read_file: data = yaml.safe_load(read_file)
        with open(self.config, "w") as write_file:
            ids = []
            for server in data["servers"]: ids.append(server["id"])
            if guild.id not in ids:
                data["servers"].append({"id": guild.id,
                                        "language": "English",
                                        "repeat": False,
                                        "keep": False,
                                        "playlists": [],
                                        "users": [],
                                        "role": None})
            yaml.safe_dump(data, write_file, indent=4)
        self.lock.release()

    # remove a Discord server that removed this bot from the YAML file
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.lock.acquire()
        with open(self.config, "r") as read_file: data = yaml.safe_load(read_file)
        with open(self.config, "w") as write_file:
            ids = []
            for server in data["servers"]: ids.append(server["id"])
            if guild.id in ids: data["servers"].remove(data["servers"][ids.index(guild.id)])
            yaml.safe_dump(data, write_file, indent=4)
        self.lock.release()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix = "+", intents = intents)
bot.remove_command("help")

lock = asyncio.Lock()
config = "Servers.yaml"
language_directory = "Languages"

@bot.event
async def on_ready(): print(f"Logged in as {bot.user}")

async def main():
    with open("Token.yaml", "r") as read_file: data = yaml.safe_load(read_file)
    async with bot:
        await bot.add_cog(Main(bot, config, language_directory, lock))
        await bot.add_cog(Music(bot, config, language_directory, lock))
        await bot.start(data["token"])

asyncio.run(main())
