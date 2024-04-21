# The-Bard
A music Discord bot that plays from file attachments and custom download URLs instead of YouTube links.

## Setup
Make sure that FFmpeg and MediaInfo (not needed for Windows) are installed and in the path.

### For Arch-based Linux distributions:
```
pacman -S ffmpeg mediainfo
```

### For Debian-based Linux distributions:
```
apt install ffmpeg mediainfo
```

### For Fedora-based Linux distributions:
```
dnf install ffmpeg mediainfo
```

### For macOS (Homebrew):
```
brew install ffmpeg mediainfo
```

### For macOS (MacPorts):
```
port install ffmpeg mediainfo
```

### For Windows (Chocolatey):
```
choco install ffmpeg
```

### For Windows (Scoop):
```
scoop install ffmpeg
```

### For Windows (Manual):
+ Download FFmpeg from https://ffmpeg.org/download.html#build-windows and copy the contents of the `bin` folder into the project's directory.

---

Also make sure to grab the Python dependencies by typing the following in your operating system's CLI at the project's directory:
```
pip3 install -r requirements.txt
```

## Usage
To run it, type the following in your operating system's CLI at the project's directory:
```
python3 Main.py
```

Make sure to add the bot token and ID of the host user to `Variables.yaml`. The host user then needs to type `+sync_commands` to make the slash commands show up and update.

Also make sure to type `+sync_guilds` and `+sync_users` after launching so that any guilds that added or removed this bot
and/or any users that joined or left any guilds with this bot during downtime can be properly added to or removed from storage.

[![Preview]
(https://img.youtube.com/vi/5fFW8cCbjbc/maxresdefault.jpg)]
(https://www.youtube.com/watch?v=5fFW8cCbjbc)

