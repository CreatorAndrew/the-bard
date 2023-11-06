FROM python:3.8.18-slim-bullseye
COPY . .
RUN apt update
RUN apt install -y ffmpeg mediainfo
RUN pip install requests PyYAML discord.py[voice]
CMD ["python", "./Main.py"]
