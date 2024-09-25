#!/bin/bash
cd "${0%/*}"
rm languages/fragments/*_music.yaml\
    playback.py\
    playlists.py\
    plugins/music.py\
    tables/music.sql\
    transfers/*_music.py\
    variables/music.yaml
