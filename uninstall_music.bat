@echo off
pushd "%~dp0"
del languages\fragments\*_music.yaml^
    playback.py^
    playlists.py^
    plugins\music.py^
    tables\music.sql^
    transfers\*_music.py^
    variables\music.yaml
popd
