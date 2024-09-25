@echo off
pushd "%~dp0"
docker build -t the-bard .
docker run -it --name the-bard -v "%cd%":/Bard the-bard
popd
