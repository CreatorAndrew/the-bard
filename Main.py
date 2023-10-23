import os
import shutil
import requests
import yaml
import asyncio
import discord
from discord.ext import commands
from Music import Music

class Main(commands.Cog):
    def __init__(self, bot, config, language_directory):
        self.bot = bot
        self.servers = []
        self.language_directory = language_directory
        self.config = config
        if not os.path.exists(self.config): shutil.copyfile(self.config.replace(".yaml", "") + "Default.yaml", self.config)

    # initialize any registered Discord servers that weren't previously initialized
    def initialize_servers(self):
        with open(self.config, "r") as read_file: data = yaml.load(read_file, yaml.Loader)
        if len(self.servers) < len(data["servers"]):
            ids = []
            for server in data["servers"]:
                with open(f"{self.language_directory}/{server['language']}.yaml", "r") as read_file: language = yaml.load(read_file, yaml.Loader)
                for server_searched in self.servers: ids.append(server_searched["id"])
                if server["id"] not in ids: self.servers.append({"id": server["id"], "strings": language["strings"]})

    # add the calling Discord server to the YAML file
    @commands.command()
    async def add_me(self, context):
        with open(self.config, "r") as read_file: data = yaml.load(read_file, yaml.Loader)
        with open(self.config, "w") as write_file:
            ids = []
            for server in data["servers"]: ids.append(server["id"])
            if context.message.guild.id not in ids:
                data["servers"].append({"id": context.message.guild.id, "language": "English", "repeat": False, "keep": False, "users": [], "role": None})
                await context.send("Server added.\nType `+help` for a list of commands.")
            else: await context.send("This server was already added.")
            yaml.dump(data, write_file, yaml.Dumper, indent = 4)

    @commands.command()
    async def language(self, context, language_name = None):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id:
                invalid_command = server["strings"]["invalid_command"]
                language_file_exists = server["strings"]["language_file_exists"]
                break
        if context.message.attachments:
            attachment = context.message.attachments[0]
            file = str(attachment)[str(attachment).rindex("/") + 1:str(attachment).index("?")].replace("_", " ")
            if file.endswith(".yaml"):
                if not os.path.exists(f"{self.language_directory}/{file}"):
                    open(f"{self.language_directory}/{file}", "wb").write(requests.get(str(attachment)).content)
                else:
                    await context.reply(language_file_exists.replace("%{language}", file))
                    return
                # ensure that the attached file is fully transferred before the language is changed to it
                while not os.path.exists(f"{self.language_directory}/{file}"): await asyncio.sleep(.1)

                language = file.replace(".yaml", "")
        elif language_name is not None: language = language_name
        else:
            await context.reply(invalid_command)
            return
        with open(self.config, "r") as read_file: data = yaml.load(read_file, yaml.Loader)
        for server in data["servers"]:
            if server["id"] == context.message.guild.id:
                with open(f"{self.language_directory}/{language}.yaml", "r") as read_file: language_data = yaml.load(read_file, yaml.Loader)
                self.servers[data["servers"].index(server)]["strings"] = language_data["strings"]
                server["language"] = language
                # modify the YAML file to reflect the change of language
                with open(self.config, "w") as write_file: yaml.dump(data, write_file, yaml.Dumper, indent = 4)

                language_message = self.servers[data["servers"].index(server)]["strings"]["language"]
                break
        await context.reply(language_message.replace("%{language}", language))

    @commands.command()
    async def help(self, context):
        self.initialize_servers()
        for server in self.servers:
            if server["id"] == context.message.guild.id: await context.send(server["strings"]["help"].replace("%{bot}", self.bot.user.mention))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix = "+", intents = intents)
bot.remove_command("help")

config = "Servers.yaml"
language_directory = "Languages"

@bot.event
async def on_ready(): print(f"Logged in as {bot.user}")

async def main():
    with open("Token.yaml", "r") as read_file: data = yaml.load(read_file, yaml.Loader)
    async with bot:
        await bot.add_cog(Main(bot, config, language_directory))
        await bot.add_cog(Music(bot, config, language_directory))
        await bot.start(data["token"])

asyncio.run(main())
