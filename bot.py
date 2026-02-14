# Importing libraries and modules
import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp
from collections import deque
import asyncio

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Song queues for each guild
SONG_QUEUES = {}

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)

# Discord intents
intents = discord.Intents.default()
intents.message_content = True

# Bot setup
bot = commands.Bot(command_prefix="!", intents=intents)

# When bot is online
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🐶 {bot.user} đã thức dậy và sẵn sàng quẩy nhạc nè!! 🎧✨")
    print("💖 Cún Con DJ xin chào chủ nhân, cho nghe bài gì hén~")


# -----------------------------
# /skip
# -----------------------------
@bot.tree.command(name="skip", description="Skips the current playing song")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client

    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await interaction.response.send_message("👉👉 *Cún bỏ qua bài này theo lệnh chủ nhân nhaaa~* 🎶✨")
    else:
        await interaction.response.send_message("🥺 Ơ hong có bài nào để skip hết trơn á chủ nhân ơi...")


# -----------------------------
# /pause
# -----------------------------
@bot.tree.command(name="pause", description="Pause the currently playing song.")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client

    if vc is None:
        return await interaction.response.send_message("🐶 *Cún chưa vô voice mà chủ nhân kêu pause… ngơ luôn á!* 😳")

    if not vc.is_playing():
        return await interaction.response.send_message("🌸 Hiện tại hong có bài nào đang phát để pause đâu chủ nhann~")

    vc.pause()
    await interaction.response.send_message("⏸️ *Cún đã tạm dừng bài nhạc lại cho chủ nhân rồi nè!* 🎀")


# -----------------------------
# /resume
# -----------------------------
@bot.tree.command(name="resume", description="Resume the currently paused song.")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client

    if vc is None:
        return await interaction.response.send_message("🐶 *Cún còn chưa vô phòng, resume sao được chòiiii~* 😭")

    if not vc.is_paused():
        return await interaction.response.send_message("✨ Có bài nào bị pause đâu, chủ nhân đừng troll Cún nữa màaa~ 😤💗")

    vc.resume()
    await interaction.response.send_message("▶️ *Cún tiếp tục phát nhạc cho chủ nhân nè!!!* 🎧💞")


# -----------------------------
# /stop
# -----------------------------
@bot.tree.command(name="stop", description="Stop playback and clear the queue.")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client

    if not vc or not vc.is_connected():
        return await interaction.response.send_message("🐶 *Cún có đang ở trong voice đâu mà dừng…* 😳")

    guild_id = str(interaction.guild_id)

    if guild_id in SONG_QUEUES:
        SONG_QUEUES[guild_id].clear()

    if vc.is_playing() or vc.is_paused():
        vc.stop()

    await vc.disconnect()

    await interaction.response.send_message("💤 *Cún đã dừng nhạc và rút lui nhẹ nhàng theo lệnh chủ nhân…* 💖")


# -----------------------------
# /play
# -----------------------------
@bot.tree.command(name="play", description="Play a song or add it to the queue.")
@app_commands.describe(song_query="Search query")
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer()

    # Check if user is in voice
    if interaction.user.voice is None:
        await interaction.followup.send("🐶 *Chủ nhân phải vô voice thì Cún mới chạy theo quẩy chung được chứ!* 🥺💗")
        return

    voice_channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client

    # Connect or move to user's voice
    if vc is None:
        vc = await voice_channel.connect()
    elif vc.channel != voice_channel:
        await vc.move_to(voice_channel)

    # Search YouTube
    ydl_options = {
        "format": "bestaudio[abr<=96]/bestaudio",
        "noplaylist": True,
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
    }

    query = "ytsearch1: " + song_query
    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get("entries", [])

    if not tracks:
        await interaction.followup.send("🥺 *Cún tìm hong ra bài này luôn á… buồn ghê…*")
        return

    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "Tên bí mật 🤫")

    guild_id = str(interaction.guild_id)
    if guild_id not in SONG_QUEUES:
        SONG_QUEUES[guild_id] = deque()

    SONG_QUEUES[guild_id].append((audio_url, title))

    if vc.is_playing() or vc.is_paused():
        await interaction.followup.send(f"📥 *Đã thêm vào hàng chờ cho chủ nhân:* **{title}** 💖✨")
    else:
        await interaction.followup.send(f"🎧 *Cún mở bài này cho chủ nhân nghe liềnn:* **{title}** 💞")
        await play_next_song(vc, guild_id, interaction.channel)


# -----------------------------
# Auto play next song
# -----------------------------
async def play_next_song(voice_client, guild_id, channel):
    if SONG_QUEUES[guild_id]:
        audio_url, title = SONG_QUEUES[guild_id].popleft()

        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -c:a libopus -b:a 96k",
        }

        source = discord.FFmpegOpusAudio(
            audio_url, 
            **ffmpeg_options,
            executable="/usr/bin/ffmpeg"
        )

        def after_play(error):
            if error:
                print(f"💥 Lỗi khi phát bài {title}: {error}")
            asyncio.run_coroutine_threadsafe(
                play_next_song(voice_client, guild_id, channel),
                bot.loop
            )

        voice_client.play(source, after=after_play)

        await channel.send(f"🎶 *Bài tiếp theo nè chủ nhân:* **{title}** ✨💗")
    else:
        await voice_client.disconnect()
        SONG_QUEUES[guild_id] = deque()

#Menu
@bot.tree.command(name="menu", description="Hiển thị danh sách tính năng của bot")
async def menu(interaction: discord.Interaction):

    embed = discord.Embed(
        title="📌 Danh Sách Tính Năng Của Bot",
        description="Toàn bộ tính năng hiện tại và nâng cấp sắp ra mắt.",
        color=discord.Color.blue()
    )

    # Tính năng hiện có
    embed.add_field(
        name="1️⃣ Tính Năng Hiện Có",
        value=(
            "**/play <tên bài>** : Phát nhạc hoặc thêm vào hàng chờ.\n"
            "**/skip** : Bỏ qua bài hiện tại.\n"
            "**/pause** : Tạm dừng bài nhạc.\n"
            "**/resume** : Tiếp tục phát nhạc.\n"
            "**/stop** : Dừng phát và thoát voice.\n"
            "Tự động phát bài tiếp theo : Có.\n"
        ),
        inline=False
    )

    # Coming Soon - Music Upgrade
    embed.add_field(
        name="2️⃣ Tính Năng Sắp Có",
        value=(
            "**/queue** : Hiển thị danh sách chờ.\n"
            "**/remove <vị trí>** : Xoá bài khỏi hàng chờ.\n"
            "**/nowplaying** : Xem bài đang phát.\n"
            "**/join** : Bot tham gia voice.\n"
            "**/leave** : Bot rời voice.\n"
            "**Volume Control** : Điều chỉnh âm lượng.\n"
        ),
        inline=False
    )

    # 6 tính năng nâng cao
    embed.add_field(
        name="3️⃣ Tính Năng Nâng Cao (Coming Soon)",
        value=(
            "**/filter <effect>** : Bass Boost, 8D, Nightcore, Slow+Reverb.\n"
            "**/seek <giây>** : Tua nhạc theo thời gian.\n"
            "**/move <từ> <đến>** : Đổi vị trí bài trong queue.\n"
            "**/shuffle** : Xáo trộn danh sách chờ.\n"
            "**/autoplay** : Tự phát bài tương tự khi queue trống.\n"
            "**/favorites** : Hệ thống bài hát yêu thích theo user.\n"
        ),
        inline=False
    )

    embed.set_footer(text="Danh sách được cập nhật theo phiên bản bot hiện tại.")

    await interaction.response.send_message(embed=embed)




# Run the bot
bot.run(TOKEN)
