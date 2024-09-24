create table guilds(
    guild_id bigint not null,
    guild_lang text not null,
    primary key (guild_id)
);
create table users(user_id bigint not null, primary key (user_id));
create table guild_users(
    guild_id bigint not null,
    user_id bigint not null,
    primary key (guild_id, user_id),
    foreign key (guild_id) references guilds(guild_id) on delete cascade,
    foreign key (user_id) references users(user_id) on delete cascade
);
