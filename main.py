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
from datetime import datetime, timedelta
import discord
from discord.ext import commands, tasks
import os
import asyncio

keep_alive()

TOKEN = os.getenv("TOKEN")

# GANTI INI dengan channel ID tempat bot kirim @here reset offline mode
RESET_CHANNEL_ID = 123456789012345678  # <-- REPLACE with your channel ID

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Regex: "something HH:MM" (24-hour format)
time_regex = re.compile(r"(.+?)\s+(\d{1,2}:\d{2})")

# Store active timers: {user_id: [ (nickname, finish_datetime, channel_id) , ... ]}
active_timers = {}

# Untuk mencegah spam reset (@here) lebih dari sekali per hari
last_reset_date = None


@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    # mulai task cek reset harian
    if not daily_reset_notifier.is_running():
        daily_reset_notifier.start()


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    text = message.content.strip()
    match = time_regex.match(text)

    if match:
        nickname = match.group(1).strip()
        start_str = match.group(2)

        # Parse starting time (24-hour format)
        try:
            start_time = datetime.strptime(start_str, "%H:%M")
        except:
            return  # invalid format, ignore

        # Hitung estimasi selesai (hanya tampilan, +8 jam)
        finish_time = start_time + timedelta(hours=8)

        # Format times
        start_fmt = start_time.strftime("%H:%M")
        finish_fmt = finish_time.strftime("%H:%M")

        # Respond to user
        reply = (
            f"**Nickname :** {nickname}\n"
            f"**Starting Time :** {start_fmt}\n"
            f"**Estimated Finish :** {finish_fmt}"
        )
        await message.reply(reply)

        # Simpan timer (8 jam dari sekarang)
        user_id = message.author.id
        channel_id = message.channel.id

        if user_id not in active_timers:
            active_timers[user_id] = []

        # Record the new timer (pakai waktu sekarang + 8 jam untuk actual reminder)
        real_finish_time = datetime.now() + timedelta(hours=8)
        active_timers[user_id].append((nickname, real_finish_time, channel_id))

        # Start the countdown task untuk timer ini
        bot.loop.create_task(start_timer(user_id, nickname, channel_id))

    await bot.process_commands(message)


async def start_timer(user_id, nickname, channel_id):
    """Timer task untuk setiap nickname (selalu 8 jam)."""
    await asyncio.sleep(8 * 60 * 60)

    channel = bot.get_channel(channel_id)
    if channel:
        user = bot.get_user(user_id)
        if user:
            await channel.send(f"{user.mention} reminder:\n{nickname} is finished.")

    # Bersihkan timer yang sudah selesai dari list
    if user_id in active_timers:
        active_timers[user_id] = [
            t for t in active_timers[user_id] if t[0] != nickname
        ]


@tasks.loop(minutes=1)
async def daily_reset_notifier():
    """
    Cek setiap 1 menit.
    Kalau jam menunjukkan 04:00 (UTC+8) dan belum kirim hari ini,
    kirim @here di channel RESET_CHANNEL_ID.
    """
    global last_reset_date

    # Ambil waktu UTC lalu convert ke UTC+8 tanpa library eksternal
    now_utc = datetime.utcnow()
    now_utc8 = now_utc + timedelta(hours=8)

    current_date = now_utc8.date()
    current_hour = now_utc8.hour
    current_minute = now_utc8.minute

    # Cek kalau jam 04:00 dan belum kirim notifikasi hari ini
    if current_hour == 4 and current_minute == 0:
        if last_reset_date != current_date:
            channel = bot.get_channel(RESET_CHANNEL_ID)
            if channel:
                await channel.send("@here offline mode has been reset. (04:00 UTC+8)")
                last_reset_date = current_date


@daily_reset_notifier.before_loop
async def before_daily_reset_notifier():
    # Tunggu sampai bot siap dulu
    await bot.wait_until_ready()


bot.run(TOKEN)
