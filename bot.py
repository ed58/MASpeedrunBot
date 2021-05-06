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
recently_offline = [] # List of streamers who have gone offline and their message needs to be edited
message_ids = [] # List of message ID's used to keep track of individual messages

async def call_twitch():
    # Waiting period between Twitch API calls - this is first so the bot can connect to Discord on init
    await asyncio.sleep(TWITCH_WAIT_TIME)
    url = 'https://api.twitch.tv/helix/streams?game_id=7341'
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

async def send_messages(speedrun_channels):
    discord_channel = client.get_channel(DISCORD_CHANNEL_ID)
    for channel in speedrun_channels:
        user_name = channel['user_name']
        title = channel['title']
        embed = create_live_embed(user_name, title)
        if user_name not in already_live_speedruns:
            already_live_speedruns.append(user_name)
            msg = await discord_channel.send(embed=embed)
            message_ids.append(msg.id)

    # Check for any offline streams and add them to recently_offline    
    online_channel_names = list((channel['user_name'] for channel in speedrun_channels))
    for channel in already_live_speedruns:
        if channel not in online_channel_names:
            already_live_speedruns.remove(channel)
            recently_offline.append(channel)

async def delete_messages():
    discord_channel = client.get_channel(DISCORD_CHANNEL_ID)
    # Compare each message id with each name in recently_offline and delete the message if a match is found
    for id in message_ids:
        msg = await discord_channel.fetch_message(id)
        embed = msg.embeds[0]
        for user_name in recently_offline:
            split = embed.title.split()
            embed_user_name = split[0]
            if(embed_user_name == user_name):
                await msg.delete()
                message_ids.remove(msg.id)
                recently_offline.remove(user_name)

async def main_task():
    while True:
        twitch_response = await call_twitch()
        speedrun_channels = await get_speedruns(twitch_response)
        await send_messages(speedrun_channels)
        await delete_messages()

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
