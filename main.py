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
            flat_file = f"{VARIABLES['name']}.yaml"
            if not exists(flat_file):
                dump({"guilds": []}, open(flat_file, "w"), indent=4)
            data = load(open(flat_file, "r"))
        else:
            data = None
            flat_file = None
            if VARIABLES["storage"] == "mysql":
                from aiomysql import create_pool

                pool = await create_pool(
                    1,
                    1,
                    host=(
                        "localhost"
                        if VARIABLES["database_credentials"]["host"] is None
                        else VARIABLES["database_credentials"]["host"]
                    ),
                    port=(
                        3306
                        if VARIABLES["database_credentials"]["port"] is None
                        else VARIABLES["database_credentials"]["port"]
                    ),
                    user=VARIABLES["database_credentials"]["user"],
                    password=VARIABLES["database_credentials"]["password"],
                    autocommit=True,
                )
                connection = await pool.acquire()
                _cursor = await connection.cursor()
                try:
                    await _cursor.execute(
                        f"create database `{VARIABLES['database_credentials']['database']}`"
                    )
                except:
                    database_exists = True
                else:
                    database_exists = False
                await _cursor.execute(
                    f"use `{VARIABLES['database_credentials']['database']}`"
                )
                cursor = Cursor(connection, _cursor, "%s", pool.acquire, pool.release)
            elif VARIABLES["storage"] == "postgresql":
                from subprocess import DEVNULL, run as execute, STDOUT
                import psycopg

                execute(
                    [
                        "psql",
                        "-c",
                        f"create database \"{VARIABLES['database_credentials']['database']}\"",
                        CREDENTIALS.replace(
                            f"dbname={VARIABLES['database_credentials']['database']}",
                            f"dbname={VARIABLES['database_credentials']['user']}",
                        ),
                    ],
                    stdout=DEVNULL,
                    stderr=STDOUT,
                )
                database_exists = False
                connection = await psycopg.AsyncConnection.connect(
                    CREDENTIALS, autocommit=True
                )
                cursor = Cursor(connection.cursor(), connection.cursor(), "%s")
            elif VARIABLES["storage"] == "sqlite":
                from aiosqlite import connect

                database = f"{VARIABLES['name']}.db"
                database_exists = exists(database)
                connection = await connect(database)
                cursor = Cursor(connection, None, "?")
            if not database_exists:
                try:
                    for plugin in LOAD_ORDER:
                        sql_file = f"tables/{plugin}.sql"
                        if exists(sql_file):
                            for statement in filter(
                                lambda statement: statement not in ["", "\n", "\r\n"],
                                open(sql_file, "r").read().split(";"),
                            ):
                                await cursor.execute(statement)
                except:
                    pass
        bot.connection = connection
        bot.cursor = cursor
        bot.data = data
        bot.flat_file = flat_file
        bot.guilds_ = {}
        bot.lock = Lock()
        for plugin in LOAD_ORDER:
            if exists(f"plugins/{plugin}.py"):
                await bot.load_extension(f"plugins.{plugin}")
        await bot.start(VARIABLES["token"])


if platform == "win32":
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy

    set_event_loop_policy(WindowsSelectorEventLoopPolicy())

run(main())
