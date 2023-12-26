#!/bin/sh
cd "${0%/*}"
./DockerStart.sh
screen -dmS the-bard docker attach the-bard
