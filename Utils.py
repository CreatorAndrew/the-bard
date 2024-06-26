import os
import yaml
import discord
from discord import app_commands

language_directory = "Languages"
variables = yaml.safe_load(open("Variables.yaml", "r"))

class CommandTranslator(app_commands.Translator):
    async def translate(self, string: app_commands.locale_str, locale: discord.Locale, context: app_commands.TranslationContext) -> "str | None":
        try:
            if os.path.exists(f"{language_directory}/{locale.name}.yaml"):
                return yaml.safe_load(open(f"{language_directory}/{locale.name}.yaml", "r"))["strings"][str(string)]
            return None
        except: return None

class Cursor:
    def __init__(self, connection, cursor, integer_data_type, placeholder):
        self.connection = connection
        self.cursor = cursor
        self.integer_data_type = integer_data_type
        self.placeholder = placeholder

    async def execute(self, statement, args=tuple()):
        cursor = await self.connection.execute(statement.replace("integer", self.integer_data_type).replace("?", self.placeholder), args)
        if self.connection != self.cursor: self.cursor = cursor

    async def fetchall(self): return await self.cursor.fetchall()

    async def fetchone(self): return await self.cursor.fetchone()

async def get_file_name(file):
    try: return file[file.rindex("/") + 1:file.rindex("?")]
    except: return file[file.rindex("/") + 1:]

async def page_selector(context, strings, pages, index, message=None):
    previous_button = discord.ui.Button(label="<", disabled=index == 0, style=discord.ButtonStyle.primary)
    page_input_button = discord.ui.Button(label=f"{str(index + 1)}/{len(pages)}", disabled=len(pages) == 1)
    next_button = discord.ui.Button(label=">", disabled=index == len(pages) - 1, style=discord.ButtonStyle.primary)
    async def previous_callback(context):
        await context.response.defer()
        await page_selector(context, strings, pages, index - 1, message)
    async def page_input_callback(context):
        page_input = discord.ui.TextInput(label=strings["page"])
        modal = discord.ui.Modal(title=strings["page_selector_title"])
        modal.add_item(page_input)
        async def submit(context):
            await context.response.defer()
            await page_selector(context,
                                strings,
                                pages,
                                int(page_input.value) - 1 if 0 < int(page_input.value) <= len(pages) else index,
                                message)
        modal.on_submit = submit
        await context.response.send_modal(modal)
    async def next_callback(context):
        await context.response.defer()
        await page_selector(context, strings, pages, index + 1, message)
    next_button.callback = next_callback
    page_input_button.callback = page_input_callback
    previous_button.callback = previous_callback
    view = discord.ui.View()
    view.add_item(previous_button)
    view.add_item(page_input_button)
    view.add_item(next_button)
    if message is None: message = await context.followup.send("...", ephemeral=True)
    await context.followup.edit_message(message.id, content=pages[index], view=view)

async def polished_message(message, replacements):
    for placeholder, replacement in replacements.items(): message = message.replace("%{" + placeholder + "}", str(replacement))
    return message

async def polished_url(file, name): return f"[{name}](<{file}>)"
