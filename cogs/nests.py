"""cogs/nests.py  –  /nests command group."""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from api_client import PterodactylClient, PterodactylError
from config import Colors
from cogs.utils import is_owner, make_embed, error_embed, warning_embed, trunc

class NestsCog(commands.Cog, name="Nests"):
    def __init__(self, bot):
        self.bot   = bot
        self.ptero: PterodactylClient = bot.ptero

    nests_group = app_commands.Group(name="nests", description="Browse Pterodactyl nests.")

    @nests_group.command(name="overview", description="Nests overview.")
    @is_owner()
    async def nests_overview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nests = await self.ptero.list_nests()
            e = make_embed("🪹 Nests Overview", f"**{len(nests)}** nest(s) configured.", Colors.NESTS,
                           fields=[("Total Nests", str(len(nests)), True)])
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @nests_group.command(name="list", description="List all nests.")
    @is_owner()
    async def nests_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nests = await self.ptero.list_nests()
            if not nests:
                await interaction.followup.send(embed=warning_embed("No nests found."), ephemeral=True)
                return
            e = make_embed("🪹 All Nests", f"Found **{len(nests)}** nest(s):", Colors.NESTS)
            for n in nests:
                a = n["attributes"]
                e.add_field(name=f"[{a['id']}] {a['name']}", value=trunc(a.get("description") or "No description.", 256), inline=True)
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @nests_group.command(name="eggs", description="View eggs in a nest.")
    @is_owner()
    async def nests_eggs(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nests = await self.ptero.list_nests()
            if not nests:
                await interaction.followup.send(embed=warning_embed("No nests found."), ephemeral=True)
                return
            opts = [discord.SelectOption(label=trunc(n["attributes"]["name"], 100), value=str(n["attributes"]["id"])) for n in nests[:25]]
            sel  = discord.ui.Select(placeholder="Select a nest…", options=opts)
            async def on_sel(inter):
                nid  = int(inter.data["values"][0])
                await inter.response.defer(ephemeral=True)
                eggs = await self.ptero.list_eggs(nid)
                e = make_embed(f"🪹 Eggs in Nest {nid}", f"Found **{len(eggs)}** egg(s):", Colors.NESTS)
                for eg in eggs[:20]:
                    a = eg["attributes"]
                    e.add_field(name=f"[{a['id']}] {a['name']}", value=trunc(a.get("description") or "—", 256), inline=True)
                await inter.followup.send(embed=e, ephemeral=True)
            sel.callback = on_sel
            view = discord.ui.View(timeout=60); view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🪹 Nest Eggs", "Select a nest:", Colors.NESTS), view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @nests_group.command(name="servers", description="Show servers grouped by nest.")
    @is_owner()
    async def nests_servers(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nests   = await self.ptero.list_nests()
            servers = await self.ptero.list_servers()
            e = make_embed("🪹 Servers by Nest", f"**{len(servers)}** server(s) across **{len(nests)}** nest(s).", Colors.NESTS)
            for nest in nests[:10]:
                nid    = nest["attributes"]["id"]
                n_eggs = await self.ptero.list_eggs(nid)
                eids   = {eg["attributes"]["id"] for eg in n_eggs}
                ns     = [s for s in servers if s["attributes"].get("egg") in eids]
                if ns:
                    lines = "\n".join(f"`{s['attributes']['id']}` {s['attributes']['name']}" for s in ns[:8])
                    e.add_field(name=f"🪹 {nest['attributes']['name']} ({len(ns)})", value=trunc(lines, 1024), inline=False)
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

async def setup(bot): await bot.add_cog(NestsCog(bot))
