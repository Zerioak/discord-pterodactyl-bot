"""cogs/database_hosts.py  –  /database-hosts command group."""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from api_client import PterodactylClient, PterodactylError
from config import Colors
from cogs.utils import is_owner, make_embed, error_embed, success_embed, warning_embed, trunc, ConfirmView


class CreateDBModal(discord.ui.Modal, title="Create Database Host"):
    name     = discord.ui.TextInput(label="Name",     placeholder="MySQL Host 1")
    host     = discord.ui.TextInput(label="Hostname", placeholder="127.0.0.1")
    port     = discord.ui.TextInput(label="Port",     placeholder="3306")
    username = discord.ui.TextInput(label="Username", placeholder="pterodactyl")
    password = discord.ui.TextInput(label="Password", required=False)

    def __init__(self, ptero):
        super().__init__()
        self.ptero = ptero

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            p: dict = {
                "name": self.name.value, "host": self.host.value,
                "port": int(self.port.value), "username": self.username.value,
            }
            if self.password.value:
                p["password"] = self.password.value
            r = await self.ptero.create_database_host(p)
            a = r["attributes"]
            e = success_embed(f"DB host **{a['name']}** (ID `{a['id']}`) created.", title="🗄️ DB Host Created")
            e.color = Colors.DB_HOSTS
            await interaction.followup.send(embed=e, ephemeral=True)
        except ValueError:
            await interaction.followup.send(embed=error_embed("Port must be a number."), ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


class EditDBModal(discord.ui.Modal, title="Edit Database Host"):
    name     = discord.ui.TextInput(label="Name")
    host     = discord.ui.TextInput(label="Hostname")
    port     = discord.ui.TextInput(label="Port")
    username = discord.ui.TextInput(label="Username")
    password = discord.ui.TextInput(label="Password (blank = keep)", required=False)

    def __init__(self, ptero, hid, current):
        super().__init__()
        self.ptero = ptero
        self.hid   = hid
        self.name.default     = current.get("name", "")
        self.host.default     = current.get("host", "")
        self.port.default     = str(current.get("port", "3306"))
        self.username.default = current.get("username", "")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            p: dict = {
                "name": self.name.value, "host": self.host.value,
                "port": int(self.port.value), "username": self.username.value,
            }
            if self.password.value:
                p["password"] = self.password.value
            await self.ptero.update_database_host(self.hid, p)
            e = success_embed(f"DB host `{self.hid}` updated.", title="🗄️ DB Host Updated")
            e.color = Colors.DB_HOSTS
            await interaction.followup.send(embed=e, ephemeral=True)
        except ValueError:
            await interaction.followup.send(embed=error_embed("Port must be a number."), ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


def _host_sel(hosts, ph="Select a database host…"):
    opts = [
        discord.SelectOption(
            label=trunc(h["attributes"]["name"], 100),
            value=str(h["attributes"]["id"]),
            description=f"{h['attributes']['host']}:{h['attributes']['port']}",
        ) for h in hosts[:25]
    ]
    return discord.ui.Select(placeholder=ph, options=opts)


class DatabaseHostsCog(commands.Cog, name="DatabaseHosts"):

    def __init__(self, bot):
        self.bot   = bot
        self.ptero: PterodactylClient = bot.ptero

    db_group = app_commands.Group(name="database-hosts", description="Manage database hosts.")

    @db_group.command(name="overview", description="Database hosts overview.")
    @is_owner()
    async def db_overview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            hosts = await self.ptero.list_database_hosts()
            e = make_embed("🗄️ DB Hosts Overview", f"**{len(hosts)}** host(s).", Colors.DB_HOSTS,
                           fields=[("Total", str(len(hosts)), True)])
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @db_group.command(name="list", description="List all database hosts.")
    @is_owner()
    async def db_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            hosts = await self.ptero.list_database_hosts()
            if not hosts:
                await interaction.followup.send(embed=warning_embed("No database hosts found."), ephemeral=True)
                return
            e = make_embed("🗄️ Database Hosts", f"Found **{len(hosts)}** host(s):", Colors.DB_HOSTS)
            for h in hosts:
                a = h["attributes"]
                e.add_field(name=f"[{a['id']}] {a['name']}",
                            value=f"**Host:** {a['host']}:{a['port']}\n**User:** {a['username']}", inline=True)
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @db_group.command(name="create", description="Create a new database host.")
    @is_owner()
    async def db_create(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateDBModal(self.ptero))

    @db_group.command(name="edit", description="Edit a database host.")
    @is_owner()
    async def db_edit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            hosts = await self.ptero.list_database_hosts()
            if not hosts:
                await interaction.followup.send(embed=warning_embed("No hosts."), ephemeral=True)
                return
            sel = _host_sel(hosts)

            async def on_sel(inter: discord.Interaction):
                hid = int(inter.data["values"][0])
                h   = await self.ptero.get_database_host(hid)
                await inter.response.send_modal(EditDBModal(self.ptero, hid, h["attributes"]))

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🗄️ Edit DB Host", "Select:", Colors.DB_HOSTS),
                                            view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @db_group.command(name="delete", description="Delete a database host.")
    @is_owner()
    async def db_delete(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            hosts = await self.ptero.list_database_hosts()
            if not hosts:
                await interaction.followup.send(embed=warning_embed("No hosts."), ephemeral=True)
                return
            sel = _host_sel(hosts)

            async def on_sel(inter: discord.Interaction):
                hid  = int(inter.data["values"][0])
                conf = ConfirmView()
                await inter.response.send_message(embed=warning_embed(f"Delete DB host `{hid}`?"),
                                                   view=conf, ephemeral=True)
                await conf.wait()
                if conf.confirmed:
                    try:
                        await self.ptero.delete_database_host(hid)
                        res = success_embed(f"DB host `{hid}` deleted.", title="🗄️ Deleted")
                        res.color = Colors.DB_HOSTS
                    except PterodactylError as ex2:
                        res = error_embed(ex2.message)
                    await inter.edit_original_response(embed=res, view=None)
                else:
                    await inter.edit_original_response(embed=warning_embed("Cancelled."), view=None)

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🗄️ Delete DB Host", "Select:", Colors.DB_HOSTS),
                                            view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @db_group.command(name="databases", description="List server databases on a host.")
    @is_owner()
    async def db_databases(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            hosts   = await self.ptero.list_database_hosts()
            servers = await self.ptero.list_servers()
            if not hosts:
                await interaction.followup.send(embed=warning_embed("No hosts."), ephemeral=True)
                return
            sel = _host_sel(hosts)

            async def on_sel(inter: discord.Interaction):
                hid = int(inter.data["values"][0])
                await inter.response.defer(ephemeral=True)
                all_dbs = []
                for srv in servers:
                    dbs = await self.ptero.list_server_databases(srv["attributes"]["id"])
                    for db in dbs:
                        if db["attributes"].get("host", {}).get("id") == hid:
                            all_dbs.append((srv["attributes"]["name"], db["attributes"]))
                e = make_embed(f"🗄️ Databases on Host {hid}", f"**{len(all_dbs)}** database(s).", Colors.DB_HOSTS)
                for sname, db in all_dbs[:15]:
                    e.add_field(name=db.get("name", "?"),
                                value=f"Server: **{sname}**\nUser: `{db.get('username','N/A')}`", inline=True)
                await inter.followup.send(embed=e, ephemeral=True)

            sel.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🗄️ Databases by Host", "Select a host:", Colors.DB_HOSTS),
                                            view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


async def setup(bot):
    await bot.add_cog(DatabaseHostsCog(bot))
