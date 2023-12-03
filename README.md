# The-Bard
A music Discord bot that plays from file attachments and custom download URLs instead of YouTube links.

# Setup:
Make sure that FFmpeg and MediaInfo are installed and in the path.

For Debian-based distros:
`sudo apt install ffmpeg mediainfo`

For Fedora-based distros:
`sudo dnf install ffmpeg mediainfo`

For macOS (using Homebrew):
`brew install ffmpeg mediainfo`

For macOS (using MacPorts):
`sudo port install ffmpeg mediainfo`

For Windows (using Chocolatey):
`choco install ffmpeg mediainfo-cli`

For Windows (using Scoop):
`scoop install main/ffmpeg main/mediainfo`

For Windows (Manual):
Download FFmpeg from https://ffmpeg.org/download.html#build-windows and add the `bin` subfolder to your `PATH` environment variable.
Download MediaInfo (CLI version) from https://mediaarea.net/en/MediaInfo/Download/Windows and add the folder to your `PATH` environment variable.

Also make sure to grab the following Python dependencies (see the command below):

`pip3 install requests PyYAML discord.py[voice]`

To run it, type the following in your operating system's CLI at the project's directory:

`python3 Main.py`

Make sure to add the bot token and user ID of the host user `Variables.yaml`. Use `+sync` to update the slash commands.
