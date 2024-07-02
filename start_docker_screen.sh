#!/bin/bash
cd "${0%/*}"
./start_docker.sh
screen -dmS the-bard docker attach the-bard
