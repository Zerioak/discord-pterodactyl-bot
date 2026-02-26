"""cogs/users.py  –  /users command group."""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from api_client import PterodactylClient, PterodactylError
from config import Colors
from cogs.utils import is_owner, make_embed, error_embed, success_embed, warning_embed, trunc, ConfirmView


class CreateUserModal(discord.ui.Modal, title="Create User"):
    email      = discord.ui.TextInput(label="Email",      placeholder="user@example.com")
    username   = discord.ui.TextInput(label="Username",   placeholder="johndoe")
    first_name = discord.ui.TextInput(label="First Name", placeholder="John")
    last_name  = discord.ui.TextInput(label="Last Name",  placeholder="Doe")
    password   = discord.ui.TextInput(label="Password")

    def __init__(self, ptero):
        super().__init__()
        self.ptero = ptero

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            r = await self.ptero.create_user({
                "email": self.email.value, "username": self.username.value,
                "first_name": self.first_name.value, "last_name": self.last_name.value,
                "password": self.password.value,
            })
            a = r["attributes"]
            e = success_embed(f"User **{a['username']}** (ID `{a['id']}`) created.", title="👤 User Created")
            e.color = Colors.USERS
            e.add_field(name="Email", value=a["email"], inline=True)
            e.add_field(name="Admin", value="✅" if a.get("root_admin") else "❌", inline=True)
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


class EditUserModal(discord.ui.Modal, title="Edit User"):
    email      = discord.ui.TextInput(label="Email")
    username   = discord.ui.TextInput(label="Username")
    first_name = discord.ui.TextInput(label="First Name")
    last_name  = discord.ui.TextInput(label="Last Name")
    password   = discord.ui.TextInput(label="New Password (blank = keep)", required=False)

    def __init__(self, ptero, uid, current):
        super().__init__()
        self.ptero = ptero
        self.uid = uid
        self.email.default      = current.get("email", "")
        self.username.default   = current.get("username", "")
        self.first_name.default = current.get("first_name", "")
        self.last_name.default  = current.get("last_name", "")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            p: dict = {
                "email": self.email.value, "username": self.username.value,
                "first_name": self.first_name.value, "last_name": self.last_name.value,
            }
            if self.password.value:
                p["password"] = self.password.value
            await self.ptero.update_user(self.uid, p)
            e = success_embed(f"User `{self.uid}` updated.", title="👤 User Updated")
            e.color = Colors.USERS
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


def _user_sel(users, ph="Select a user…"):
    opts = [
        discord.SelectOption(
            label=trunc(f"{u['attributes']['first_name']} {u['attributes']['last_name']}", 100),
            value=str(u["attributes"]["id"]),
            description=trunc(u["attributes"]["email"], 100),
        ) for u in users[:25]
    ]
    return discord.ui.Select(placeholder=ph, options=opts)


class UsersCog(commands.Cog, name="Users"):

    def __init__(self, bot):
        self.bot = bot
        self.ptero: PterodactylClient = bot.ptero

    users_group = app_commands.Group(name="users", description="Manage Pterodactyl users.")

    @users_group.command(name="overview", description="Users overview statistics.")
    @is_owner()
    async def users_overview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            users = await self.ptero.list_users()
            admins = sum(1 for u in users if u["attributes"].get("root_admin"))
            e = make_embed("👤 Users Overview", f"**{len(users)}** user(s) registered.", Colors.USERS,
                           fields=[("Total", str(len(users)), True),
                                   ("Admins", str(admins), True),
                                   ("Regular", str(len(users) - admins), True)])
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @users_group.command(name="list", description="List all panel users.")
    @is_owner()
    async def users_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            users = await self.ptero.list_users()
            if not users:
                await interaction.followup.send(embed=warning_embed("No users found."), ephemeral=True)
                return
            e = make_embed("👤 All Users", f"Found **{len(users)}** user(s):", Colors.USERS)
            for u in users[:15]:
                a = u["attributes"]
                e.add_field(
                    name=f"[{a['id']}] {a['username']}",
                    value=f"**Email:** {a['email']}\n**Name:** {a['first_name']} {a['last_name']}\n**Admin:** {'✅' if a.get('root_admin') else '❌'}",
                    inline=True,
                )
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @users_group.command(name="create", description="Create a new panel user.")
    @is_owner()
    async def users_create(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateUserModal(self.ptero))

    @users_group.command(name="edit", description="Edit a user's details.")
    @is_owner()
    async def users_edit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            users = await self.ptero.list_users()
            if not users:
                await interaction.followup.send(embed=warning_embed("No users."), ephemeral=True)
                return
            sel = _user_sel(users, "Select a user to edit…")

            async def on_sel(inter: discord.Interaction):
                uid = int(inter.data["values"][0])
                u   = await self.ptero.get_user(uid)
                await inter.response.send_modal(EditUserModal(self.ptero, uid, u["attributes"]))

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(embed=make_embed("👤 Edit User", "Select:", Colors.USERS),
                                            view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @users_group.command(name="delete", description="Delete a panel user.")
    @is_owner()
    async def users_delete(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            users = await self.ptero.list_users()
            if not users:
                await interaction.followup.send(embed=warning_embed("No users."), ephemeral=True)
                return
            sel = _user_sel(users, "Select a user to delete…")

            async def on_sel(inter: discord.Interaction):
                uid  = int(inter.data["values"][0])
                conf = ConfirmView()
                await inter.response.send_message(embed=warning_embed(f"Delete user `{uid}`? This is permanent."),
                                                   view=conf, ephemeral=True)
                await conf.wait()
                if conf.confirmed:
                    try:
                        await self.ptero.delete_user(uid)
                        res = success_embed(f"User `{uid}` deleted.", title="👤 Deleted")
                        res.color = Colors.USERS
                    except PterodactylError as ex2:
                        res = error_embed(ex2.message)
                    await inter.edit_original_response(embed=res, view=None)
                else:
                    await inter.edit_original_response(embed=warning_embed("Cancelled."), view=None)

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(embed=make_embed("👤 Delete User", "Select:", Colors.USERS),
                                            view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @users_group.command(name="roles", description="Toggle admin role for a user.")
    @is_owner()
    async def users_roles(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            users = await self.ptero.list_users()
            if not users:
                await interaction.followup.send(embed=warning_embed("No users."), ephemeral=True)
                return
            sel = _user_sel(users, "Toggle admin for user…")

            async def on_sel(inter: discord.Interaction):
                uid = int(inter.data["values"][0])
                await inter.response.defer(ephemeral=True)
                u         = await self.ptero.get_user(uid)
                a         = u["attributes"]
                new_admin = not a.get("root_admin", False)
                await self.ptero.update_user(uid, {
                    "email": a["email"], "username": a["username"],
                    "first_name": a["first_name"], "last_name": a["last_name"],
                    "root_admin": new_admin,
                })
                status = "promoted to **Admin**" if new_admin else "demoted to **Regular User**"
                e = success_embed(f"User `{a['username']}` {status}.", title="👤 Role Updated")
                e.color = Colors.USERS
                await inter.followup.send(embed=e, ephemeral=True)

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(embed=make_embed("👤 Toggle Admin", "Select a user:", Colors.USERS),
                                            view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @users_group.command(name="servers", description="List servers owned by a user.")
    @is_owner()
    async def users_servers(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            users = await self.ptero.list_users()
            if not users:
                await interaction.followup.send(embed=warning_embed("No users."), ephemeral=True)
                return
            sel = _user_sel(users, "Select a user…")

            async def on_sel(inter: discord.Interaction):
                uid     = int(inter.data["values"][0])
                await inter.response.defer(ephemeral=True)
                servers = await self.ptero.list_servers()
                owned   = [s for s in servers if s["attributes"].get("user") == uid]
                e = make_embed(f"👤 Servers for User {uid}", f"**{len(owned)}** server(s).", Colors.USERS)
                for s in owned[:15]:
                    a = s["attributes"]
                    e.add_field(name=f"[{a['id']}] {a['name']}", value=f"`{a['uuid'][:8]}…`", inline=True)
                await inter.followup.send(embed=e, ephemeral=True)

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(embed=make_embed("👤 User Servers", "Select:", Colors.USERS),
                                            view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


async def setup(bot):
    await bot.add_cog(UsersCog(bot))
