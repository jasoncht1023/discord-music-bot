import discord
import asyncio
from discord.ext import commands
import os

bot = commands.Bot(command_prefix='!', intents = discord.Intents.all())
token = ""
with open("token.txt") as file:
    token = file.read()

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")

@bot.event
async def on_error(event, *args):
    print(f'Error in {event}: {args}')

@bot.command()
async def bothelp(ctx):
    message_embed = discord.Embed()
    message_embed.description = "Command list:\n!join\n!play <song/url>\n!queue\n!remove <queue number/all>\n!skip\n!pause\n!resume\n!loop\n!download <song>\n!downloadhelp"
    await ctx.send(embed=message_embed)

async def load():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

async def main():
    async with bot:
        await load()
        await bot.start(token)

asyncio.run(main())

