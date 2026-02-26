"""
config.py
Centralised configuration — reads from .env via python-dotenv.
"""

import os
from dotenv import load_dotenv
import discord

load_dotenv()

# ── Bot ──────────────────────────────────────────────────────────────────────────
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
OWNER_ID: int      = int(os.getenv("OWNER_ID", "0"))

# ── Pterodactyl ──────────────────────────────────────────────────────────────────
PTERODACTYL_URL: str     = os.getenv("PTERODACTYL_URL", "").rstrip("/")
PTERODACTYL_API_KEY: str = os.getenv("PTERODACTYL_API_KEY", "")

# ── Embed colours ────────────────────────────────────────────────────────────────
class Colors:
    NODES    = discord.Color.blue()
    SERVERS  = discord.Color.green()
    USERS    = discord.Color.yellow()
    EGGS     = discord.Color.purple()
    NESTS    = discord.Color.teal()
    MOUNTS   = discord.Color.orange()
    DB_HOSTS = discord.Color.from_rgb(255, 140, 0)
    ROLES    = discord.Color.from_rgb(160, 90, 240)
    ERROR    = discord.Color.red()
    SUCCESS  = discord.Color.green()
    WARNING  = discord.Color.orange()
    INFO     = discord.Color.blurple()

# ── Meta ─────────────────────────────────────────────────────────────────────────
BOT_NAME    = "Made by ♥️ @zerioak"
BOT_VERSION = "1.0.0"
FOOTER_TEXT = f"{BOT_NAME} v{BOT_VERSION}"
