"""cogs/mounts.py  –  /mounts command group."""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from api_client import PterodactylClient, PterodactylError
from config import Colors
from cogs.utils import is_owner, make_embed, error_embed, success_embed, warning_embed, trunc, ConfirmView


class CreateMountModal(discord.ui.Modal, title="Create Mount"):
    name      = discord.ui.TextInput(label="Name",        placeholder="shared-plugins")
    source    = discord.ui.TextInput(label="Source Path", placeholder="/mnt/shared/plugins")
    target    = discord.ui.TextInput(label="Target Path", placeholder="/plugins")
    desc      = discord.ui.TextInput(label="Description", required=False, style=discord.TextStyle.paragraph)
    read_only = discord.ui.TextInput(label="Read-Only? (yes/no)", placeholder="no", required=False)

    def __init__(self, ptero):
        super().__init__()
        self.ptero = ptero

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            payload = {
                "name": self.name.value, "source": self.source.value, "target": self.target.value,
                "description": self.desc.value or "",
                "read_only": self.read_only.value.lower() in ("yes", "true", "1"),
                "user_mountable": False,
            }
            result = await self.ptero.create_mount(payload)
            attr = result["attributes"]
            e = success_embed(f"Mount **{attr['name']}** (ID `{attr['id']}`) created.", title="📁 Mount Created")
            e.color = Colors.MOUNTS
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


class EditMountModal(discord.ui.Modal, title="Edit Mount"):
    name      = discord.ui.TextInput(label="Name")
    source    = discord.ui.TextInput(label="Source Path")
    target    = discord.ui.TextInput(label="Target Path")
    desc      = discord.ui.TextInput(label="Description", required=False, style=discord.TextStyle.paragraph)
    read_only = discord.ui.TextInput(label="Read-Only? (yes/no)", required=False)

    def __init__(self, ptero, mount_id, current):
        super().__init__()
        self.ptero    = ptero
        self.mount_id = mount_id
        self.name.default     = current.get("name", "")
        self.source.default   = current.get("source", "")
        self.target.default   = current.get("target", "")
        self.desc.default     = current.get("description", "")
        self.read_only.default = "yes" if current.get("read_only") else "no"

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            payload = {
                "name": self.name.value, "source": self.source.value, "target": self.target.value,
                "description": self.desc.value or "",
                "read_only": self.read_only.value.lower() in ("yes", "true", "1"),
                "user_mountable": False,
            }
            await self.ptero.update_mount(self.mount_id, payload)
            e = success_embed(f"Mount `{self.mount_id}` updated.", title="📁 Mount Updated")
            e.color = Colors.MOUNTS
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


def _mount_sel(mounts, ph="Select a mount…"):
    opts = [
        discord.SelectOption(
            label=trunc(m["attributes"]["name"], 100),
            value=str(m["attributes"]["id"]),
            description=f"{m['attributes']['source']} → {m['attributes']['target']}",
        ) for m in mounts[:25]
    ]
    return discord.ui.Select(placeholder=ph, options=opts)


class MountsCog(commands.Cog, name="Mounts"):

    def __init__(self, bot):
        self.bot   = bot
        self.ptero: PterodactylClient = bot.ptero

    mounts_group = app_commands.Group(name="mounts", description="Manage Pterodactyl mounts.")

    @mounts_group.command(name="overview", description="Mounts overview.")
    @is_owner()
    async def mounts_overview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            mounts = await self.ptero.list_mounts()
            ro = sum(1 for m in mounts if m["attributes"].get("read_only"))
            e = make_embed("📁 Mounts Overview", f"**{len(mounts)}** mount(s).", Colors.MOUNTS,
                           fields=[("Total", str(len(mounts)), True),
                                   ("Read-Only", str(ro), True),
                                   ("Read-Write", str(len(mounts) - ro), True)])
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @mounts_group.command(name="list", description="List all mounts.")
    @is_owner()
    async def mounts_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            mounts = await self.ptero.list_mounts()
            if not mounts:
                await interaction.followup.send(embed=warning_embed("No mounts found."), ephemeral=True)
                return
            e = make_embed("📁 All Mounts", f"Found **{len(mounts)}** mount(s):", Colors.MOUNTS)
            for m in mounts[:15]:
                a = m["attributes"]
                e.add_field(name=f"[{a['id']}] {a['name']}",
                            value=f"`{a['source']}` → `{a['target']}`\nRO: {'Yes' if a.get('read_only') else 'No'}",
                            inline=True)
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @mounts_group.command(name="create", description="Create a new mount.")
    @is_owner()
    async def mounts_create(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateMountModal(self.ptero))

    @mounts_group.command(name="edit", description="Edit a mount.")
    @is_owner()
    async def mounts_edit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            mounts = await self.ptero.list_mounts()
            if not mounts:
                await interaction.followup.send(embed=warning_embed("No mounts."), ephemeral=True)
                return
            sel = _mount_sel(mounts)

            async def on_sel(inter: discord.Interaction):
                mid   = int(inter.data["values"][0])
                mount = await self.ptero.get_mount(mid)
                await inter.response.send_modal(EditMountModal(self.ptero, mid, mount["attributes"]))

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(embed=make_embed("📁 Edit Mount", "Select:", Colors.MOUNTS),
                                            view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @mounts_group.command(name="delete", description="Delete a mount.")
    @is_owner()
    async def mounts_delete(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            mounts = await self.ptero.list_mounts()
            if not mounts:
                await interaction.followup.send(embed=warning_embed("No mounts."), ephemeral=True)
                return
            sel = _mount_sel(mounts)

            async def on_sel(inter: discord.Interaction):
                mid  = int(inter.data["values"][0])
                conf = ConfirmView()
                await inter.response.send_message(embed=warning_embed(f"Delete mount `{mid}`?"),
                                                   view=conf, ephemeral=True)
                await conf.wait()
                if conf.confirmed:
                    try:
                        await self.ptero.delete_mount(mid)
                        res = success_embed(f"Mount `{mid}` deleted.", title="📁 Deleted")
                        res.color = Colors.MOUNTS
                    except PterodactylError as ex2:
                        res = error_embed(ex2.message)
                    await inter.edit_original_response(embed=res, view=None)
                else:
                    await inter.edit_original_response(embed=warning_embed("Cancelled."), view=None)

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(embed=make_embed("📁 Delete Mount", "Select:", Colors.MOUNTS),
                                            view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    async def _show_rel(self, interaction: discord.Interaction, rel_key: str, title: str):
        await interaction.response.defer(ephemeral=True)
        try:
            mounts = await self.ptero.list_mounts()
            if not mounts:
                await interaction.followup.send(embed=warning_embed("No mounts."), ephemeral=True)
                return
            sel = _mount_sel(mounts)

            async def on_sel(inter: discord.Interaction):
                mid   = int(inter.data["values"][0])
                await inter.response.defer(ephemeral=True)
                mount = await self.ptero.get_mount(mid)
                attr  = mount.get("attributes", {})
                items = mount.get("relationships", {}).get(rel_key, {}).get("data", [])
                e = make_embed(f"📁 {title} — {attr.get('name', '')}", f"**{len(items)}** attached.", Colors.MOUNTS)
                for it in items[:15]:
                    ia   = it.get("attributes", {})
                    name = (ia.get("name") or
                            f"{ia.get('ip', '')}:{ia.get('port', '')}" or
                            str(ia.get("id", "?")))
                    e.add_field(name=name, value=f"ID `{ia.get('id', '?')}`", inline=True)
                await inter.followup.send(embed=e, ephemeral=True)

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(
                embed=make_embed(f"📁 Mount {title}", "Select a mount:", Colors.MOUNTS),
                view=view, ephemeral=True,
            )
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @mounts_group.command(name="servers", description="View servers attached to a mount.")
    @is_owner()
    async def mounts_servers(self, interaction: discord.Interaction):
        await self._show_rel(interaction, "servers", "Servers")

    @mounts_group.command(name="nodes", description="View nodes attached to a mount.")
    @is_owner()
    async def mounts_nodes(self, interaction: discord.Interaction):
        await self._show_rel(interaction, "nodes", "Nodes")

    @mounts_group.command(name="eggs", description="View eggs attached to a mount.")
    @is_owner()
    async def mounts_eggs(self, interaction: discord.Interaction):
        await self._show_rel(interaction, "eggs", "Eggs")


async def setup(bot):
    await bot.add_cog(MountsCog(bot))
