"""
cogs/help.py – Premium Interactive /help command.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import Colors
from cogs.utils import is_owner, make_embed, safe_respond


# ═══════════════════════════════════════════════════════════════════════
# CATEGORY DATA
# ═══════════════════════════════════════════════════════════════════════

HELP_CATEGORIES = {
    "nodes": {
        "emoji": "🖥️",
        "title": "Node Management",
        "commands": """
`/nodes overview`
`/nodes list`
`/nodes create`
`/nodes edit`
`/nodes delete`

Allocations:
`/nodes allocations`
`/nodes create-allocations`
`/nodes delete-allocations`

Node Servers:
`/nodes servers`
"""
    },
    "servers": {
        "emoji": "🌐",
        "title": "Server Management",
        "commands": """
`/servers overview`
`/servers list`
`/servers create`
`/servers edit-details`
`/servers edit-build`
`/servers edit-startup`
`/servers delete`
`/servers suspend`
`/servers unsuspend`
`/servers reinstall`

Databases:
`/servers databases`
"""
    },
    "users": {
        "emoji": "👤",
        "title": "User Management",
        "commands": """
`/users overview`
`/users list`
`/users create`
`/users edit`
`/users delete`
`/users roles`
`/users servers`
"""
    },
    "nests": {
        "emoji": "🪹",
        "title": "Nest Management",
        "commands": """
`/nests overview`
`/nests list`
`/nests eggs`
`/nests servers`
"""
    },
    "eggs": {
        "emoji": "🥚",
        "title": "Egg Management",
        "commands": """
`/eggs overview`
`/eggs list`
`/eggs servers`
"""
    },
    "mounts": {
        "emoji": "📁",
        "title": "Mount Management",
        "commands": """
`/mounts overview`
`/mounts list`
`/mounts create`
`/mounts edit`
`/mounts delete`
`/mounts servers`
`/mounts nodes`
`/mounts eggs`
"""
    },
    "roles": {
        "emoji": "🛡️",
        "title": "Role Management",
        "commands": """
`/roles overview`
`/roles list`
`/roles create`
`/roles edit`
`/roles delete`
"""
    },
}


# ═══════════════════════════════════════════════════════════════════════
# SELECT MENU VIEW
# ═══════════════════════════════════════════════════════════════════════

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=data["title"],
                description=f"View all {data['title']} commands",
                emoji=data["emoji"],
                value=key
            )
            for key, data in HELP_CATEGORIES.items()
        ]

        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        data = HELP_CATEGORIES[key]

        embed = make_embed(
            title=f"{data['emoji']} {data['title']}",
            description=data["commands"],
            color=Colors.INFO
        )

        embed.set_footer(text="Pterodactyl Admin • Premium Help System")

        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(HelpSelect())


# ═══════════════════════════════════════════════════════════════════════
# COG
# ═══════════════════════════════════════════════════════════════════════

class HelpCog(commands.Cog, name="Help"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Premium admin help panel.")
    @is_owner()
    async def help_cmd(self, interaction: discord.Interaction):

        embed = make_embed(
            title="🦅 Pterodactyl Admin Panel",
            description=(
                "**Enterprise Control System**\n\n"
                "Select a category below to view full command details.\n\n"
                "All commands are owner-only and secure."
            ),
            color=Colors.INFO,
        )

        embed.set_footer(text="HYDRFL GAMING • Admin System")

        view = HelpView()

        await safe_respond(interaction, embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))