"""
cogs/servers.py  –  /servers command group.

Server creation wizard (9 steps):
  Step 1  Modal   – Name, Description, External ID
  Step 2  Select  – Owner (user)
  Step 3  Select  – Node
  Step 4  Select  – Nest  (to filter eggs)
  Step 5  Select  – Egg   (auto-fills startup, env vars)
  Step 5b Select  – Docker Image (shows ONLY images available for that egg)
  Step 6  Select  – Allocation (IP:Port)
  Step 7  Modal   – Resources (memory, disk, cpu, swap, io)
  Step 8  Confirm – Review embed → Create / Cancel
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from api_client import PterodactylClient, PterodactylError
from config import Colors
from cogs.utils import (
    is_owner, make_embed, error_embed, success_embed, warning_embed,
    trunc, fmt_bytes, ConfirmView,
)


# ══════════════════════════════════════════════════════════════════════════════════
# State bag passed through all creation steps
# ══════════════════════════════════════════════════════════════════════════════════
class CreationState:
    __slots__ = (
        "name", "description", "external_id",
        "user_id", "node_id", "nest_id", "egg_id", "egg_name", "alloc_id",
        "docker_image", "docker_images",
        "startup", "env_vars",
        "memory", "disk", "cpu", "swap", "io",
    )

    def __init__(self):
        self.name          = ""
        self.description   = ""
        self.external_id   = ""
        self.user_id       = 0
        self.node_id       = 0
        self.nest_id       = 0
        self.egg_id        = 0
        self.egg_name      = ""
        self.alloc_id      = 0
        # docker
        self.docker_image  = ""
        self.docker_images: dict[str, str] = {}   # {"Display Name": "image:tag"}
        # startup / env
        self.startup       = ""
        self.env_vars: dict[str, str] = {}
        # resources
        self.memory = 1024
        self.disk   = 5120
        self.cpu    = 100
        self.swap   = 0
        self.io     = 500


# ══════════════════════════════════════════════════════════════════════════════════
# STEP 1 — Modal: basic info
# ══════════════════════════════════════════════════════════════════════════════════
class Step1Modal(discord.ui.Modal, title="Create Server — Step 1"):
    name        = discord.ui.TextInput(label="Server Name",            placeholder="My Minecraft Server", max_length=191)
    description = discord.ui.TextInput(label="Description (optional)", placeholder="A fun survival server",
                                       required=False, style=discord.TextStyle.paragraph, max_length=255)
    external_id = discord.ui.TextInput(label="External ID (optional)", placeholder="ext-001",
                                       required=False, max_length=191)

    def __init__(self, ptero: PterodactylClient):
        super().__init__()
        self.ptero = ptero

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        state             = CreationState()
        state.name        = self.name.value.strip()
        state.description = self.description.value.strip()
        state.external_id = self.external_id.value.strip()
        try:
            users = await self.ptero.list_users()
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)
            return
        if not users:
            await interaction.followup.send(embed=error_embed("No panel users found. Create a user first."), ephemeral=True)
            return
        embed = make_embed(
            title="🌐 Create Server — Step 2: Owner",
            description=f"**Server:** {state.name}\nWho will own this server?",
            color=Colors.SERVERS,
        )
        await interaction.followup.send(embed=embed, view=Step2UserSelect(self.ptero, state, users), ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════════
# STEP 2 — Select: user
# ══════════════════════════════════════════════════════════════════════════════════
class Step2UserSelect(discord.ui.View):
    def __init__(self, ptero, state, users):
        super().__init__(timeout=180)
        self.ptero = ptero
        self.state = state
        opts = [
            discord.SelectOption(
                label=trunc(f"{u['attributes']['first_name']} {u['attributes']['last_name']}", 100),
                value=str(u["attributes"]["id"]),
                description=trunc(u["attributes"]["email"], 100),
            ) for u in users[:25]
        ]
        sel = discord.ui.Select(placeholder="Choose server owner…", options=opts)
        sel.callback = self._cb
        self.add_item(sel)

    async def _cb(self, interaction: discord.Interaction):
        self.state.user_id = int(interaction.data["values"][0])
        await interaction.response.defer(ephemeral=True)
        self.stop()
        try:
            nodes = await self.ptero.list_nodes()
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)
            return
        if not nodes:
            await interaction.followup.send(embed=error_embed("No nodes found. Create a node first."), ephemeral=True)
            return
        embed = make_embed(
            title="🌐 Create Server — Step 3: Node",
            description=f"**Server:** {self.state.name}\nWhich node should host this server?",
            color=Colors.SERVERS,
        )
        await interaction.followup.send(embed=embed, view=Step3NodeSelect(self.ptero, self.state, nodes), ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════════
# STEP 3 — Select: node
# ══════════════════════════════════════════════════════════════════════════════════
class Step3NodeSelect(discord.ui.View):
    def __init__(self, ptero, state, nodes):
        super().__init__(timeout=180)
        self.ptero = ptero
        self.state = state
        opts = [
            discord.SelectOption(
                label=trunc(n["attributes"]["name"], 100),
                value=str(n["attributes"]["id"]),
                description=trunc(n["attributes"]["fqdn"], 100),
            ) for n in nodes[:25]
        ]
        sel = discord.ui.Select(placeholder="Choose a node…", options=opts)
        sel.callback = self._cb
        self.add_item(sel)

    async def _cb(self, interaction: discord.Interaction):
        self.state.node_id = int(interaction.data["values"][0])
        await interaction.response.defer(ephemeral=True)
        self.stop()
        try:
            nests = await self.ptero.list_nests()
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)
            return
        if not nests:
            await interaction.followup.send(embed=error_embed("No nests found."), ephemeral=True)
            return
        embed = make_embed(
            title="🌐 Create Server — Step 4: Nest",
            description=f"**Server:** {self.state.name}\nChoose a nest to browse eggs.",
            color=Colors.SERVERS,
        )
        await interaction.followup.send(embed=embed, view=Step4NestSelect(self.ptero, self.state, nests), ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════════
# STEP 4 — Select: nest
# ══════════════════════════════════════════════════════════════════════════════════
class Step4NestSelect(discord.ui.View):
    def __init__(self, ptero, state, nests):
        super().__init__(timeout=180)
        self.ptero = ptero
        self.state = state
        opts = [
            discord.SelectOption(
                label=trunc(n["attributes"]["name"], 100),
                value=str(n["attributes"]["id"]),
                description=trunc(n["attributes"].get("description", ""), 100),
            ) for n in nests[:25]
        ]
        sel = discord.ui.Select(placeholder="Choose a nest…", options=opts)
        sel.callback = self._cb
        self.add_item(sel)

    async def _cb(self, interaction: discord.Interaction):
        nest_id = int(interaction.data["values"][0])
        self.state.nest_id = nest_id
        await interaction.response.defer(ephemeral=True)
        self.stop()
        try:
            eggs = await self.ptero.list_eggs(nest_id)
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)
            return
        if not eggs:
            await interaction.followup.send(embed=error_embed("This nest has no eggs. Choose a different nest."), ephemeral=True)
            return
        embed = make_embed(
            title="🌐 Create Server — Step 5: Egg",
            description=f"**Server:** {self.state.name}\nChoose the game / software egg.",
            color=Colors.SERVERS,
        )
        await interaction.followup.send(embed=embed, view=Step5EggSelect(self.ptero, self.state, eggs), ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════════
# STEP 5 — Select: egg
# Fetches full egg details → stores docker_images dict, startup, env vars
# Then proceeds to Step 5b (Docker Image picker)
# ══════════════════════════════════════════════════════════════════════════════════
class Step5EggSelect(discord.ui.View):
    def __init__(self, ptero, state, eggs):
        super().__init__(timeout=180)
        self.ptero = ptero
        self.state = state
        opts = [
            discord.SelectOption(
                label=trunc(e["attributes"]["name"], 100),
                value=str(e["attributes"]["id"]),
                description=trunc(e["attributes"].get("description", "No description"), 100),
            ) for e in eggs[:25]
        ]
        sel = discord.ui.Select(placeholder="Choose an egg…", options=opts)
        sel.callback = self._cb
        self.add_item(sel)

    async def _cb(self, interaction: discord.Interaction):
        egg_id = int(interaction.data["values"][0])
        self.state.egg_id = egg_id
        await interaction.response.defer(ephemeral=True)
        self.stop()

        # Fetch full egg details (includes docker_images, variables, startup)
        try:
            egg_detail = await self.ptero.get_egg(self.state.nest_id, egg_id)
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(f"Could not load egg details:\n{e.message}"), ephemeral=True)
            return

        attr = egg_detail.get("attributes", {})
        self.state.egg_name = attr.get("name", str(egg_id))

        # ── Collect all available docker images for this egg ────────────────────
        docker_images: dict[str, str] = {}

        # Primary source: docker_images dict  {"Java 17": "ghcr.io/...:java_17", ...}
        raw = attr.get("docker_images", {})
        if isinstance(raw, dict):
            docker_images.update(raw)

        # Fallback: single docker_image field
        if not docker_images and attr.get("docker_image"):
            img = attr["docker_image"]
            # Use the tag part as display name  (e.g. "java_17" from "…:java_17")
            label = img.split(":")[-1] if ":" in img else img
            docker_images[label] = img

        # Very last resort
        if not docker_images:
            docker_images["default"] = "ghcr.io/pterodactyl/yolks:java_17"

        self.state.docker_images = docker_images

        # ── startup command ─────────────────────────────────────────────────────
        self.state.startup = attr.get("startup", "")

        # ── environment variables (pre-fill defaults) ───────────────────────────
        self.state.env_vars = {}
        for v in attr.get("relationships", {}).get("variables", {}).get("data", []):
            va  = v.get("attributes", {})
            key = va.get("env_variable", "")
            val = va.get("default_value", "")
            if key:
                self.state.env_vars[key] = val if val is not None else ""

        # ── Proceed to Docker Image picker ──────────────────────────────────────
        embed = make_embed(
            title="🌐 Create Server — Step 5b: Docker Image",
            description=(
                f"**Server:** {self.state.name}\n"
                f"**Egg:** `{self.state.egg_name}`\n\n"
                f"Choose the Docker image for this egg.\n"
                f"Only images registered for **{self.state.egg_name}** are shown."
            ),
            color=Colors.SERVERS,
        )
        await interaction.followup.send(
            embed=embed,
            view=Step5bDockerSelect(self.ptero, self.state),
            ephemeral=True,
        )


# ══════════════════════════════════════════════════════════════════════════════════
# STEP 5b — Select: Docker Image
# Shows ONLY the images that belong to the chosen egg.
# ══════════════════════════════════════════════════════════════════════════════════
class Step5bDockerSelect(discord.ui.View):
    def __init__(self, ptero, state):
        super().__init__(timeout=180)
        self.ptero = ptero
        self.state = state

        opts = []
        for display_name, image_tag in state.docker_images.items():
            # Shorten image_tag for description (keep last 80 chars)
            short = image_tag if len(image_tag) <= 80 else "…" + image_tag[-79:]
            opts.append(
                discord.SelectOption(
                    label=trunc(display_name, 100),
                    value=image_tag,          # value is the actual image:tag
                    description=short,
                )
            )

        # Discord allows max 25 options per select
        sel = discord.ui.Select(
            placeholder="Choose a Docker image…",
            options=opts[:25],
        )
        sel.callback = self._cb
        self.add_item(sel)

    async def _cb(self, interaction: discord.Interaction):
        self.state.docker_image = interaction.data["values"][0]
        await interaction.response.defer(ephemeral=True)
        self.stop()

        # Fetch free allocations on selected node
        try:
            allocs = await self.ptero.list_allocations(self.state.node_id)
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(f"Could not load allocations:\n{e.message}"), ephemeral=True)
            return

        free = [a for a in allocs if not a["attributes"].get("assigned", False)]
        if not free:
            await interaction.followup.send(
                embed=error_embed(
                    f"No free allocations on node `{self.state.node_id}`.\n"
                    "Use `/nodes create-allocations` to add ports first."
                ),
                ephemeral=True,
            )
            return

        embed = make_embed(
            title="🌐 Create Server — Step 6: Allocation",
            description=(
                f"**Server:** {self.state.name}\n"
                f"**Egg:** `{self.state.egg_name}`\n"
                f"**Image:** `{self.state.docker_image}`\n\n"
                "Choose the IP:Port for this server."
            ),
            color=Colors.SERVERS,
        )
        await interaction.followup.send(embed=embed, view=Step6AllocSelect(self.ptero, self.state, free), ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════════
# STEP 6 — Select: allocation
# ══════════════════════════════════════════════════════════════════════════════════
class Step6AllocSelect(discord.ui.View):
    def __init__(self, ptero, state, allocations):
        super().__init__(timeout=180)
        self.ptero = ptero
        self.state = state
        opts = [
            discord.SelectOption(
                label=f"{a['attributes']['ip']}:{a['attributes']['port']}",
                value=str(a["attributes"]["id"]),
                description=a["attributes"].get("alias") or "No alias",
            ) for a in allocations[:25]
        ]
        sel = discord.ui.Select(placeholder="Choose IP:Port…", options=opts)
        sel.callback = self._cb
        self.add_item(sel)

    async def _cb(self, interaction: discord.Interaction):
        self.state.alloc_id = int(interaction.data["values"][0])
        self.stop()
        await interaction.response.send_modal(Step7ResourcesModal(self.ptero, self.state))


# ══════════════════════════════════════════════════════════════════════════════════
# STEP 7 — Modal: resources
# ══════════════════════════════════════════════════════════════════════════════════
class Step7ResourcesModal(discord.ui.Modal, title="Create Server — Resources"):
    memory = discord.ui.TextInput(label="Memory (MB)  — 0 = unlimited",           default="1024", placeholder="1024")
    disk   = discord.ui.TextInput(label="Disk (MB)    — 0 = unlimited",           default="5120", placeholder="5120")
    cpu    = discord.ui.TextInput(label="CPU (%)      — 0 = unlimited",           default="100",  placeholder="100")
    swap   = discord.ui.TextInput(label="Swap (MB)    — 0 = off, -1 = unlimited", default="0",    placeholder="0")
    io     = discord.ui.TextInput(label="IO Weight    — 10 to 1000",              default="500",  placeholder="500")

    def __init__(self, ptero, state):
        super().__init__()
        self.ptero = ptero
        self.state = state

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            s        = self.state
            s.memory = int(self.memory.value)
            s.disk   = int(self.disk.value)
            s.cpu    = int(self.cpu.value)
            s.swap   = int(self.swap.value)
            s.io     = max(10, min(1000, int(self.io.value)))
        except ValueError:
            await interaction.followup.send(embed=error_embed("All resource fields must be whole numbers."), ephemeral=True)
            return

        s = self.state
        embed = make_embed(
            title="🌐 Create Server — Final Confirmation",
            description=(
                "Review your server configuration.\n"
                "Press **🚀 Create Server** to deploy, or **🚫 Cancel** to abort."
            ),
            color=Colors.SERVERS,
            fields=[
                ("📛 Name",          s.name,                    False),
                ("📝 Description",   s.description or "—",      False),
                ("🔖 External ID",   s.external_id or "—",      True),
                ("👤 User ID",       str(s.user_id),            True),
                ("🖥️ Node ID",      str(s.node_id),            True),
                ("🥚 Egg",           s.egg_name,                True),
                ("🔌 Allocation ID", str(s.alloc_id),           True),
                ("🐳 Docker Image",  trunc(s.docker_image, 80), False),
                ("💾 Memory",        fmt_bytes(s.memory),       True),
                ("💿 Disk",          fmt_bytes(s.disk),         True),
                ("⚙️ CPU",           f"{s.cpu}%",               True),
                ("🔄 Swap",          str(s.swap),               True),
                ("📊 IO",            str(s.io),                 True),
                ("🔧 Env Vars",      str(len(s.env_vars)),      True),
            ],
        )
        await interaction.followup.send(embed=embed, view=Step8ConfirmView(self.ptero, self.state), ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════════
# STEP 8 — Confirm + create
# ══════════════════════════════════════════════════════════════════════════════════
class Step8ConfirmView(discord.ui.View):
    def __init__(self, ptero, state):
        super().__init__(timeout=120)
        self.ptero = ptero
        self.state = state

    @discord.ui.button(label="🚀 Create Server", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        self.stop()
        s = self.state

        payload: dict = {
            "name":         s.name,
            "user":         s.user_id,
            "egg":          s.egg_id,
            "docker_image": s.docker_image,
            "startup":      s.startup,
            "environment":  s.env_vars,
            "limits": {
                "memory": s.memory,
                "swap":   s.swap,
                "disk":   s.disk,
                "io":     s.io,
                "cpu":    s.cpu,
            },
            "feature_limits": {
                "databases":   5,
                "backups":     3,
                "allocations": 1,
            },
            "allocation": {
                "default": s.alloc_id,
            },
            "start_on_completion": False,
            "skip_scripts":        False,
        }
        if s.description:
            payload["description"] = s.description
        if s.external_id:
            payload["external_id"] = s.external_id

        try:
            result = await self.ptero.create_server(payload)
            attr   = result["attributes"]
            embed  = make_embed(
                title="🌐 Server Created Successfully!",
                description=(
                    f"**{attr['name']}** is being set up.\n\n"
                    f"🆔 **Panel ID:** `{attr['id']}`\n"
                    f"🔑 **UUID:** `{attr['uuid']}`\n"
                    f"🐳 **Image:** `{attr.get('container', {}).get('image', s.docker_image)}`"
                ),
                color=Colors.SUCCESS,
                fields=[
                    ("Memory", fmt_bytes(attr["limits"]["memory"]), True),
                    ("Disk",   fmt_bytes(attr["limits"]["disk"]),   True),
                    ("CPU",    f"{attr['limits']['cpu']}%",         True),
                ],
            )
        except PterodactylError as e:
            embed = error_embed(
                f"Pterodactyl returned an error:\n```\n{e.message}\n```\nHTTP `{e.status}`",
                title="❌ Server Creation Failed",
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🚫 Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.send_message(embed=warning_embed("Server creation cancelled."), ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════════
# EDIT MODALS
# ══════════════════════════════════════════════════════════════════════════════════
class EditDetailsModal(discord.ui.Modal, title="Edit Server Details"):
    name        = discord.ui.TextInput(label="Server Name",            max_length=191)
    description = discord.ui.TextInput(label="Description (optional)", required=False,
                                       style=discord.TextStyle.paragraph, max_length=255)
    external_id = discord.ui.TextInput(label="External ID (optional)", required=False, max_length=191)

    def __init__(self, ptero, server_id, attr):
        super().__init__()
        self.ptero           = ptero
        self.server_id       = server_id
        self._user_id        = attr.get("user", 0)
        self.name.default        = attr.get("name", "")
        self.description.default = attr.get("description", "")
        self.external_id.default = attr.get("external_id", "")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            payload: dict = {
                "name":        self.name.value,
                "user":        self._user_id,
                "description": self.description.value or "",
            }
            if self.external_id.value:
                payload["external_id"] = self.external_id.value
            await self.ptero.update_server_details(self.server_id, payload)
            e = success_embed(f"Server `{self.server_id}` details updated.", title="🌐 Details Updated")
            e.color = Colors.SERVERS
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


class EditBuildModal(discord.ui.Modal, title="Edit Server Build / Resources"):
    memory = discord.ui.TextInput(label="Memory (MB) — 0 = unlimited")
    disk   = discord.ui.TextInput(label="Disk (MB)   — 0 = unlimited")
    cpu    = discord.ui.TextInput(label="CPU (%)     — 0 = unlimited")
    swap   = discord.ui.TextInput(label="Swap (MB)   — -1 = unlimited")
    io     = discord.ui.TextInput(label="IO Weight   — 10 to 1000")

    def __init__(self, ptero, server_id, attr):
        super().__init__()
        self.ptero      = ptero
        self.server_id  = server_id
        self._alloc_id  = attr.get("allocation", 0)
        lim = attr.get("limits", {})
        self.memory.default = str(lim.get("memory", 1024))
        self.disk.default   = str(lim.get("disk",   5120))
        self.cpu.default    = str(lim.get("cpu",    100))
        self.swap.default   = str(lim.get("swap",   0))
        self.io.default     = str(lim.get("io",     500))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            payload = {
                "allocation": self._alloc_id,
                "limits": {
                    "memory": int(self.memory.value),
                    "disk":   int(self.disk.value),
                    "cpu":    int(self.cpu.value),
                    "swap":   int(self.swap.value),
                    "io":     max(10, min(1000, int(self.io.value))),
                },
                "feature_limits": {"databases": 5, "backups": 3, "allocations": 1},
            }
            await self.ptero.update_server_build(self.server_id, payload)
            e = success_embed(f"Server `{self.server_id}` build updated.", title="🌐 Build Updated")
            e.color = Colors.SERVERS
            await interaction.followup.send(embed=e, ephemeral=True)
        except ValueError:
            await interaction.followup.send(embed=error_embed("All values must be integers."), ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


class EditStartupModal(discord.ui.Modal, title="Edit Server Startup"):
    startup     = discord.ui.TextInput(label="Startup Command",
                                       style=discord.TextStyle.paragraph, max_length=1000)
    environment = discord.ui.TextInput(
        label="Environment Variables (KEY=VALUE per line)",
        style=discord.TextStyle.paragraph, required=False,
        placeholder="SERVER_JARFILE=server.jar\nMEMORY=1G",
        max_length=4000,
    )

    def __init__(self, ptero, server_id, egg_id, docker_image, current_startup, env_vars):
        super().__init__()
        self.ptero        = ptero
        self.server_id    = server_id
        self.egg_id       = egg_id
        self.docker_image = docker_image
        self.startup.default = current_startup
        if env_vars:
            self.environment.default = "\n".join(f"{k}={v}" for k, v in env_vars.items())

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            env: dict = {}
            for line in (self.environment.value or "").splitlines():
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
            payload = {
                "startup":      self.startup.value,
                "egg":          self.egg_id,
                "image":        self.docker_image,
                "environment":  env,
                "skip_scripts": False,
            }
            await self.ptero.update_server_startup(self.server_id, payload)
            e = success_embed(f"Server `{self.server_id}` startup updated.", title="🌐 Startup Updated")
            e.color = Colors.SERVERS
            await interaction.followup.send(embed=e, ephemeral=True)
        except PterodactylError as ex:
            await interaction.followup.send(embed=error_embed(ex.message), ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════════
# Shared helper
# ══════════════════════════════════════════════════════════════════════════════════
def _server_select(servers, placeholder="Select a server…") -> discord.ui.Select:
    opts = [
        discord.SelectOption(
            label=trunc(s["attributes"]["name"], 100),
            value=str(s["attributes"]["id"]),
            description=f"ID {s['attributes']['id']} — {s['attributes']['uuid'][:8]}…",
        ) for s in servers[:25]
    ]
    return discord.ui.Select(placeholder=placeholder, options=opts)


# ══════════════════════════════════════════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════════════════════════════════════════
class ServersCog(commands.Cog, name="Servers"):

    def __init__(self, bot: commands.Bot):
        self.bot   = bot
        self.ptero: PterodactylClient = bot.ptero  # type: ignore

    servers_group = app_commands.Group(name="servers", description="Manage Pterodactyl servers.")

    # ── overview ─────────────────────────────────────────────────────────────────
    @servers_group.command(name="overview", description="Server statistics overview.")
    @is_owner()
    async def servers_overview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            servers    = await self.ptero.list_servers()
            total_mem  = sum(s["attributes"]["limits"]["memory"] for s in servers)
            total_disk = sum(s["attributes"]["limits"]["disk"]   for s in servers)
            embed = make_embed(
                title="🌐 Servers Overview",
                description=f"Your panel has **{len(servers)}** server(s).",
                color=Colors.SERVERS,
                fields=[
                    ("Total Servers", str(len(servers)),     True),
                    ("Total Memory",  fmt_bytes(total_mem),  True),
                    ("Total Disk",    fmt_bytes(total_disk), True),
                ],
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)

    # ── list ─────────────────────────────────────────────────────────────────────
    @servers_group.command(name="list", description="List all servers.")
    @is_owner()
    async def servers_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            servers = await self.ptero.list_servers()
            if not servers:
                await interaction.followup.send(embed=warning_embed("No servers found."), ephemeral=True)
                return
            embed = make_embed(
                title="🌐 All Servers",
                description=f"Found **{len(servers)}** server(s):",
                color=Colors.SERVERS,
            )
            for s in servers[:12]:
                a   = s["attributes"]
                lim = a["limits"]
                embed.add_field(
                    name=f"[{a['id']}] {a['name']}",
                    value=(
                        f"**Node:** {a.get('node','?')}  "
                        f"**Mem:** {fmt_bytes(lim['memory'])}  "
                        f"**Disk:** {fmt_bytes(lim['disk'])}\n"
                        f"**UUID:** `{a['uuid'][:8]}…`"
                    ),
                    inline=False,
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)

    # ── create ────────────────────────────────────────────────────────────────────
    @servers_group.command(name="create", description="Create a new server (wizard with Docker image picker).")
    @is_owner()
    async def servers_create(self, interaction: discord.Interaction):
        await interaction.response.send_modal(Step1Modal(self.ptero))

    # ── edit-details ──────────────────────────────────────────────────────────────
    @servers_group.command(name="edit-details", description="Edit server name / description.")
    @is_owner()
    async def servers_edit_details(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            servers = await self.ptero.list_servers()
            if not servers:
                await interaction.followup.send(embed=warning_embed("No servers found."), ephemeral=True)
                return
            select = _server_select(servers, "Select a server to edit…")

            async def on_sel(inter: discord.Interaction):
                sid = int(inter.data["values"][0])
                srv = await self.ptero.get_server(sid)
                await inter.response.send_modal(EditDetailsModal(self.ptero, sid, srv["attributes"]))

            select.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            await interaction.followup.send(
                embed=make_embed("🌐 Edit Server Details", "Select a server:", color=Colors.SERVERS),
                view=view, ephemeral=True,
            )
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)

    # ── edit-build ────────────────────────────────────────────────────────────────
    @servers_group.command(name="edit-build", description="Edit server resource limits.")
    @is_owner()
    async def servers_edit_build(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            servers = await self.ptero.list_servers()
            if not servers:
                await interaction.followup.send(embed=warning_embed("No servers found."), ephemeral=True)
                return
            select = _server_select(servers, "Select a server to edit build…")

            async def on_sel(inter: discord.Interaction):
                sid = int(inter.data["values"][0])
                srv = await self.ptero.get_server(sid)
                await inter.response.send_modal(EditBuildModal(self.ptero, sid, srv["attributes"]))

            select.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            await interaction.followup.send(
                embed=make_embed("🌐 Edit Server Build", "Select a server:", color=Colors.SERVERS),
                view=view, ephemeral=True,
            )
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)

    # ── edit-startup ──────────────────────────────────────────────────────────────
    @servers_group.command(name="edit-startup", description="Edit server startup command and env vars.")
    @is_owner()
    async def servers_edit_startup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            servers = await self.ptero.list_servers()
            if not servers:
                await interaction.followup.send(embed=warning_embed("No servers found."), ephemeral=True)
                return
            select = _server_select(servers, "Select a server to edit startup…")

            async def on_sel(inter: discord.Interaction):
                sid       = int(inter.data["values"][0])
                srv       = await self.ptero.get_server(sid)
                attr      = srv["attributes"]
                container = attr.get("container", {})
                startup   = container.get("startup_command") or attr.get("startup", "")
                docker_img = container.get("image", "")
                egg_id    = attr.get("egg", 0)
                env_vars  = container.get("environment", {})
                await inter.response.send_modal(
                    EditStartupModal(self.ptero, sid, egg_id, docker_img, startup, env_vars)
                )

            select.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            await interaction.followup.send(
                embed=make_embed("🌐 Edit Server Startup", "Select a server:", color=Colors.SERVERS),
                view=view, ephemeral=True,
            )
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)

    # ── delete ────────────────────────────────────────────────────────────────────
    @servers_group.command(name="delete", description="Delete a server permanently.")
    @is_owner()
    async def servers_delete(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            servers = await self.ptero.list_servers()
            if not servers:
                await interaction.followup.send(embed=warning_embed("No servers found."), ephemeral=True)
                return
            select = _server_select(servers, "Select a server to delete…")

            async def on_sel(inter: discord.Interaction):
                sid  = int(inter.data["values"][0])
                conf = ConfirmView()
                await inter.response.send_message(
                    embed=warning_embed(
                        f"Delete server `{sid}`?\n⚠️ **All data will be permanently lost.**",
                        title="⚠️ Confirm Deletion",
                    ),
                    view=conf, ephemeral=True,
                )
                await conf.wait()
                if conf.confirmed:
                    try:
                        await self.ptero.delete_server(sid)
                        res = success_embed(f"Server `{sid}` deleted.", title="🌐 Server Deleted")
                        res.color = Colors.SERVERS
                    except PterodactylError as ex:
                        res = error_embed(ex.message)
                    await inter.edit_original_response(embed=res, view=None)
                else:
                    await inter.edit_original_response(embed=warning_embed("Deletion cancelled."), view=None)

            select.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            await interaction.followup.send(
                embed=make_embed("🌐 Delete Server", "Select a server:", color=Colors.SERVERS),
                view=view, ephemeral=True,
            )
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)

    # ── databases ─────────────────────────────────────────────────────────────────
    @servers_group.command(name="databases", description="View server databases.")
    @is_owner()
    async def servers_databases(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            servers = await self.ptero.list_servers()
            if not servers:
                await interaction.followup.send(embed=warning_embed("No servers found."), ephemeral=True)
                return
            select = _server_select(servers, "Select a server…")

            async def on_sel(inter: discord.Interaction):
                sid = int(inter.data["values"][0])
                await inter.response.defer(ephemeral=True)
                dbs = await self.ptero.list_server_databases(sid)
                embed = make_embed(
                    title=f"🌐 Databases — Server {sid}",
                    description=f"**{len(dbs)}** database(s) found.",
                    color=Colors.SERVERS,
                )
                for db in dbs:
                    a = db["attributes"]
                    embed.add_field(
                        name=a.get("name", "Unknown"),
                        value=f"User: `{a.get('username','N/A')}`\nHost ID: `{a.get('host', {}).get('id','?')}`",
                        inline=True,
                    )
                await inter.followup.send(embed=embed, ephemeral=True)

            select.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            await interaction.followup.send(
                embed=make_embed("🌐 Server Databases", "Select a server:", color=Colors.SERVERS),
                view=view, ephemeral=True,
            )
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)

    # ── suspend ───────────────────────────────────────────────────────────────────
    @servers_group.command(name="suspend", description="Suspend a server.")
    @is_owner()
    async def servers_suspend(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            servers = await self.ptero.list_servers()
            if not servers:
                await interaction.followup.send(embed=warning_embed("No servers found."), ephemeral=True)
                return
            select = _server_select(servers, "Select a server to suspend…")

            async def on_sel(inter: discord.Interaction):
                sid  = int(inter.data["values"][0])
                conf = ConfirmView()
                await inter.response.send_message(
                    embed=warning_embed(
                        f"Suspend server `{sid}`?\nUsers will **NOT** be able to start it.",
                        title="⚠️ Confirm Suspension",
                    ),
                    view=conf, ephemeral=True,
                )
                await conf.wait()
                if conf.confirmed:
                    try:
                        await self.ptero.suspend_server(sid)
                        res = success_embed(f"Server `{sid}` suspended.", title="🔴 Server Suspended")
                        res.color = Colors.SERVERS
                    except PterodactylError as ex:
                        res = error_embed(ex.message)
                    await inter.edit_original_response(embed=res, view=None)
                else:
                    await inter.edit_original_response(embed=warning_embed("Suspension cancelled."), view=None)

            select.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            await interaction.followup.send(
                embed=make_embed("🔴 Suspend Server", "Select a server:", color=Colors.SERVERS),
                view=view, ephemeral=True,
            )
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)

    # ── unsuspend ─────────────────────────────────────────────────────────────────
    @servers_group.command(name="unsuspend", description="Unsuspend a server.")
    @is_owner()
    async def servers_unsuspend(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            servers = await self.ptero.list_servers()
            if not servers:
                await interaction.followup.send(embed=warning_embed("No servers found."), ephemeral=True)
                return
            select = _server_select(servers, "Select a server to unsuspend…")

            async def on_sel(inter: discord.Interaction):
                sid  = int(inter.data["values"][0])
                conf = ConfirmView()
                await inter.response.send_message(
                    embed=warning_embed(
                        f"Unsuspend server `{sid}`?\nUsers will be able to start it again.",
                        title="⚠️ Confirm Unsuspend",
                    ),
                    view=conf, ephemeral=True,
                )
                await conf.wait()
                if conf.confirmed:
                    try:
                        await self.ptero.unsuspend_server(sid)
                        res = success_embed(f"Server `{sid}` unsuspended.", title="🟢 Server Unsuspended")
                        res.color = Colors.SERVERS
                    except PterodactylError as ex:
                        res = error_embed(ex.message)
                    await inter.edit_original_response(embed=res, view=None)
                else:
                    await inter.edit_original_response(embed=warning_embed("Unsuspend cancelled."), view=None)

            select.callback = on_sel
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            await interaction.followup.send(
                embed=make_embed("🟢 Unsuspend Server", "Select a server:", color=Colors.SERVERS),
                view=view, ephemeral=True,
            )
        except PterodactylError as e:
            await interaction.followup.send(embed=error_embed(e.message), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServersCog(bot))

