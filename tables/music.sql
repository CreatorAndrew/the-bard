create table guilds_music(
    guild_id bigint not null,
    working_thread_id bigint null,
    keep_in_voice boolean not null,
    repeat_queue boolean not null,
    primary key (guild_id),
    foreign key (guild_id) references guilds(guild_id) on delete cascade
);
create table playlists(
    pl_id bigint not null,
    pl_name text not null,
    guild_id bigint not null,
    guild_pl_id bigint not null,
    primary key (pl_id),
    foreign key (guild_id) references guilds_music(guild_id) on delete cascade
);
create table songs(
    song_id bigint not null,
    song_name text not null,
    song_duration float not null,
    guild_id bigint not null,
    channel_id bigint not null,
    message_id bigint not null,
    attachment_index bigint not null,
    primary key (song_id)
);
create table pl_songs(
    song_id bigint not null,
    song_name text not null,
    song_url text null,
    pl_id bigint not null,
    pl_song_id bigint not null,
    primary key (song_id, pl_id),
    foreign key (song_id) references songs(song_id),
    foreign key (pl_id) references playlists(pl_id) on delete cascade
);
