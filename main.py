from sys import platform
from os.path import isfile
from asyncio import Lock, run
from yaml import safe_dump as dump, safe_load as load
from discord import Intents
from discord.ext import commands
from utils import CommandTranslator, Cursor, load_order, variables

intents = Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="+", intents=intents)
bot.remove_command("help")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")


@bot.command()
async def sync_commands(context):
    if context.author.id == variables["master_id"]:
        await bot.tree.set_translator(CommandTranslator())
        await bot.tree.sync()
        await context.reply(
            f"Synced {len(bot.tree.get_commands())} command{'' if len(bot.tree.get_commands()) == 1 else 's'}"
        )


async def main():
    async with bot:
        if variables["storage"] == "yaml":
            connection = None
            cursor = None
            flat_file = "Bard.yaml"
            if not isfile(flat_file):
                dump({"guilds": []}, open(flat_file, "w"), indent=4)
            data = load(open(flat_file, "r"))
        else:
            data = None
            flat_file = None
            if variables["storage"] == "postgresql":
                import subprocess
                import psycopg

                credentials = f"""
                    dbname={variables["postgresql_credentials"]["user"]}
                    user={variables["postgresql_credentials"]["user"]}
                    password={variables["postgresql_credentials"]["password"]}
                    {"" if variables["postgresql_credentials"]["host"] is None else f"host={variables['postgresql_credentials']['host']}"}
                    {"" if variables["postgresql_credentials"]["port"] is None else f"port={variables['postgresql_credentials']['port']}"}
                """
                subprocess.run(
                    [
                        "psql",
                        "-c",
                        f"create database \"{variables['postgresql_credentials']['database']}\"",
                        credentials,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                )
                database_exists = False
                connection = await psycopg.AsyncConnection.connect(
                    credentials.replace(
                        f"dbname={variables['postgresql_credentials']['user']}",
                        f"dbname={variables['postgresql_credentials']['database']}",
                    ),
                    autocommit=True,
                )
                cursor = Cursor(
                    connection.cursor(), connection.cursor(), "bigint", "%s"
                )
            elif variables["storage"] == "sqlite":
                import aiosqlite

                database = "Bard.db"
                database_exists = isfile(database)
                connection = await aiosqlite.connect(database)
                cursor = Cursor(connection, None, "integer", "?")
            if not database_exists:
                try:
                    for item in load_order:
                        tables_file = f"tables/{item}.yaml"
                        if isfile(tables_file):
                            for statement in load(open(tables_file, "r")):
                                await cursor.execute(statement)
                except:
                    pass
        bot.connection = connection
        bot.cursor = cursor
        bot.data = data
        bot.flat_file = flat_file
        bot.guilds_ = {}
        bot.lock = Lock()
        bot.use_lavalink = variables["multimedia_backend"] == "lavalink"
        for item in load_order:
            if isfile(f"plugins/{item}.py"):
                await bot.load_extension(f"plugins.{item}")
        await bot.start(variables["token"])


if platform == "win32":
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy

    set_event_loop_policy(WindowsSelectorEventLoopPolicy())

run(main())
