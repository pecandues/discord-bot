# ====== KEEP ALIVE WEB SERVER ======
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()


# ====== DISCORD BOT CODE ======
import re
import json
import os
import asyncio
from datetime import datetime, timedelta
import discord
from discord.ext import commands

keep_alive()

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Regex for: "nickname HH:MM"
time_regex = re.compile(r"(.+?)\s+(\d{1,2}:\d{2})")

TIMERS_FILE = "timers.json"

# Persistent storage: { user_id: [ {nickname, finish, channel_id}, ... ] }
active_timers = {}



# ====== HELPER FUNCTIONS ======

def load_timers():
    """Load persistent timers from timers.json"""
    global active_timers

    if not os.path.exists(TIMERS_FILE):
        with open(TIMERS_FILE, "w") as f:
            json.dump({}, f)

    try:
        with open(TIMERS_FILE, "r") as f:
            data = json.load(f)
            # Convert finish time back to datetime
            for user_id, timers in data.items():
                active_timers[int(user_id)] = [
                    {
                        "nickname": t["nickname"],
                        "finish": datetime.strptime(t["finish"], "%Y-%m-%d %H:%M"),
                        "channel_id": t["channel_id"]
                    }
                    for t in timers
                ]
    except:
        active_timers = {}


def save_timers():
    """Save all timers to timers.json"""
    data = {}
    for user_id, timers in active_timers.items():
        data[user_id] = [
            {
                "nickname": t["nickname"],
                "finish": t["finish"].strftime("%Y-%m-%d %H:%M"),
                "channel_id": t["channel_id"]
            }
            for t in timers
        ]
    with open(TIMERS_FILE, "w") as f:
        json.dump(data, f, indent=4)



async def start_timer(user_id, nickname, finish_time, channel_id):
    """Sleep until finish_time, then remind user."""
    now = datetime.now()
    seconds_left = (finish_time - now).total_seconds()

    if seconds_left > 0:
        await asyncio.sleep(seconds_left)

    channel = bot.get_channel(channel_id)
    user = bot.get_user(user_id)

    if channel and user:
        await channel.send(f"{user.mention} reminder:\n{nickname} is finished.")

    # Remove finished timer
    if user_id in active_timers:
        active_timers[user_id] = [
            t for t in active_timers[user_id] if t["nickname"] != nickname
        ]
        save_timers()


def restart_existing_timers():
    """After bot restarts, resume timers"""
    now = datetime.now()

    for user_id, timers in active_timers.items():
        for t in timers:
            if t["finish"] > now:
                # Resume countdown
                bot.loop.create_task(
                    start_timer(user_id, t["nickname"], t["finish"], t["channel_id"])
                )
            else:
                # Timer already finished → no reminder, remove it
                active_timers[user_id] = [
                    timer for timer in active_timers[user_id]
                    if timer["nickname"] != t["nickname"]
                ]
                save_timers()



# ====== BOT EVENTS ======

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    load_timers()
    restart_existing_timers()



@bot.event
async def on_message(message):
    if message.author.bot:
        return

    text = message.content.strip()
    match = time_regex.match(text)

    if match:
        nickname = match.group(1).strip()
        start_str = match.group(2).strip()

        # Parse HH:MM time
        try:
            start_time = datetime.strptime(start_str, "%H:%M")
        except:
            return

        now = datetime.now()

        # Apply today's date
        start_time = start_time.replace(year=now.year, month=now.month, day=now.day)

        finish_time = start_time + timedelta(hours=8)

        # CASE 2: Already finished → show "You've Done"
        if finish_time <= now:
            finish_fmt = finish_time.strftime("%H:%M")
            msg = (
                f"**You've Done**\n"
                f"**Finished At :** {finish_fmt}"
            )
            await message.reply(msg)
            return

        # CASE 1: Active timer
        start_fmt = start_time.strftime("%H:%M")
        finish_fmt = finish_time.strftime("%H:%M")

        reply = (
            f"**Nickname :** {nickname}\n"
            f"**Starting Time :** {start_fmt}\n"
            f"**Estimated Finish :** {finish_fmt}"
        )
        await message.reply(reply)

        user_id = message.author.id
        channel_id = message.channel.id

        if user_id not in active_timers:
            active_timers[user_id] = []

        # Store timer persistently
        active_timers[user_id].append({
            "nickname": nickname,
            "finish": finish_time,
            "channel_id": channel_id
        })
        save_timers()

        # Start countdown
        bot.loop.create_task(start_timer(user_id, nickname, finish_time, channel_id))

    await bot.process_commands(message)



# ====== COMMANDS ======

@bot.command()
async def list(ctx):
    """List your active timers"""
    user_id = ctx.author.id

    if user_id not in active_timers or len(active_timers[user_id]) == 0:
        await ctx.reply("You have no active timers.")
        return

    timers = sorted(active_timers[user_id], key=lambda x: x["finish"])

    msg = "**Your Active Timers:**\n"
    for i, t in enumerate(timers, start=1):
        msg += f"{i}. {t['nickname']} — {t['finish'].strftime('%H:%M')}\n"

    await ctx.reply(msg)



@bot.command()
async def reset(ctx):
    """Reset ALL of your timers (for testing)"""
    user_id = ctx.author.id

    if user_id in active_timers:
        active_timers[user_id] = []
        save_timers()

    await ctx.reply("All your timers have been reset.")


bot.run(TOKEN)
