from typing import List, Literal
from yaml import safe_dump as dump
from discord import Attachment, Interaction, Message, RawThreadUpdateEvent
from discord.app_commands import Choice, command, ContextMenu, describe
from discord.ext.commands import Cog
from pymediainfo import MediaInfo
from playback import (
    disconnect_when_alone,
    dismiss_command,
    forward_command,
    insert_command,
    insert_song,
    jump_command,
    jump_to,
    keep_command,
    loop_command,
    move_command,
    pause_command,
    play_command,
    play_song,
    previous_command,
    queue_command,
    recruit_command,
    remove_command,
    remove_song,
    rename_command,
    rewind_command,
    shuffle_command,
    skip_command,
    song_autocompletion,
    stop_command,
    stop_music,
    volume_command,
    what_command,
    when_command,
)
from playlists import (
    playlist_add_files,
    playlist_autocompletion,
    playlist_command,
    playlist_guild_autocompletion,
    playlist_song_autocompletion,
    playlists_command,
    renew_attachment,
    renew_attachment_from_message,
    working_thread_autocompletion,
    working_thread_command,
)
from utils import get_filename, VARIABLES


class Music(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.connection = bot.connection
        self.cursor = bot.cursor
        self.data = bot.data
        self.flat_file = bot.flat_file
        self.guilds = bot.guilds_
        self.init_guilds(bot.music_init_guilds)
        self.lock = bot.lock
        self.messages = {}
        self.playlist_add_files_context_menu = ContextMenu(
            name="playlist_add_files_context_menu", callback=self.playlist_add_files
        )
        self.use_lavalink = bot.use_lavalink
        bot.tree.add_command(self.playlist_add_files_context_menu)

    def init_guilds(self, guilds):
        if VARIABLES["storage"] == "yaml":
            guilds = self.data["guilds"]
            id = "id"
            keep = "keep"
            repeat = "repeat"
        else:
            id = 0
            keep = 1
            repeat = 2
        for guild in guilds:
            self.guilds[str(guild[id])] = {
                **self.guilds[str(guild[id])],
                "connected": False,
                "index": 0,
                "keep": guild[keep],
                "queue": [],
                "repeat": guild[repeat],
                "time": 0.0,
                "volume": 1.0,
            }

    def get_metadata(self, file, url):
        duration = 0.0
        for track in MediaInfo.parse(file).tracks:
            try:
                if track.to_data()["track_type"] == "General":
                    name = track.to_data()["title"]
            except:
                try:
                    name = track.to_data()["track_name"]
                except:
                    name = get_filename(url).replace("_", " ")
                    try:
                        name = name[: name.rindex(".")]
                    except:
                        pass
            try:
                duration = float(track.to_data()["duration"]) / 1000
            except:
                pass
        return {"name": name, "duration": duration}

    @Cog.listener("on_ready")
    async def create_node(self):
        if self.use_lavalink:
            import pomice

            if VARIABLES["lavalink_credentials"]["host"] is None:
                VARIABLES["lavalink_credentials"]["host"] = "127.0.0.1"
            if VARIABLES["lavalink_credentials"]["port"] is None:
                VARIABLES["lavalink_credentials"]["port"] = 2333

            await pomice.NodePool.create_node(
                bot=self.bot,
                host=VARIABLES["lavalink_credentials"]["host"],
                port=VARIABLES["lavalink_credentials"]["port"],
                password=VARIABLES["lavalink_credentials"]["password"],
                identifier="main",
            )

    @Cog.listener("on_main_add_guild")
    async def add_guild(self, guild):
        if VARIABLES["storage"] == "yaml":
            await self.lock.acquire()
        init_guild = False
        keep = False
        repeat = False
        if VARIABLES["storage"] == "yaml":
            for guild_searched in self.data["guilds"]:
                if guild_searched["id"] == guild.id:
                    try:
                        assert not any(
                            key
                            for key in guild_searched.keys()
                            if key in ["keep", "playlists", "repeat"]
                        )
                        guild_searched["keep"] = keep
                        guild_searched["playlists"] = []
                        guild_searched["repeat"] = repeat
                        dump(self.data, open(self.flat_file, "w"), indent=4)
                        init_guild = True
                    except:
                        pass
                    break
        else:
            try:
                await self.cursor.execute(
                    "insert into guilds_music values(?, ?, ?, ?)",
                    (guild.id, None, keep, repeat),
                )
                init_guild = True
            except:
                pass
        if init_guild:
            self.guilds[str(guild.id)] = {
                **self.guilds[str(guild.id)],
                "connected": False,
                "index": 0,
                "keep": keep,
                "queue": [],
                "repeat": repeat,
                "time": 0.0,
                "volume": 1.0,
            }
        if VARIABLES["storage"] == "yaml":
            self.lock.release()

    @Cog.listener("on_main_remove_guild_from_database")
    async def remove_songs_not_in_playlists(self):
        await self.cursor.execute(
            "delete from songs where song_id not in (select song_id from pl_songs)"
        )

    @command(description="playlists_command_desc")
    @describe(from_guild="from_guild_desc")
    @describe(transfer="transfer_desc")
    @describe(add="add_desc")
    @describe(clone="clone_desc")
    @describe(into="into_desc")
    @describe(move="move_playlist_desc")
    @describe(rename="rename_desc")
    @describe(remove="remove_desc")
    @describe(load="load_desc")
    @describe(list_songs="list_desc")
    @describe(new_name="new_name_desc")
    @describe(new_index="new_index_desc")
    async def playlists_command(
        self,
        context: Interaction,
        from_guild: str = None,
        transfer: int = None,
        add: str = None,
        clone: int = None,
        into: int = None,
        move: int = None,
        rename: int = None,
        remove: int = None,
        load: int = None,
        list_songs: int = None,
        new_name: str = None,
        new_index: int = None,
    ):
        await playlists_command(
            self,
            context,
            from_guild,
            transfer,
            add,
            clone,
            into,
            move,
            rename,
            remove,
            load,
            list_songs,
            new_name,
            new_index,
        )

    @command(description="playlist_command_desc")
    @describe(select="select_desc")
    @describe(file="file_desc")
    @describe(song_url="song_url_desc")
    @describe(move="move_song_desc")
    @describe(rename="rename_desc")
    @describe(remove="remove_desc")
    @describe(load="load_desc")
    @describe(new_name="new_name_desc")
    @describe(new_index="new_index_desc")
    async def playlist_command(
        self,
        context: Interaction,
        select: int,
        file: Attachment = None,
        song_url: str = None,
        move: int = None,
        rename: int = None,
        remove: int = None,
        load: int = None,
        new_name: str = None,
        new_index: int = None,
    ):
        await playlist_command(
            self,
            context,
            select,
            file,
            song_url,
            move,
            rename,
            remove,
            load,
            new_name,
            new_index,
        )

    @playlists_command.autocomplete("from_guild")
    async def playlist_guild_autocompletion(
        self, context: Interaction, current: str
    ) -> List[Choice[str]]:
        return await playlist_guild_autocompletion(self, context, current)

    @playlists_command.autocomplete("transfer")
    @playlists_command.autocomplete("clone")
    @playlists_command.autocomplete("into")
    @playlists_command.autocomplete("move")
    @playlists_command.autocomplete("rename")
    @playlists_command.autocomplete("remove")
    @playlists_command.autocomplete("load")
    @playlists_command.autocomplete("list_songs")
    @playlist_command.autocomplete("select")
    async def playlist_autocompletion(
        self, context: Interaction, current: str
    ) -> List[Choice[int]]:
        return await playlist_autocompletion(self, context, current)

    @playlist_command.autocomplete("move")
    @playlist_command.autocomplete("rename")
    @playlist_command.autocomplete("remove")
    @playlist_command.autocomplete("load")
    async def playlist_song_autocompletion(
        self, context: Interaction, current: str
    ) -> List[Choice[int]]:
        return await playlist_song_autocompletion(self, context, current)

    async def playlist_add_files(self, context: Interaction, message_regarded: Message):
        await playlist_add_files(self, context, message_regarded)

    async def renew_attachment(self, guild_id, channel_id, url, song_id=None):
        await renew_attachment(self, guild_id, channel_id, url, song_id)

    @Cog.listener("on_message")
    async def renew_attachment_from_message(self, message: Message):
        await renew_attachment_from_message(self, message)

    @command(description="working_thread_command_desc")
    async def working_thread_command(self, context: Interaction, set: str = None):
        await working_thread_command(self, context, set)

    @working_thread_command.autocomplete("set")
    async def working_thread_autocompletion(
        self, context: Interaction, current: str
    ) -> List[Choice[str]]:
        return await working_thread_autocompletion(context, current)

    @Cog.listener("on_raw_thread_update")
    async def keep_working_thread_open(self, payload: RawThreadUpdateEvent):
        try:
            if (
                payload.thread_id
                == (
                    next(
                        guild_searched["working_thread_id"]
                        for guild_searched in self.data["guilds"]
                        if guild_searched["id"] == payload.guild_id
                    )
                    if VARIABLES["storage"] == "yaml"
                    else (
                        await self.cursor.execute_fetchone(
                            "select working_thread_id from guilds_music where guild_id = ?",
                            (payload.guild_id,),
                        )
                    )[0]
                )
                and payload.thread.archived
            ):
                await payload.thread.edit(archived=False)
        except:
            pass

    @command(description="play_command_desc")
    async def play_command(
        self,
        context: Interaction,
        file: Attachment = None,
        song_url: str = None,
        new_name: str = None,
    ):
        await play_command(self, context, file, song_url, new_name)

    async def play_song(self, context, url=None, name=None, playlist=None):
        await play_song(self, context, url, name, playlist)

    @command(description="insert_command_desc")
    async def insert_command(
        self,
        context: Interaction,
        file: Attachment = None,
        song_url: str = None,
        new_name: str = None,
        new_index: int = None,
    ):
        await insert_command(self, context, file, song_url, new_name, new_index)

    async def insert_song(
        self, context, url, name, index, time="0", duration=None, silent=False
    ):
        await insert_song(self, context, url, name, index, time, duration, silent)

    @command(description="move_command_desc")
    async def move_command(self, context: Interaction, song_index: int, new_index: int):
        await move_command(self, context, song_index, new_index)

    @command(description="rename_command_desc")
    async def rename_command(
        self, context: Interaction, song_index: int, new_name: str
    ):
        await rename_command(self, context, song_index, new_name)

    @command(description="remove_command_desc")
    async def remove_command(self, context: Interaction, song_index: int):
        await remove_command(self, context, song_index)

    async def remove_song(self, context, index, silent=False):
        await remove_song(self, context, index, silent)

    @move_command.autocomplete("song_index")
    @rename_command.autocomplete("song_index")
    @remove_command.autocomplete("song_index")
    async def song_autocompletion(
        self, context: Interaction, current: str
    ) -> List[Choice[int]]:
        return await song_autocompletion(self, context, current)

    @command(description="skip_command_desc")
    async def skip_command(self, context: Interaction, by: int = 1, to: int = None):
        await skip_command(self, context, by, to)

    @command(description="previous_command_desc")
    async def previous_command(self, context: Interaction, by: int = 1):
        await previous_command(self, context, by)

    @command(description="stop_command_desc")
    async def stop_command(self, context: Interaction):
        await stop_command(self, context)

    async def stop_music(self, context, leave=False, guild=None):
        await stop_music(self, context, leave, guild)

    @command(description="pause_command_desc")
    async def pause_command(self, context: Interaction):
        await pause_command(self, context)

    @command(description="jump_command_desc")
    async def jump_command(self, context: Interaction, time: str):
        await jump_command(self, context, time)

    async def jump_to(self, context, time):
        await jump_to(self, context, time)

    @command(description="forward_command_desc")
    async def forward_command(self, context: Interaction, time: str):
        await forward_command(self, context, time)

    @command(description="rewind_command_desc")
    async def rewind_command(self, context: Interaction, time: str):
        await rewind_command(self, context, time)

    @command(description="when_command_desc")
    async def when_command(self, context: Interaction):
        await when_command(self, context)

    @command(description="shuffle_command_desc")
    async def shuffle_command(self, context: Interaction, restart: Literal[0, 1] = 1):
        await shuffle_command(self, context, restart)

    @command(description="queue_command_desc")
    async def queue_command(self, context: Interaction):
        await queue_command(self, context)

    @command(description="what_command_desc")
    async def what_command(self, context: Interaction):
        await what_command(self, context)

    @command(description="volume_command_desc")
    async def volume_command(self, context: Interaction, set: str = None):
        await volume_command(self, context, set)

    @command(description="recruit_command_desc")
    async def recruit_command(self, context: Interaction):
        await recruit_command(self, context)

    @command(description="dismiss_command_desc")
    async def dismiss_command(self, context: Interaction):
        await dismiss_command(self, context)

    @Cog.listener("on_voice_state_update")
    async def disconnect_when_alone(self, member, before, after):
        await disconnect_when_alone(self, member, before, after)

    @command(description="keep_command_desc")
    async def keep_command(self, context: Interaction, set: Literal[0, 1] = None):
        await keep_command(self, context, set)

    @command(description="loop_command_desc")
    async def loop_command(self, context: Interaction, set: Literal[0, 1] = None):
        await loop_command(self, context, set)


async def setup(bot):
    bot.music_init_guilds = None
    bot.use_lavalink = VARIABLES["multimedia_backend"] == "lavalink"
    if VARIABLES["storage"] != "yaml":
        bot.music_init_guilds = await bot.cursor.execute_fetchall(
            "select guild_id, keep_in_voice, repeat_queue from guilds_music"
        )
    await bot.add_cog(Music(bot))
