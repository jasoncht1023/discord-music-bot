import discord
import asyncio
from discord.ext import commands
from yt_dlp import YoutubeDL
# ported to yt_dlp from youtube_dl

class music_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_embed = {}                             #temp variable for all servers for storing the next embeded message to be sent
        self.current_song = {}                              #stores the song currently playing in all servers
        self.music_queue = {}                               #stores the song queues of all servers
        self.server_status = {}                             #stores status flags of all servers, containing: queue_created, is_playing, is_looping
        self.YDL_OPTIONS = {'formats': 'bestaudio', 'youtube_include_dash_manifest': False, 'extractor_args': {'youtube': {'player_client': ['ios']}}}
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("Loaded music_cog.py")

    def search_yt(self, item):                              #search audio source from user input
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                if (item.startswith("https://")):
                    if (item.find("watch?v=") != -1):
                        item = "https://www.youtube.com/" + item[item.rfind('/')+1:item.rfind('/')+20]
                    else:
                        item = "https://www.youtube.com/watch?v=" + item[item.rfind('/')+1:item.rfind('/')+12]
                info = ydl.extract_info("ytsearch:{}".format(item), download=False)['entries'][0]
            except Exception:
                return False
        for entry in reversed(info['formats']):
            if (entry['vcodec'] == 'none'):
                return {'source': entry['url'], 'title': info['title'], 'yt_url': info['webpage_url']}
        return False

    def play_next(self, vc, server_id):                                                           #play the next song in the queue when the current song is finished
        if (self.server_status[server_id]["is_looping"] == True):                                 #play the current song when it is looping instead of the next song in the queue
            self.server_status[server_id]["is_playing"] = True
            m_url = self.current_song[server_id][0]['source']
            vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next(vc, server_id))
        elif (len(self.music_queue[server_id]) > 0):                                              #play the next song in the queue when queue is not empty
            self.server_status[server_id]["is_playing"] = True
            m_url = self.music_queue[server_id][0][0]['source']
            self.message_embed[server_id] = discord.Embed()
            self.message_embed[server_id].description = f"Now playing: [{self.music_queue[server_id][0][0]['title']}]({self.music_queue[server_id][0][0]['yt_url']})"
            self.bot.loop.create_task(self.music_queue[server_id][0][2].send(embed=self.message_embed[server_id])) #show the next song that is going to play
            self.current_song[server_id] = self.music_queue[server_id].pop(0)
            vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next(vc, server_id))
        else:
            self.server_status[server_id]["is_playing"] = False

    async def play_music(self, vc, server_id):                                                     #start to play the song, usually when no song is playing currently
        if (len(self.music_queue[server_id]) > 0):
            self.server_status[server_id]["is_playing"] = True
            m_url = self.music_queue[server_id][0][0]['source']
            self.message_embed[server_id] = discord.Embed()
            self.message_embed[server_id].description = f"Now playing: [{self.music_queue[server_id][0][0]['title']}]({self.music_queue[server_id][0][0]['yt_url']})"
            await self.music_queue[server_id][0][2].send(embed=self.message_embed[server_id])       #show the next song that is going to play
            self.current_song[server_id] = self.music_queue[server_id].pop(0)
            vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next(vc, server_id)) #initiate to play the next song when the current song is finished
        else:
            self.server_status[server_id]["is_playing"] = False

    @commands.command()
    async def join(self, ctx):                                          #join the voice channel of the command sender
        server_id = ctx.message.guild.id
        self.message_embed[server_id] = discord.Embed()
        if ctx.author.voice is None:
            self.message_embed[server_id].description = "You are not in a voice channel."
            await ctx.send(embed=self.message_embed[server_id])
        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await voice_channel.connect()
        else:
            await ctx.voice_client.move_to(voice_channel)

    @commands.command()
    async def play(self, ctx, *args):                                                              #play song in the voice channel of the command sender
        query = " ".join(args)
        server_id = ctx.message.guild.id
        voice_channel = None
        self.message_embed[server_id] = discord.Embed()
        if (self.server_status.get(server_id) == None):
            self.server_status[server_id] = {"queue_created": False, "is_playing": False, "is_looping": False}
        if (ctx.author.voice is None):                                                             #join the command sender's voice channel or ask the sender to join one
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
        if (self.server_status[server_id]["queue_created"] == False):
            self.music_queue[server_id] = []
            self.server_status[server_id]["queue_created"] = True
        if (ctx.author.voice is not None and ctx.author.voice.channel == voice_channel):           #add the song to the queue and start playing
            song = self.search_yt(query)
            if (type(song) == type(True)):
                self.message_embed[server_id].description = "Could not download the song. Try another keyword"
                await ctx.send(embed=self.message_embed[server_id])
            else:
                self.music_queue[server_id].append([song, voice_channel, ctx.channel])
                if (self.server_status[server_id]["is_playing"] == True):
                    self.message_embed[server_id].description = f"Song added to the queue: [{song['title']}]({song['yt_url']})"
                    await ctx.send(embed=self.message_embed[server_id])  
                else:
                    await self.play_music(ctx.voice_client, server_id)

    @commands.command()
    async def queue(self, ctx):                                                                                 #show the song queue
        retval = "Song queue:\n"
        server_id = ctx.message.guild.id 
        for i in range(0, len(self.music_queue[server_id])):
            retval += f"{str(i+1)}. [{self.music_queue[server_id][i][0]['title']}]({self.music_queue[server_id][i][0]['yt_url']})\n"
        if retval != "Song queue:\n":
            self.message_embed[server_id].description = retval
        else:
            self.message_embed[server_id].description = "No song in the queue"
        await ctx.send(embed=self.message_embed[server_id])

    @commands.command()                                                                                 
    async def remove(self, ctx, q_num):                                                                         #remove songs in the song queue
        server_id = ctx.message.guild.id
        if (q_num == 'all'):                                                                                    #remove all the songs
            self.message_embed[server_id].description = "All queued songs have been remove"
            self.music_queue[server_id] = []    
        elif (q_num.isdigit() == False or int(q_num) < 1 or int(q_num) > (len(self.music_queue[server_id]))):   #report for wrong input
            self.message_embed[server_id].description = "Please enter a correct queue number"
        else:
            self.message_embed[server_id].description = f"Song removed: [{self.music_queue[server_id][int(q_num)-1][0]['title']}]({self.music_queue[server_id][int(q_num)-1][0]['yt_url']})"           
            self.music_queue[server_id].pop(int(q_num)-1)                                                       #remove a specific song
        await ctx.send(embed=self.message_embed[server_id])   
    
    @commands.command()
    async def skip(self, ctx):                                      #skip the current song and initiate to play the next song
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
    
    @commands.command()                                             
    async def pause(self, ctx):                                     #pause the current song
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
    
    @commands.command()                                         
    async def resume(self, ctx):                                    #resume the current song
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
    
    @commands.command()                                             
    async def loop(self, ctx):                                      #loop the current song
        server_id = ctx.message.guild.id
        self.message_embed[server_id] = discord.Embed()
        if (self.server_status[server_id]["is_looping"] == False):
            self.message_embed[server_id].description = "Loop is enabled"
        else:
            self.message_embed[server_id].description = "Loop is disabled"
        self.server_status[server_id]["is_looping"] = not(self.server_status[server_id]["is_looping"])
        await ctx.send(embed=self.message_embed[server_id])
    
    @commands.command()                                             
    async def disconnect(self, ctx):                                #disconnect the bot
        server_id = ctx.message.guild.id
        if (ctx.voice_client is not None):
            self.server_status[server_id]["is_playing"] = False
            self.music_queue[server_id] = []
            ctx.voice_client.stop()
            await ctx.voice_client.disconnect()

    @commands.command()                                             #warning: this function will expose your ip address, only use it in trusted servers
    async def download(self, ctx, *args):                           #generate a downloadable audio file source
        server_id = ctx.message.guild.id                                                           
        query = " ".join(args)
        info = self.search_yt(query)
        self.message_embed[server_id] = discord.Embed()
        self.message_embed[server_id].description = f"Song: {info['title']}. [Click me to download]({info['source']})\nType !downloadhelp to check how to download the song."
        await ctx.send(embed=self.message_embed[server_id])

    @commands.command()
    async def downloadhelp(self, ctx):                              #guide to download the audio file using the 'download' command
        server_id = ctx.message.guild.id
        self.message_embed[server_id] = discord.Embed()
        self.message_embed[server_id].description = "Steps to download audio:\nStep 1: Type !download <song> to generate a hyperlink\nStep 2: Click the hyperlink and open the audio source in browser\nStep 3: Press Ctrl+S\nStep 4: Change the file extension to .mp3 and the file type to \"All Files\"\nStep 5: Click Save"
        await ctx.send(embed=self.message_embed[server_id])

async def setup(bot):
    await bot.add_cog(music_cog(bot))