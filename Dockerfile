FROM python:3.11-slim-bullseye
RUN apt update
RUN apt install -y ffmpeg mediainfo
RUN pip install requests PyYAML discord.py[voice]
CMD ["/bin/sh", "/The-Bard/The-Bard.sh"]
