#!/bin/bash
cd "${0%/*}"
source .venv/bin/activate
screen -dmS the-bard ./start.sh
