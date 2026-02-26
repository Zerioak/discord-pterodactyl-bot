"""
cogs/utils.py  –  Shared helpers for all cogs.
"""

from __future__ import annotations

import datetime
from typing import Any

import discord
from discord import app_commands

from config import Colors, FOOTER_TEXT, OWNER_ID


# ── Owner-only app command check ─────────────────────────────────────────────────
def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id != OWNER_ID:
            raise app_commands.CheckFailure("Owner-only command.")
        return True
    return app_commands.check(predicate)


# ── Embed builders ───────────────────────────────────────────────────────────────
def make_embed(
    title: str,
    description: str = "",
    color: discord.Color = Colors.INFO,
    fields: list[tuple[str, str, bool]] | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.utcnow(),
    )
    embed.set_footer(text=FOOTER_TEXT)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=str(value) or "N/A", inline=inline)
    return embed


def error_embed(description: str, title: str = "❌ Error") -> discord.Embed:
    return make_embed(title, description, Colors.ERROR)


def success_embed(description: str, title: str = "✅ Success") -> discord.Embed:
    return make_embed(title, description, Colors.SUCCESS)


def warning_embed(description: str, title: str = "⚠️ Warning") -> discord.Embed:
    return make_embed(title, description, Colors.WARNING)


# ── Safe respond (handles already-responded interactions) ────────────────────────
async def safe_respond(
    interaction: discord.Interaction,
    embed: discord.Embed,
    ephemeral: bool = True,
    view: discord.ui.View | None = None,
):
    kwargs: dict = {"embed": embed, "ephemeral": ephemeral}
    if view is not None:
        kwargs["view"] = view
    try:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)
    except Exception:
        pass


# ── Text helpers ─────────────────────────────────────────────────────────────────
def trunc(text: Any, length: int = 1024) -> str:
    s = str(text) if text else ""
    return s if len(s) <= length else s[: length - 3] + "..."


def fmt_bytes(num: int) -> str:
    if num == 0:
        return "Unlimited"
    if num < 0:
        return "Unlimited"
    if num >= 1024:
        return f"{num / 1024:.1f} GB"
    return f"{num} MB"


# ── Generic Confirm View ─────────────────────────────────────────────────────────
class ConfirmView(discord.ui.View):
    def __init__(self, timeout: float = 30):
        super().__init__(timeout=timeout)
        self.confirmed = False

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()
