from sys import platform
from os.path import exists
from asyncio import Lock, run
from yaml import safe_dump as dump, safe_load as load
from discord import Intents
from discord.ext.commands import Bot
from utils import CommandTranslator, CREDENTIALS, Cursor, LOAD_ORDER, VARIABLES

intents = Intents.default()
intents.members = True
intents.message_content = True

bot = Bot(command_prefix="+", intents=intents)
bot.remove_command("help")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")


@bot.command()
async def sync_commands(context):
    if context.author.id == VARIABLES["master_id"]:
        await bot.tree.set_translator(CommandTranslator())
        await bot.tree.sync()
        await context.reply(
            f"Synced {len(bot.tree.get_commands())} command{'' if len(bot.tree.get_commands()) == 1 else 's'}"
        )


async def main():
    async with bot:
        if VARIABLES["storage"] == "yaml":
            connection = None
            cursor = None
            flat_file = f"{VARIABLES["name"]}.yaml"
            if not exists(flat_file):
                dump({"guilds": []}, open(flat_file, "w"), indent=4)
            data = load(open(flat_file, "r"))
        else:
            data = None
            flat_file = None
            if VARIABLES["storage"] == "postgresql":
                import subprocess
                import psycopg

                subprocess.run(
                    [
                        "psql",
                        "-c",
                        f"create database \"{VARIABLES['postgresql_credentials']['database']}\"",
                        CREDENTIALS.replace(
                            f"dbname={VARIABLES['postgresql_credentials']['database']}",
                            f"dbname={VARIABLES['postgresql_credentials']['user']}",
                        ),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                )
                database_exists = False
                connection = await psycopg.AsyncConnection.connect(
                    CREDENTIALS, autocommit=True
                )
                cursor = Cursor(connection.cursor(), connection.cursor(), "%s")
            elif VARIABLES["storage"] == "sqlite":
                import aiosqlite

                database = f"{VARIABLES["name"]}.db"
                database_exists = exists(database)
                connection = await aiosqlite.connect(database)
                cursor = Cursor(connection, None, "?")
            if not database_exists:
                try:
                    for item in LOAD_ORDER:
                        tables_file = f"tables/{item}.yaml"
                        if exists(tables_file):
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
        for item in LOAD_ORDER:
            if exists(f"plugins/{item}.py"):
                await bot.load_extension(f"plugins.{item}")
        await bot.start(VARIABLES["token"])


if platform == "win32":
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy

    set_event_loop_policy(WindowsSelectorEventLoopPolicy())

run(main())
