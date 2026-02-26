"""
cogs/nodes.py  –  /nodes command group.
Subcommands: overview, list, create, edit, delete,
             allocations, servers, create-allocations, delete-allocations
"""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from api_client import PterodactylClient, PterodactylError
from config import Colors
from cogs.utils import is_owner, make_embed, error_embed, success_embed, warning_embed, trunc, fmt_bytes, ConfirmView


# ── Modals ───────────────────────────────────────────────────────────────────────
class CreateNodeModal(discord.ui.Modal, title="Create Node"):
    name        = discord.ui.TextInput(label="Name",             placeholder="US-East-1")
    location_id = discord.ui.TextInput(label="Location ID",      placeholder="1")
    fqdn        = discord.ui.TextInput(label="FQDN / IP",        placeholder="node.example.com")
    memory      = discord.ui.TextInput(label="Total Memory (MB)", placeholder="16384")
    disk        = discord.ui.TextInput(label="Total Disk (MB)",  placeholder="102400")

    def __init__(self, ptero):
        super().__init__()
        self.ptero = ptero

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            payload = {
                "name": self.name.value, "location_id": int(self.location_id.value),
                "fqdn": self.fqdn.value, "scheme": "https",
                "memory": int(self.memory.value), "memory_overallocate": 0,
                "disk":   int(self.disk.value),   "disk_overallocate":   0,
                "daemonSftp": 2022, "daemonListen": 8080,
            }
            result = await self.ptero.create_node(payload)
            attr   = result["attributes"]
            e = success_embed(f"Node **{attr['name']}** (ID `{attr['id']}`) created.", title="🖥️ Node Created")
            e.color = Colors.NODES
            await interaction.followup.send(embed=e, ephemeral=True)
        except ValueError:
            await interaction.followup.send(embed=error_embed("Location ID, Memory and Disk must be numbers."), ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


class EditNodeModal(discord.ui.Modal, title="Edit Node"):
    name   = discord.ui.TextInput(label="Name")
    fqdn   = discord.ui.TextInput(label="FQDN / IP")
    memory = discord.ui.TextInput(label="Total Memory (MB)")
    disk   = discord.ui.TextInput(label="Total Disk (MB)")

    def __init__(self, ptero, node_id, current):
        super().__init__()
        self.ptero   = ptero
        self.node_id = node_id
        self._loc_id = current.get("location_id", 1)
        self.name.default   = current.get("name", "")
        self.fqdn.default   = current.get("fqdn", "")
        self.memory.default = str(current.get("memory", ""))
        self.disk.default   = str(current.get("disk", ""))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            payload = {
                "name": self.name.value, "location_id": self._loc_id,
                "fqdn": self.fqdn.value, "scheme": "https",
                "memory": int(self.memory.value), "memory_overallocate": 0,
                "disk":   int(self.disk.value),   "disk_overallocate":   0,
                "daemonSftp": 2022, "daemonListen": 8080,
            }
            await self.ptero.update_node(self.node_id, payload)
            e = success_embed(f"Node `{self.node_id}` updated.", title="🖥️ Node Updated")
            e.color = Colors.NODES
            await interaction.followup.send(embed=e, ephemeral=True)
        except ValueError:
            await interaction.followup.send(embed=error_embed("Memory and Disk must be numbers."), ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


class CreateAllocationsModal(discord.ui.Modal, title="Create Allocations"):
    ip    = discord.ui.TextInput(label="IP Address", placeholder="0.0.0.0")
    ports = discord.ui.TextInput(label="Ports (comma-sep or range 25565-25580)", placeholder="25565, 25566, 25570-25580", style=discord.TextStyle.paragraph)
    alias = discord.ui.TextInput(label="IP Alias (optional)", required=False, placeholder="play.example.com")

    def __init__(self, ptero, node_id):
        super().__init__()
        self.ptero   = ptero
        self.node_id = node_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            port_list = []
            for part in self.ports.value.replace(" ", "").split(","):
                if "-" in part:
                    s, e = part.split("-", 1)
                    port_list.extend(str(p) for p in range(int(s), int(e) + 1))
                else:
                    if part:
                        port_list.append(part)
            payload = {"ip": self.ip.value, "ports": port_list}
            if self.alias.value:
                payload["alias"] = self.alias.value
            await self.ptero.create_allocation(self.node_id, payload)
            e = success_embed(f"Created **{len(port_list)}** allocation(s) on node `{self.node_id}`.", title="🖥️ Allocations Created")
            e.color = Colors.NODES
            await interaction.followup.send(embed=e, ephemeral=True)
        except (ValueError, TypeError):
            await interaction.followup.send(embed=error_embed("Invalid port format."), ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


# ── Node select view ──────────────────────────────────────────────────────────────
def _node_select(nodes, placeholder="Select a node…"):
    opts = [
        discord.SelectOption(
            label=trunc(n["attributes"]["name"], 100),
            value=str(n["attributes"]["id"]),
            description=n["attributes"]["fqdn"],
        ) for n in nodes[:25]
    ]
    return discord.ui.Select(placeholder=placeholder, options=opts)


# ── Cog ───────────────────────────────────────────────────────────────────────────
class NodesCog(commands.Cog, name="Nodes"):
    def __init__(self, bot):
        self.bot   = bot
        self.ptero: PterodactylClient = bot.ptero

    nodes_group = app_commands.Group(name="nodes", description="Manage Pterodactyl nodes.")

    @nodes_group.command(name="overview", description="Node statistics overview.")
    @is_owner()
    async def nodes_overview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nodes = await self.ptero.list_nodes()
            total_mem  = sum(n["attributes"]["memory"] for n in nodes)
            total_disk = sum(n["attributes"]["disk"]   for n in nodes)
            e = make_embed("🖥️ Nodes Overview", f"**{len(nodes)}** node(s) configured.", Colors.NODES,
                           fields=[("Total Nodes", str(len(nodes)), True), ("Total Memory", fmt_bytes(total_mem), True), ("Total Disk", fmt_bytes(total_disk), True)])
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @nodes_group.command(name="list", description="List all nodes.")
    @is_owner()
    async def nodes_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nodes = await self.ptero.list_nodes()
            if not nodes:
                await interaction.followup.send(embed=warning_embed("No nodes found."), ephemeral=True)
                return
            e = make_embed("🖥️ All Nodes", f"Found **{len(nodes)}** node(s):", Colors.NODES)
            for n in nodes[:15]:
                a = n["attributes"]
                e.add_field(name=f"[{a['id']}] {a['name']}",
                    value=f"**FQDN:** {a['fqdn']}\n**Memory:** {fmt_bytes(a['memory'])} | **Disk:** {fmt_bytes(a['disk'])}", inline=True)
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @nodes_group.command(name="create", description="Create a new node.")
    @is_owner()
    async def nodes_create(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateNodeModal(self.ptero))

    @nodes_group.command(name="edit", description="Edit a node.")
    @is_owner()
    async def nodes_edit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nodes = await self.ptero.list_nodes()
            if not nodes:
                await interaction.followup.send(embed=warning_embed("No nodes available."), ephemeral=True)
                return
            sel = _node_select(nodes, "Select a node to edit…")
            async def on_sel(inter):
                nid  = int(inter.data["values"][0])
                node = await self.ptero.get_node(nid)
                await inter.response.send_modal(EditNodeModal(self.ptero, nid, node["attributes"]))
            sel.callback = on_sel
            view = discord.ui.View(timeout=60); view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🖥️ Edit Node", "Select a node:", Colors.NODES), view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @nodes_group.command(name="delete", description="Delete a node.")
    @is_owner()
    async def nodes_delete(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nodes = await self.ptero.list_nodes()
            if not nodes:
                await interaction.followup.send(embed=warning_embed("No nodes available."), ephemeral=True)
                return
            sel = _node_select(nodes, "Select a node to delete…")
            async def on_sel(inter):
                nid  = int(inter.data["values"][0])
                conf = ConfirmView()
                await inter.response.send_message(embed=warning_embed(f"Delete node `{nid}`? This is irreversible.", title="⚠️ Confirm"), view=conf, ephemeral=True)
                await conf.wait()
                if conf.confirmed:
                    try:
                        await self.ptero.delete_node(nid)
                        res = success_embed(f"Node `{nid}` deleted.", title="🖥️ Node Deleted"); res.color = Colors.NODES
                    except PterodactylError as ex2:
                        res = error_embed(ex2.message)
                    await inter.edit_original_response(embed=res, view=None)
                else:
                    await inter.edit_original_response(embed=warning_embed("Cancelled."), view=None)
            sel.callback = on_sel
            view = discord.ui.View(timeout=60); view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🖥️ Delete Node", "Select a node:", Colors.NODES), view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @nodes_group.command(name="allocations", description="View allocations for a node.")
    @is_owner()
    async def nodes_allocations(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nodes = await self.ptero.list_nodes()
            if not nodes:
                await interaction.followup.send(embed=warning_embed("No nodes found."), ephemeral=True)
                return
            sel = _node_select(nodes, "Select a node…")
            async def on_sel(inter):
                nid    = int(inter.data["values"][0])
                await inter.response.defer(ephemeral=True)
                allocs = await self.ptero.list_allocations(nid)
                e = make_embed(f"🖥️ Allocations — Node {nid}", f"**{len(allocs)}** allocation(s):", Colors.NODES)
                for a in allocs[:20]:
                    aa = a["attributes"]
                    e.add_field(name=f"{aa['ip']}:{aa['port']}", value=f"ID `{aa['id']}` | {'🔴 Used' if aa.get('assigned') else '🟢 Free'}", inline=True)
                await inter.followup.send(embed=e, ephemeral=True)
            sel.callback = on_sel
            view = discord.ui.View(timeout=60); view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🖥️ Node Allocations", "Select a node:", Colors.NODES), view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @nodes_group.command(name="servers", description="List servers on a node.")
    @is_owner()
    async def nodes_servers(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nodes = await self.ptero.list_nodes()
            if not nodes:
                await interaction.followup.send(embed=warning_embed("No nodes found."), ephemeral=True)
                return
            sel = _node_select(nodes, "Select a node…")
            async def on_sel(inter):
                nid     = int(inter.data["values"][0])
                await inter.response.defer(ephemeral=True)
                servers = await self.ptero.list_servers()
                ns      = [s for s in servers if s["attributes"].get("node") == nid]
                e = make_embed(f"🖥️ Servers on Node {nid}", f"**{len(ns)}** server(s):", Colors.NODES)
                for s in ns[:15]:
                    a = s["attributes"]
                    e.add_field(name=f"[{a['id']}] {a['name']}", value=f"`{a['uuid'][:8]}…`", inline=True)
                await inter.followup.send(embed=e, ephemeral=True)
            sel.callback = on_sel
            view = discord.ui.View(timeout=60); view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🖥️ Node Servers", "Select a node:", Colors.NODES), view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @nodes_group.command(name="create-allocations", description="Add allocations to a node.")
    @is_owner()
    async def nodes_create_allocations(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nodes = await self.ptero.list_nodes()
            if not nodes:
                await interaction.followup.send(embed=warning_embed("No nodes available."), ephemeral=True)
                return
            sel = _node_select(nodes, "Select a node…")
            async def on_sel(inter):
                nid = int(inter.data["values"][0])
                await inter.response.send_modal(CreateAllocationsModal(self.ptero, nid))
            sel.callback = on_sel
            view = discord.ui.View(timeout=60); view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🖥️ Create Allocations", "Select a node:", Colors.NODES), view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)

    @nodes_group.command(name="delete-allocations", description="Remove free allocations from a node.")
    @is_owner()
    async def nodes_delete_allocations(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            nodes = await self.ptero.list_nodes()
            if not nodes:
                await interaction.followup.send(embed=warning_embed("No nodes available."), ephemeral=True)
                return
            sel = _node_select(nodes, "Select a node first…")
            async def on_node(inter):
                nid    = int(inter.data["values"][0])
                await inter.response.defer(ephemeral=True)
                allocs = await self.ptero.list_allocations(nid)
                free   = [a for a in allocs if not a["attributes"].get("assigned")]
                if not free:
                    await inter.followup.send(embed=warning_embed("No free allocations on this node."), ephemeral=True)
                    return
                opts = [discord.SelectOption(label=f"{a['attributes']['ip']}:{a['attributes']['port']}", value=str(a["attributes"]["id"])) for a in free[:25]]
                asel = discord.ui.Select(placeholder="Select allocation to remove…", options=opts)
                async def on_alloc(ai):
                    aid = int(ai.data["values"][0])
                    await ai.response.defer(ephemeral=True)
                    try:
                        await self.ptero.delete_allocation(nid, aid)
                        res = success_embed(f"Allocation `{aid}` removed.", title="🖥️ Allocation Deleted"); res.color = Colors.NODES
                    except PterodactylError as ex2:
                        res = error_embed(ex2.message)
                    await ai.followup.send(embed=res, ephemeral=True)
                asel.callback = on_alloc
                av = discord.ui.View(timeout=60); av.add_item(asel)
                await inter.followup.send(embed=make_embed("🖥️ Delete Allocation", "Select:", Colors.NODES), view=av, ephemeral=True)
            sel.callback = on_node
            view = discord.ui.View(timeout=60); view.add_item(sel)
            await interaction.followup.send(embed=make_embed("🖥️ Delete Allocation", "Select a node:", Colors.NODES), view=view, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


async def setup(bot):
    await bot.add_cog(NodesCog(bot))
