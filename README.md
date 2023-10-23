# The-Bard
A music Discord bot that plays from file attachments and custom download URLs instead of YouTube links.

Type `+help` to see a list of commands.

# Setup:

Make sure that FFmpeg is installed and is in the path.

For Debian-based distros:
`sudo apt install ffmpeg`

For Fedora-based distros:
`sudo dnf install ffmpeg`

For macOS (using Homebrew)
`brew install ffmpeg`

For macOS (using MacPorts)
`sudo port install ffmpeg`

For Windows:
Download from https://ffmpeg.org/download.html#build-windows and add the `bin` directory to your `PATH` environment variable.

Also make sure to grab the following Python dependencies (see the command below):

`pip3 install requests PyYAML discord.py[voice]`

To run it, type the following in Command Prompt or Terminal at the project's directory:

`python3 Main.py`
