import discord
import asyncio
from discord.ext import commands
from yt_dlp import YoutubeDL
import time

class music_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_embed = {}                             # temp variable for all servers for storing the next embeded message to be sent
        self.current_song = {}                              # stores the song currently playing in all servers
        self.music_queue = {}                               # stores the song queues of all servers
        self.server_status = {}                             # stores status flags of all servers, containing: is_playing, is_looping
        self.last_action = {}                               # stores last action (play / join) time and ctx for all servers
        self.YDL_OPTIONS = {
            "format": "bestaudio/best",
            "youtube_include_dash_manifest": False, 
            "extractor_args": {
                "youtube": {
                    "player_client": ["android_sdkless", "web_safari", "web"],
                    "skip": ["dash", "hls"],
                    "formats": "missing_pot"
                }
            },
            "cookies": "/yt_cookie.txt",
            "noplaylist": False,
            "default_search": "auto",
            "skip_download": True
        }
        self.FFMPEG_OPTIONS = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", 
            "options": "-vn"
        }

        self.timeout_interval = self.bot.loop.create_task(self.timeout_check())

    # checks for timeout for all servers every 60 seconds
    # disconnects the bot of the server for inactivity of 10 minutes
    async def timeout_check(self):
        while True:
            for server_id in list(self.last_action.keys()):
                if server_id not in self.last_action:
                    continue
                if (self.last_action[server_id]["time"] + 600 < time.time()):
                    if (server_id in self.server_status and self.server_status[server_id]["is_playing"] == True):
                        self.last_action[server_id]["time"] = time.time()
                    else:
                        voice_client = self.bot.get_guild(server_id).voice_client
                        ctx = self.last_action[server_id]["ctx"]
                        self.message_embed[server_id].description = "Disconnected due to inactivity"
                        await ctx.send(embed=self.message_embed[server_id])  
                        if (voice_client is not None):
                            voice_client.stop()
                            await voice_client.disconnect()
            await asyncio.sleep(60) 
                
    @commands.Cog.listener()
    async def on_ready(self):
        print("Loaded music_cog.py")
    
    # delete all states associated to the server when being disconnected from voice channel
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if (member == self.bot.user):
            if (before.channel is not None and after.channel is None):                 # check if the bot was disconnected from the voice channel
                server_id = before.channel.guild.id
                if (server_id in self.current_song):
                    del self.current_song[server_id]
                if (server_id in self.music_queue):
                    del self.music_queue[server_id]
                if (server_id in self.server_status):
                    del self.server_status[server_id]
                if (server_id in self.last_action):
                    del self.last_action[server_id]
                
    # search audio source from user input
    def search_yt(self, query):                              
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(query, download=False)
                entries = info.get("entries", [info])
            except Exception:
                return []
        songs = []
        for entry in entries:
            if ((not entry) or (not entry.get('url'))):
                continue
            songs.append({
                "source": entry["url"],
                "title": entry["title"],
                "yt_url": entry["webpage_url"]
            })
        return songs

    # play the next song in the queue when the current song is finished
    # play the current song when it is looping instead of the next song in the queue
    def play_next(self, vc, server_id):
        self.last_action[server_id]["time"] = time.time()
        if (self.server_status[server_id]["is_looping"] == True):
            self.server_status[server_id]["is_playing"] = True
            m_url = self.current_song[server_id][0]['source']
            vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next(vc, server_id))
        elif (len(self.music_queue[server_id]) > 0):                                              # play the next song in the queue when queue is not empty
            self.server_status[server_id]["is_playing"] = True
            m_url = self.music_queue[server_id][0][0]['source']
            self.message_embed[server_id] = discord.Embed()
            self.message_embed[server_id].description = f"Now playing: [{self.music_queue[server_id][0][0]['title']}]({self.music_queue[server_id][0][0]['yt_url']})"
            self.bot.loop.create_task(self.music_queue[server_id][0][2].send(embed=self.message_embed[server_id]))      # show the next song that is going to play
            self.current_song[server_id] = self.music_queue[server_id].pop(0)
            vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next(vc, server_id))
        else:
            self.server_status[server_id]["is_playing"] = False

    # start to play the song, usually when no song is playing currently
    async def play_music(self, vc, server_id):
        if (len(self.music_queue[server_id]) > 0):
            self.server_status[server_id]["is_playing"] = True
            m_url = self.music_queue[server_id][0][0]['source']
            self.message_embed[server_id] = discord.Embed()
            self.message_embed[server_id].description = f"Now playing: [{self.music_queue[server_id][0][0]['title']}]({self.music_queue[server_id][0][0]['yt_url']})"
            await self.music_queue[server_id][0][2].send(embed=self.message_embed[server_id])       # show the next song that is going to play
            self.current_song[server_id] = self.music_queue[server_id].pop(0)
            vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next(vc, server_id)) # initiate to play the next song when the current song is finished
        else:
            self.server_status[server_id]["is_playing"] = False

    # join the voice channel of the command sender
    @commands.command()
    async def join(self, ctx):                                          
        server_id = ctx.message.guild.id
        self.message_embed[server_id] = discord.Embed()
        self.last_action[server_id] = { "time": time.time(), "ctx": ctx }
        if ctx.author.voice is None:
            self.message_embed[server_id].description = "You are not in a voice channel."
            await ctx.send(embed=self.message_embed[server_id])
        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await voice_channel.connect()
        else:
            await ctx.voice_client.move_to(voice_channel)

    # play song in the voice channel of the command sender
    @commands.command()
    async def play(self, ctx, *args):
        query = " ".join(args)
        server_id = ctx.message.guild.id
        voice_channel = None
        self.message_embed[server_id] = discord.Embed()
        self.last_action[server_id] = { "time": time.time(), "ctx": ctx }
        if (self.server_status.get(server_id) == None):
            self.server_status[server_id] = { "is_playing": False, "is_looping": False }
        if (ctx.author.voice is None):                                                             # join the command sender's voice channel or ask the sender to join one
            self.message_embed[server_id].description = "Connect to a voice channel to play music"
            await ctx.send(embed=self.message_embed[server_id])
        elif (ctx.voice_client is None):
            await ctx.author.voice.channel.connect()
            voice_channel = ctx.voice_client.channel
        elif (ctx.author.voice.channel == ctx.voice_client.channel):
            voice_channel = ctx.voice_client.channel
        elif (self.server_status[server_id]["is_playing"] == True and ctx.author.voice.channel != ctx.voice_client.channel):
            self.message_embed[server_id].description = "You have to be in the same voice channel as the bot"
            await ctx.send(embed=self.message_embed[server_id])            
        else:
            await ctx.voice_client.disconnect()
            await ctx.author.voice.channel.connect()
            voice_channel = ctx.author.voice.channel
        if (server_id not in self.music_queue):
            self.music_queue[server_id] = []
        if (ctx.author.voice is not None and ctx.author.voice.channel == voice_channel):           # add the song to the queue and start playing
            if any(x in query for x in ['youtube.com/playlist', '&list=', 'playlist?list=']):
                self.message_embed[server_id].description = "Extracting playlist. Please wait..."
                await ctx.send(embed=self.message_embed[server_id]) 
            songs = self.search_yt(query)
            if (len(songs) == 0):
                self.message_embed[server_id].description = "Could not download the song. Try another keyword"
                await ctx.send(embed=self.message_embed[server_id])
            else:
                for song in songs:
                    self.music_queue[server_id].append([song, voice_channel, ctx.channel])
                if (len(songs) > 1 or (self.server_status[server_id]["is_playing"] == True and len(songs) == 1)):
                    if (len(songs) == 1):
                        self.message_embed[server_id].description = f"Added to the queue: [{songs[0]['title']}]({songs[0]['yt_url']})" 
                    else:
                        lines = [f"{i}. [{s['title']}]({s['yt_url']})" for i, s in enumerate(songs[:10], 1)]
                        if (len(songs) > 10):
                            lines.append(f"... and {len(songs) - 10} more")
                        self.message_embed[server_id].description = f"Added {len(songs)} songs to the queue:\n" + "\n".join(lines)
                    await ctx.send(embed=self.message_embed[server_id]) 
                if (self.server_status[server_id]["is_playing"] == False):
                    await self.play_music(ctx.voice_client, server_id)

    # show the song queue
    @commands.command()
    async def queue(self, ctx):
        retval = "Song queue:\n"
        server_id = ctx.message.guild.id
        if (server_id not in self.music_queue):
             self.message_embed[server_id].description = "No song in the queue"
        else:
            for i in range(0, len(self.music_queue[server_id])):
                retval += f"{str(i+1)}. [{self.music_queue[server_id][i][0]['title']}]({self.music_queue[server_id][i][0]['yt_url']})\n"
            if retval != "Song queue:\n":
                self.message_embed[server_id].description = retval
            else:
                self.message_embed[server_id].description = "No song in the queue"
        await ctx.send(embed=self.message_embed[server_id])

    # remove songs in the song queue
    @commands.command()                                                                                 
    async def remove(self, ctx, q_num):
        server_id = ctx.message.guild.id
        if (q_num == 'all'):                                                                                    # remove all the songs
            self.message_embed[server_id].description = "All queued songs have been remove"
            self.music_queue[server_id] = []    
        elif (q_num.isdigit() == False or int(q_num) < 1 or int(q_num) > (len(self.music_queue[server_id]))):   # report for wrong input
            self.message_embed[server_id].description = "Please enter a correct queue number"
        else:
            self.message_embed[server_id].description = f"Song removed: [{self.music_queue[server_id][int(q_num)-1][0]['title']}]({self.music_queue[server_id][int(q_num)-1][0]['yt_url']})"           
            self.music_queue[server_id].pop(int(q_num)-1)                                                       # remove a specific song
        await ctx.send(embed=self.message_embed[server_id])   
    
    # skip the current song and initiate to play the next song
    @commands.command()
    async def skip(self, ctx):
        server_id = ctx.message.guild.id
        self.message_embed[server_id] = discord.Embed()
        if (ctx.voice_client != None):
            if (self.server_status[server_id]["is_looping"] == True):
                self.server_status[server_id]["is_looping"] = False
                self.message_embed[server_id].description = "Loop is disabled"
                await ctx.send(embed=self.message_embed[server_id])
            self.message_embed[server_id].description = "Song skipped"   
            self.server_status[server_id]["is_playing"] = False
            await ctx.send(embed=self.message_embed[server_id])
            ctx.voice_client.stop()
    
    # pause the current song
    @commands.command()       
    async def pause(self, ctx):
        server_id = ctx.message.guild.id
        self.message_embed[server_id] = discord.Embed()
        if (self.server_status.get(server_id) == None or self.server_status[server_id]["is_playing"] == False):
            self.message_embed[server_id].description = "No song is playing now"    
        elif (ctx.voice_client.is_paused() == True):
            self.message_embed[server_id].description = "Song is already paused"
        else:
            ctx.voice_client.pause()
            self.message_embed[server_id].description = "Song paused"
        await ctx.send(embed=self.message_embed[server_id])
    
    # resume the current song
    @commands.command()                                         
    async def resume(self, ctx):
        server_id = ctx.message.guild.id
        self.message_embed[server_id] = discord.Embed()
        if (self.server_status.get(server_id) == None or self.server_status[server_id]["is_playing"] == False):
            self.message_embed[server_id].description = "No song is playing now"
        elif (ctx.voice_client.is_paused() == False):
            self.message_embed[server_id].description = "Song is already playing"
        else:
            ctx.voice_client.resume()
            self.message_embed[server_id].description = "Song resumed"
        await ctx.send(embed=self.message_embed[server_id])
    
    # loop the current playing song
    @commands.command()                                             
    async def loop(self, ctx):
        server_id = ctx.message.guild.id
        self.message_embed[server_id] = discord.Embed()
        if (self.server_status[server_id]["is_looping"] == False):
            self.message_embed[server_id].description = "Loop is enabled"
        else:
            self.message_embed[server_id].description = "Loop is disabled"
        self.server_status[server_id]["is_looping"] = not(self.server_status[server_id]["is_looping"])
        await ctx.send(embed=self.message_embed[server_id])
    
    # disconnect the bot
    @commands.command()                                             
    async def disconnect(self, ctx):
        if (ctx.voice_client is not None):
            ctx.voice_client.stop()
            await ctx.voice_client.disconnect()

    # warning: this function will expose your ip address, only use it in trusted servers
    # generate a downloadable audio file source
    @commands.command()
    async def download(self, ctx, *args):
        server_id = ctx.message.guild.id                                                           
        query = " ".join(args)
        info = self.search_yt(query)
        self.message_embed[server_id] = discord.Embed()
        self.message_embed[server_id].description = f"Song: {info['title']}. [Click me to download]({info['source']})\nType !downloadhelp to check how to download the song."
        await ctx.send(embed=self.message_embed[server_id])

    # guide to download the audio file using the 'download' command
    @commands.command()
    async def downloadhelp(self, ctx):
        server_id = ctx.message.guild.id
        self.message_embed[server_id] = discord.Embed()
        self.message_embed[server_id].description = "Steps to download audio:\nStep 1: Type !download <song> to generate a hyperlink\nStep 2: Click the hyperlink and open the audio source in browser\nStep 3: Press Ctrl+S\nStep 4: Change the file extension to .mp3 and the file type to \"All Files\"\nStep 5: Click Save"
        await ctx.send(embed=self.message_embed[server_id])

async def setup(bot):
    await bot.add_cog(music_cog(bot))