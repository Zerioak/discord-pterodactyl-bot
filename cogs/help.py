"""
cogs/help.py – Enterprise Interactive /help command.
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
`/nodes allocations`
`/nodes create-allocations`
`/nodes delete-allocations`
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
`/servers databases`
"""
    },
    "manage": {
        "emoji": "🎮",
        "title": "Live Server Control",
        "commands": """
`/manage`

• Start / Stop / Restart / Kill
• Live CPU / RAM / Disk stats
• Real-time power control
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
# EMBED BUILDERS
# ═══════════════════════════════════════════════════════════════════════

def build_home_embed():
    total_commands = sum(
        len(data["commands"].strip().split("\n"))
        for data in HELP_CATEGORIES.values()
    )

    embed = make_embed(
        title="🦅 Pterodactyl Enterprise Admin",
        description=(
            "**Advanced Control System**\n\n"
            "Select a category below to view full command details.\n\n"
            f"📊 Total Commands: **{total_commands}**\n"
            "🔐 Access Level: Owner Only"
        ),
        color=Colors.INFO,
    )

    embed.set_footer(text="HYDRFL GAMING • Enterprise Panel")
    return embed


def build_category_embed(key: str):
    data = HELP_CATEGORIES[key]

    embed = make_embed(
        title=f"{data['emoji']} {data['title']}",
        description=data["commands"],
        color=Colors.INFO
    )

    embed.set_footer(text="Enterprise Help • Secure System")
    return embed


# ═══════════════════════════════════════════════════════════════════════
# VIEW
# ═══════════════════════════════════════════════════════════════════════

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=data["title"],
                description=f"View {data['title']} commands",
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
        embed = build_category_embed(self.values[0])
        await interaction.response.edit_message(embed=embed, view=self.view)


class HomeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Home", emoji="🏠", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=build_home_embed(),
            view=self.view
        )


class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close", emoji="✖️", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        await interaction.message.delete()


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(HelpSelect())
        self.add_item(HomeButton())
        self.add_item(CloseButton())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# ═══════════════════════════════════════════════════════════════════════
# COG
# ═══════════════════════════════════════════════════════════════════════

class HelpCog(commands.Cog, name="Help"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Enterprise admin help panel.")
    @is_owner()
    async def help_cmd(self, interaction: discord.Interaction):

        embed = build_home_embed()
        view = HelpView()

        await safe_respond(interaction, embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
