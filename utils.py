from os.path import exists
from yaml import safe_load as load
from discord import ButtonStyle, Locale
from discord.app_commands import locale_str, TranslationContext, Translator
from discord.ui import Button, Modal, TextInput, View

LANGUAGE_DIRECTORY = "languages"
load_order = list(
    map(
        lambda line: line.replace("\r\n", "").replace("\n", ""),
        open("load_order.txt", "r").readlines(),
    )
)
try:
    variables = load(open("variables.yaml", "r"))
    credentials = f"""
        dbname={variables["postgresql_credentials"]["user"]}
        user={variables["postgresql_credentials"]["user"]}
        password={variables["postgresql_credentials"]["password"]}
        {"" if variables["postgresql_credentials"]["host"] is None else f"host={variables['postgresql_credentials']['host']}"}
        {"" if variables["postgresql_credentials"]["port"] is None else f"port={variables['postgresql_credentials']['port']}"}
    """
except:
    variables = {}
    credentials = ""


class CommandTranslator(Translator):
    async def translate(
        self, string: locale_str, locale: Locale, context: TranslationContext
    ) -> "str | None":
        try:
            if exists(f"{LANGUAGE_DIRECTORY}/{locale.name}.yaml"):
                return load(open(f"{LANGUAGE_DIRECTORY}/{locale.name}.yaml", "r"))[
                    "strings"
                ][str(string)]
            return None
        except:
            return None


class Cursor:
    def __init__(self, connection, cursor, placeholder):
        self.connection = connection
        self.cursor = cursor
        self.placeholder = placeholder

    async def execute(self, statement, args=tuple()):
        cursor = await self.connection.execute(
            statement.replace("?", self.placeholder),
            args,
        )
        if self.connection != self.cursor:
            self.cursor = cursor

    async def fetchall(self):
        return await self.cursor.fetchall()

    async def fetchone(self):
        return await self.cursor.fetchone()


def get_file_name(file):
    try:
        return file[file.rindex("/") + 1 : file.rindex("?")]
    except:
        return file[file.rindex("/") + 1 :]


async def page_selector(context, strings, pages, index, message=None):
    previous_button = Button(label="<", disabled=index == 0, style=ButtonStyle.primary)
    page_input_button = Button(
        label=f"{str(index + 1)}/{len(pages)}", disabled=len(pages) == 1
    )
    next_button = Button(
        label=">", disabled=index == len(pages) - 1, style=ButtonStyle.primary
    )

    async def previous_callback(context):
        await context.response.defer()
        await page_selector(context, strings, pages, index - 1, message)

    async def page_input_callback(context):
        page_input = TextInput(label=strings["page"])
        modal = Modal(title=strings["page_selector_title"])
        modal.add_item(page_input)

        async def submit(context):
            await context.response.defer()
            await page_selector(
                context,
                strings,
                pages,
                (
                    int(page_input.value) - 1
                    if 0 < int(page_input.value) <= len(pages)
                    else index
                ),
                message,
            )

        modal.on_submit = submit
        await context.response.send_modal(modal)

    async def next_callback(context):
        await context.response.defer()
        await page_selector(context, strings, pages, index + 1, message)

    next_button.callback = next_callback
    page_input_button.callback = page_input_callback
    previous_button.callback = previous_callback
    view = View()
    view.add_item(previous_button)
    view.add_item(page_input_button)
    view.add_item(next_button)
    if message is None:
        message = await context.followup.send("...", ephemeral=True)
    await context.followup.edit_message(message.id, content=pages[index], view=view)


def polished_message(message, replacements):
    for placeholder, replacement in replacements.items():
        message = message.replace("%{" + placeholder + "}", str(replacement))
    return message


def polished_url(file, name):
    return f"[{name}](<{file}>)"
