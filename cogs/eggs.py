"""cogs/eggs.py  –  /eggs command group."""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from api_client import PterodactylClient, PterodactylError
from config import Colors
from cogs.utils import is_owner, make_embed, error_embed, warning_embed, trunc

class EggsCog(commands.Cog, name="Eggs"):
    def __init__(self, bot):
        self.bot   = bot
        self.ptero: PterodactylClient = bot.ptero

    eggs_group = app_commands.Group(name="eggs", description="Browse Pterodactyl eggs.")

    @eggs_group.command(name="overview", description="Eggs statistics overview.")
    @is_owner()
    async def eggs_overview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nests = await self.ptero.list_nests()
            total = 0
            lines = []
            for nest in nests:
                eggs = await self.ptero.list_eggs(nest["attributes"]["id"])
                total += len(eggs)
                lines.append(f"**{nest['attributes']['name']}** — {len(eggs)} egg(s)")
            e = make_embed("🥚 Eggs Overview", "\n".join(lines) or "No eggs.", Colors.EGGS,
                           fields=[("Nests", str(len(nests)), True), ("Total Eggs", str(total), True)])
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @eggs_group.command(name="list", description="List all eggs across all nests.")
    @is_owner()
    async def eggs_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nests = await self.ptero.list_nests()
            e     = make_embed("🥚 All Eggs", "", Colors.EGGS)
            total = 0
            for nest in nests:
                eggs = await self.ptero.list_eggs(nest["attributes"]["id"])
                total += len(eggs)
                if eggs:
                    lines = "\n".join(f"`{eg['attributes']['id']}` — {eg['attributes']['name']}" for eg in eggs)
                    e.add_field(name=f"🪹 {nest['attributes']['name']}", value=trunc(lines, 1024), inline=False)
            e.description = f"Found **{total}** egg(s) across **{len(nests)}** nest(s)."
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @eggs_group.command(name="servers", description="Show servers using a specific egg.")
    @is_owner()
    async def eggs_servers(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            all_eggs = await self.ptero.list_all_eggs()
            if not all_eggs:
                await interaction.followup.send(embed=warning_embed("No eggs found."), ephemeral=True)
                return
            opts = [discord.SelectOption(label=trunc(eg["attributes"]["name"], 100), value=str(eg["attributes"]["id"]),
                    description=f"Nest {eg['attributes']['nest']}") for eg in all_eggs[:25]]
            sel = discord.ui.Select(placeholder="Choose an egg…", options=opts)
            async def on_sel(inter):
                eid     = int(inter.data["values"][0])
                await inter.response.defer(ephemeral=True)
                servers = await self.ptero.list_servers()
                using   = [s for s in servers if s["attributes"].get("egg") == eid]
                e = make_embed(f"🥚 Servers Using Egg {eid}", f"**{len(using)}** server(s).", Colors.EGGS)
                for s in using[:15]:
                    a = s["attributes"]
                    e.add_field(name=f"[{a['id']}] {a['name']}", value=f"`{a['uuid'][:8]}…`", inline=True)
                await inter.followup.send(embed=e, ephemeral=True)
            sel.callback = on_sel
            view = discord.ui.View(timeout=60); view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🥚 Egg → Servers", "Select an egg:", Colors.EGGS), view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

async def setup(bot): await bot.add_cog(EggsCog(bot))
