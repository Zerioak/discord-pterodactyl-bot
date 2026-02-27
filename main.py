"""
main.py – Pterodactyl Admin Discord Bot entry-point.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import itertools
import datetime

import discord
from discord.ext import commands

from config import DISCORD_TOKEN, OWNER_ID, BOT_NAME, BOT_VERSION
from api_client import PterodactylClient


# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ptero-bot")


# ═══════════════════════════════════════════════════════════════
# ENV CHECK
# ═══════════════════════════════════════════════════════════════

if not DISCORD_TOKEN:
    log.critical("DISCORD_TOKEN is missing from .env — aborting.")
    sys.exit(1)

if not OWNER_ID:
    log.critical("OWNER_ID is missing from .env — aborting.")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# BOT CLASS
# ═══════════════════════════════════════════════════════════════

class PterodactylBot(commands.Bot):
    """Custom Bot that exposes a shared Pterodactyl API client to every cog."""

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

        self.ptero = PterodactylClient()
        self.owner_id = OWNER_ID


    # ────────────────────────────────────────────────────────────
    # LOAD COGS + SYNC COMMANDS
    # ────────────────────────────────────────────────────────────

    async def setup_hook(self):

        cogs = [
            "cogs.help",
            "cogs.nodes",
            "cogs.eggs",
            "cogs.nests",
            "cogs.mounts",
            "cogs.database_hosts",
            "cogs.users",
            "cogs.servers",
            "cogs.roles",
            "cogs.manage",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info(f"✓ Loaded {cog}")
            except Exception as exc:
                log.error(f"✗ Failed to load {cog}: {exc}", exc_info=True)

        synced = await self.tree.sync()
        log.info(f"Synced {len(synced)} slash commands globally.")


    # ────────────────────────────────────────────────────────────
    # READY EVENT + ROTATING STATUS
    # ────────────────────────────────────────────────────────────

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info(f"{BOT_NAME} v{BOT_VERSION} is online.")

        activities = itertools.cycle([
            discord.Activity(
                type=discord.ActivityType.watching,
                name="Pterodactyl Panel | Made by Zerioak"
            ),
            discord.Game("Minecraft"),
        ])

        async def rotate_status():
            await self.wait_until_ready()

            while not self.is_closed():
                activity = next(activities)
                await self.change_presence(
                    status=discord.Status.idle,
                    activity=activity
                )
                await asyncio.sleep(15)

        self.loop.create_task(rotate_status())


    # ────────────────────────────────────────────────────────────
    # CLEAN SHUTDOWN
    # ────────────────────────────────────────────────────────────

    async def close(self):
        await self.ptero.close()
        await super().close()


    # ────────────────────────────────────────────────────────────
    # GLOBAL SLASH COMMAND ERROR HANDLER
    # ────────────────────────────────────────────────────────────

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ):
        from config import Colors, FOOTER_TEXT

        embed = discord.Embed(
            title="❌ Error",
            color=Colors.ERROR,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(text=FOOTER_TEXT)

        if isinstance(error, discord.app_commands.CheckFailure):
            embed.description = "🔒 You do not have permission to use this command."
        else:
            embed.description = f"An unexpected error occurred:\n```{error}```"
            log.error(f"Unhandled error: {error}", exc_info=True)

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════

async def main():
    bot = PterodactylBot()
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped by keyboard interrupt.")
