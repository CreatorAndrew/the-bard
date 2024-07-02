FROM python:3.11-slim-bullseye
SHELL ["/bin/bash", "-c"]
RUN apt update
RUN apt install -y build-essential ffmpeg libpq5 mediainfo postgresql
COPY requirements.txt /tmp
RUN python -m venv /Bard/.venv
RUN source /Bard/.venv/bin/activate
RUN python -m pip install -r /tmp/requirements.txt
CMD ["/bin/bash", "/Bard/bard.sh"]
