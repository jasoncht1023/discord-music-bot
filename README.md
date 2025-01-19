# Discord Music Bot

A discord music bot to stream youtube audio in the discord servers. Host your own discord music bot in your servers. Developed using Python.

### Supported functions / commands:
- Stream youtube audio in your servers
	- !play, !join, !queue, !remove, !skip, !pause, !resume, !loop, !disconnect
- Download audio file from youtube
	- !download, !downloadhelp

### Hosting:
- Prerequisites:
	- [Python](https://www.python.org/downloads/)
	- [FFmpeg](http://ffmpeg.org/download.html)
	- [discord.py](https://discordpy.readthedocs.io/en/stable/) (Python library)
	- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Python library)
- Setup:
	- Clone or download the repository
	- Create a "token.txt" file in the root folder and paste your discord bot token in the file
	- Export your YouTube login cookies from chrome in Netscape format, rename it to `yt_cookies.txt` and paste it in the root folder [(Reference)](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)
	- Run "python musicbot.py" in the terminal