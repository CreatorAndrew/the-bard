FROM python:3.8-slim-bullseye
RUN apt update
RUN apt install -y ffmpeg mediainfo
RUN pip install discord.py[voice] PyYAML requests
CMD ["/bin/sh", "/Bard/Bard.sh"]
