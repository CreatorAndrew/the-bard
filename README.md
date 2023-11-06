# The-Bard
A music Discord bot that plays from file attachments and custom download URLs instead of YouTube links.

Type `+help` to see a list of commands.

# Setup:

Make sure that FFmpeg and MediaInfo are installed and in the path.

For Debian-based distros:
`sudo apt install ffmpeg mediainfo`

For Fedora-based distros:
`sudo dnf install ffmpeg mediainfo`

For macOS (using Homebrew)
`brew install ffmpeg mediainfo`

For macOS (using MacPorts)
`sudo port install ffmpeg mediainfo`

For Windows:
Download FFmpeg from https://ffmpeg.org/download.html#build-windows and add the `bin` directory to your `PATH` environment variable.
Download and install MediaInfo from https://mediaarea.net/en/MediaInfo/Download/Windows

Also make sure to grab the following Python dependencies (see the command below):

`pip3 install requests PyYAML pymediainfo discord.py[voice]`

To run it, type the following in Command Prompt or Terminal at the project's directory:

`python3 Main.py`
