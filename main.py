import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()


class Mybot(commands.Bot):
    def __init__(self, command_prefix, intents, config):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.config = config

    async def on_ready(self):
        print(f'Logged in as {self.user.name} - {self.user.id}')
        print('------')
        
        await self.tree.sync()
        for command in self.tree.get_commands():
            print(f'Command: {command.name}')
        print('------')
        
        activity = discord.Streaming(name="ShirafukasBOT", url="https://www.twitch.tv/shirafukayayoi")
        await self.change_presence(status=discord.Status.online, activity=activity)

intents = discord.Intents.default()
intents.message_content = True

bot = Mybot(command_prefix='!', intents=intents, config={})

from command import setup

setup(bot)
bot.run(os.getenv('DISCORD_TOKEN'))