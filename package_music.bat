@echo off
pushd "%~dp0"
mkdir music^
    music\languages^
    music\languages\fragments^
    music\plugins^
    music\tables^
    music\transfers^
    music\variables
copy languages\fragments\*_music.yaml music\languages\fragments
copy playback.py music
copy playlists.py music
copy plugins\music.py music\plugins
copy tables\music.sql music\tables
copy transfers\*_music.py music\transfers
copy variables\music.yaml music\variables
copy *_music.* music
cd music
7z a ..\music.zip .\*
cd ..
rmdir /s /q music
popd
