import asyncio
import discord
import os
import requests
import sys
import datetime

from dotenv import load_dotenv
from pprint import pprint
from discord.ext import commands

load_dotenv()

# Super secret stuff
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TWITCH_BEARER_TOKEN = os.getenv("TWITCH_BEARER_TOKEN")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")

# Kinda secret stuff
DISCORD_GUILD = os.getenv("DISCORD_GUILD")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

TWITCH_WAIT_TIME = int(os.getenv("TWITCH_WAIT_TIME"))
SPEEDRUN_TAG_ID = '7cefbf30-4c3e-4aa7-99cd-70aabb662f27'

client = discord.Client()
already_live_speedruns = [] # List of live streamers that have already been posted in the channel to avoid dupes
recently_offline = [] # List of streamers who have gone offline and their message needs to be deleted from the channel
ids = []
async def call_twitch():
    # Waiting period between Twitch API calls - this is first so the bot can connect to Discord on init
    await asyncio.sleep(TWITCH_WAIT_TIME)
    url = 'https://api.twitch.tv/helix/streams?game_id=7341'
    #url = 'https://api.twitch.tv/helix/streams?game_id=11557'
    # TODO - Automate refreshing the Bearer token - it expires after 60 days
    headers = {'Authorization' : 'Bearer ' + TWITCH_BEARER_TOKEN, 'Client-Id': TWITCH_CLIENT_ID}
    return requests.get(url, headers=headers)

def is_speedrun(stream):
    if stream['tag_ids']:
        return SPEEDRUN_TAG_ID in stream['tag_ids']
    return False

async def get_speedruns(twitch_response):
    json_response = twitch_response.json()
    if not json_response:
        return []
    streams = json_response['data']
    if not streams:
        return []
    return list(filter(is_speedrun, streams))

def create_live_embed(embed_user_name, embed_title):
    embed = discord.Embed()
    embed.title=embed_user_name+" is streaming"
    embed.description="["+embed_title+"](https://twitch.tv/"+embed_user_name+")"
    embed.color=0x00FF00
    return embed

#def create_recently_offline_embed(embed_user_name, embed_title):
#    embed = discord.Embed()
#    embed.title=embed_user_name+" is ending stream"
#    embed.description="["+embed_title+"](https://twitch.tv/"+embed_user_name+")"
#    embed.color=0xFF0000
#    return embed  

def create_offline_embed(embed_user_name, embed_title):
    embed = discord.Embed()
    embed.title=embed_user_name+" is no longer streaming"
    embed.description="["+embed_title+"](https://twitch.tv/"+embed_user_name+")"
    embed.color=0xFF0000
    return embed    

async def send_messages(speedrun_channels):
    discord_channel = client.get_channel(DISCORD_CHANNEL_ID)
    for channel in speedrun_channels:
        user_name = channel['user_name']
        title = channel['title']
        embed = create_live_embed(user_name, title)
        if channel not in already_live_speedruns:
            already_live_speedruns.append(channel)
            msg = await discord_channel.send(embed=embed) 
            await msg.edit(embed=embed)
            ids.append(msg.id)
        
    online_channel_names = list((channel for channel in speedrun_channels))
    for channel in already_live_speedruns:
        if channel not in online_channel_names:
            already_live_speedruns.remove(channel)
            recently_offline.append(channel)

async def edit_messages(recently_offline):
    
    discord_channel = client.get_channel(DISCORD_CHANNEL_ID)
    for message_id in ids:
        msg = await discord_channel.fetch_message(message_id)
        embed = msg.embeds[0]
        for channel in recently_offline:
            name = channel['user_name']
            title= channel['title']
            split = embed.title.split()
            new_title = split[0]
            if(new_title == name):
                new_embed = create_offline_embed(name, title)
                await msg.edit(embed=new_embed)
                ids.remove(msg.id)

async def main_task():
    while True:
        twitch_response = await call_twitch()
        speedrun_channels = await get_speedruns(twitch_response)
        await send_messages(speedrun_channels)
        await edit_messages(recently_offline)

@client.event
async def on_ready():
    for guild in client.guilds:
        if guild.name == DISCORD_GUILD:
            break
    await client.change_presence(activity=discord.Game("Metal Arms"))
    print("Connected")

loop = asyncio.get_event_loop()
loop.create_task(client.start(DISCORD_TOKEN))
loop.create_task(main_task())
loop.run_forever()
