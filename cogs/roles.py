"""cogs/roles.py  –  /roles command group."""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from api_client import PterodactylClient, PterodactylError
from config import Colors
from cogs.utils import is_owner, make_embed, error_embed, success_embed, warning_embed, trunc, ConfirmView


class CreateRoleModal(discord.ui.Modal, title="Create Role"):
    name = discord.ui.TextInput(label="Role Name", placeholder="Support Staff")
    desc = discord.ui.TextInput(label="Description", required=False, style=discord.TextStyle.paragraph)

    def __init__(self, ptero):
        super().__init__()
        self.ptero = ptero

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            r = await self.ptero.create_role({"name": self.name.value, "description": self.desc.value or ""})
            a = r["attributes"]
            e = success_embed(f"Role **{a['name']}** (ID `{a['id']}`) created.", title="🛡️ Role Created")
            e.color = Colors.ROLES
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


class EditRoleModal(discord.ui.Modal, title="Edit Role"):
    name = discord.ui.TextInput(label="Role Name")
    desc = discord.ui.TextInput(label="Description", required=False, style=discord.TextStyle.paragraph)

    def __init__(self, ptero, rid, current):
        super().__init__()
        self.ptero = ptero
        self.rid = rid
        self.name.default = current.get("name", "")
        self.desc.default = current.get("description", "")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.ptero.update_role(self.rid, {"name": self.name.value, "description": self.desc.value or ""})
            e = success_embed(f"Role `{self.rid}` updated.", title="🛡️ Role Updated")
            e.color = Colors.ROLES
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


class RolesCog(commands.Cog, name="Roles"):

    def __init__(self, bot):
        self.bot = bot
        self.ptero: PterodactylClient = bot.ptero

    roles_group = app_commands.Group(name="roles", description="Manage Pterodactyl admin roles.")

    @roles_group.command(name="overview", description="Roles overview.")
    @is_owner()
    async def roles_overview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            roles = await self.ptero.list_roles()
            e = make_embed("🛡️ Roles Overview", f"**{len(roles)}** role(s).", Colors.ROLES,
                           fields=[("Total", str(len(roles)), True)])
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @roles_group.command(name="list", description="List all admin roles.")
    @is_owner()
    async def roles_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            roles = await self.ptero.list_roles()
            if not roles:
                await interaction.followup.send(embed=warning_embed("No roles found."), ephemeral=True)
                return
            e = make_embed("🛡️ All Roles", f"Found **{len(roles)}** role(s):", Colors.ROLES)
            for r in roles:
                a = r["attributes"]
                e.add_field(name=f"[{a['id']}] {a['name']}",
                            value=trunc(a.get("description") or "No description.", 256), inline=True)
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @roles_group.command(name="create", description="Create a new admin role.")
    @is_owner()
    async def roles_create(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateRoleModal(self.ptero))

    @roles_group.command(name="edit", description="Edit an existing role.")
    @is_owner()
    async def roles_edit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            roles = await self.ptero.list_roles()
            if not roles:
                await interaction.followup.send(embed=warning_embed("No roles."), ephemeral=True)
                return
            opts = [discord.SelectOption(label=trunc(r["attributes"]["name"], 100),
                    value=str(r["attributes"]["id"])) for r in roles[:25]]
            sel = discord.ui.Select(placeholder="Select a role to edit…", options=opts)

            async def on_sel(inter: discord.Interaction):
                rid = int(inter.data["values"][0])
                role = await self.ptero.get_role(rid)
                await inter.response.send_modal(EditRoleModal(self.ptero, rid, role["attributes"]))

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🛡️ Edit Role", "Select:", Colors.ROLES),
                                            view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @roles_group.command(name="delete", description="Delete a role.")
    @is_owner()
    async def roles_delete(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            roles = await self.ptero.list_roles()
            if not roles:
                await interaction.followup.send(embed=warning_embed("No roles."), ephemeral=True)
                return
            opts = [discord.SelectOption(label=trunc(r["attributes"]["name"], 100),
                    value=str(r["attributes"]["id"])) for r in roles[:25]]
            sel = discord.ui.Select(placeholder="Select a role to delete…", options=opts)

            async def on_sel(inter: discord.Interaction):
                rid = int(inter.data["values"][0])
                conf = ConfirmView()
                await inter.response.send_message(embed=warning_embed(f"Delete role `{rid}`?"),
                                                   view=conf, ephemeral=True)
                await conf.wait()
                if conf.confirmed:
                    try:
                        await self.ptero.delete_role(rid)
                        res = success_embed(f"Role `{rid}` deleted.", title="🛡️ Deleted")
                        res.color = Colors.ROLES
                    except PterodactylError as ex2:
                        res = error_embed(ex2.message)
                    await inter.edit_original_response(embed=res, view=None)
                else:
                    await inter.edit_original_response(embed=warning_embed("Cancelled."), view=None)

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🛡️ Delete Role", "Select:", Colors.ROLES),
                                            view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


async def setup(bot):
    await bot.add_cog(RolesCog(bot))
