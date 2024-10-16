#!/bin/bash
cd "${0%/*}"
mkdir music\
    music/languages\
    music/languages/fragments\
    music/plugins\
    music/tables\
    music/transfers\
    music/variables
cp languages/fragments/*_music.yaml music/languages/fragments
cp playback.py music
cp playlists.py music
cp plugins/music.py music/plugins
cp tables/music.sql music/tables
cp transfers/*_music.py music/transfers
cp variables/music.yaml music/variables
cp *_music.* music
cd music
7z a ../music.zip ./*
cd ..
rm -rf music
