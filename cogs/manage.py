"""
cogs/manage.py  –  /manage command group.

/manage servers
  → Premium dropdown of all servers
  → Select one → gorgeous status embed:
       🟢/🔴  status  |  CPU  |  Memory  |  Disk  |  Uptime  |  IP:Port
  → Action buttons: Start · Stop · Restart · Kill · Reinstall · Refresh

KEY DESIGN:
  - Application API key  (PTERODACTYL_API_KEY)    → list servers via self.ptero
  - Client API key       (PTERODACTYL_CLIENT_KEY)  → live stats + power actions
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from api_client import PterodactylClient, PterodactylError
from config import PTERODACTYL_URL, PTERODACTYL_CLIENT_KEY
from cogs.utils import is_owner, trunc, fmt_bytes


# ══════════════════════════════════════════════════════════════════════════════════
# Client-API wrapper  (uses PTERODACTYL_CLIENT_KEY)
# ══════════════════════════════════════════════════════════════════════════════════

class ClientAPI:
    """
    Thin async wrapper for /api/client endpoints.
    Requires a CLIENT API key (Account → API Credentials), NOT the Application key.
    """

    def __init__(self):
        self._base = f"{PTERODACTYL_URL}/api/client"
        self._hdrs = {
            "Authorization": f"Bearer {PTERODACTYL_CLIENT_KEY}",
            "Accept":        "application/json",
            "Content-Type":  "application/json",
        }

    async def _req(self, method: str, path: str, json: Optional[dict] = None) -> dict:
        url = f"{self._base}{path}"
        async with aiohttp.ClientSession(
            headers=self._hdrs,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as s:
            async with s.request(method, url, json=json) as r:
                if r.status == 204:
                    return {}
                txt = await r.text()
                if not txt.strip():
                    return {}
                try:
                    return await r.json(content_type=None)
                except Exception:
                    return {}

    async def resources(self, identifier: str) -> dict:
        """GET /api/client/servers/{identifier}/resources  →  attributes dict"""
        d = await self._req("GET", f"/servers/{identifier}/resources")
        return d.get("attributes", {})

    async def power(self, identifier: str, signal: str) -> None:
        """POST /api/client/servers/{identifier}/power   signal: start|stop|restart|kill"""
        await self._req("POST", f"/servers/{identifier}/power", {"signal": signal})

    async def reinstall(self, identifier: str) -> None:
        """POST /api/client/servers/{identifier}/reinstall"""
        await self._req("POST", f"/servers/{identifier}/reinstall")


# Singleton — one ClientAPI instance for the whole bot lifetime
_client_api = ClientAPI()


# ══════════════════════════════════════════════════════════════════════════════════
# Visual helpers
# ══════════════════════════════════════════════════════════════════════════════════

def _bar(pct: float, width: int = 12) -> str:
    filled = max(0, min(width, round(pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def _pct_emoji(pct: float) -> str:
    if pct >= 90: return "🔴"
    if pct >= 70: return "🟠"
    if pct >= 40: return "🟡"
    return "🟢"


def _state_line(state: str) -> tuple[str, discord.Color]:
    table = {
        "running":  ("🟢  **ONLINE**",    discord.Color.from_rgb(0, 210, 130)),
        "starting": ("🟡  **STARTING…**", discord.Color.from_rgb(255, 200, 0)),
        "stopping": ("🟠  **STOPPING…**", discord.Color.from_rgb(255, 130, 0)),
        "offline":  ("🔴  **OFFLINE**",   discord.Color.from_rgb(220, 50, 50)),
    }
    return table.get(state.lower(), ("⚫  **UNKNOWN**", discord.Color.greyple()))


def _uptime(ms: int) -> str:
    if ms <= 0:
        return "—"
    s = ms // 1000
    m = s  // 60;  s %= 60
    h = m  // 60;  m %= 60
    d = h  // 24;  h %= 24
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts[:3])


def _bytes(b: int) -> str:
    if b <= 0:
        return "0 MB"
    mb = b / 1_048_576
    return f"{mb / 1024:.2f} GB" if mb >= 1024 else f"{mb:.1f} MB"


# ══════════════════════════════════════════════════════════════════════════════════
# Premium embed builder
# ══════════════════════════════════════════════════════════════════════════════════

async def _build_embed(app_attr: dict) -> discord.Embed:
    """
    Build the premium server status embed.
    app_attr = the 'attributes' block from the Application API.
    Live resource stats are pulled from the Client API using the server identifier.
    """
    name       = app_attr.get("name", "Unknown")
    sid        = app_attr.get("id", "?")
    identifier = app_attr.get("identifier", "")
    limits     = app_attr.get("limits", {})
    mem_lim    = limits.get("memory", 0)
    disk_lim   = limits.get("disk",   0)
    cpu_lim    = limits.get("cpu",    0)

    # IP:Port — pulled from relationships.allocations
    alloc_data = (
        app_attr
        .get("relationships", {})
        .get("allocations", {})
        .get("data", [])
    )
    if alloc_data:
        a0      = alloc_data[0].get("attributes", {})
        ip_port = f"{a0.get('alias') or a0.get('ip', '?')}:{a0.get('port', '?')}"
    else:
        ip_port = "N/A"

    # ── Live stats via Client API ────────────────────────────────────────────────
    res     = await _client_api.resources(identifier) if identifier else {}
    state   = res.get("current_state", "offline")
    stats   = res.get("resources", {})
    cpu_abs = stats.get("cpu_absolute",     0.0)
    mem_b   = stats.get("memory_bytes",     0)
    disk_b  = stats.get("disk_bytes",       0)
    net_rx  = stats.get("network_rx_bytes", 0)
    net_tx  = stats.get("network_tx_bytes", 0)
    uptime  = stats.get("uptime",           0)

    cpu_pct  = min(cpu_abs, 100.0)
    mem_pct  = (mem_b  / (mem_lim  * 1_048_576) * 100) if mem_lim  > 0 else 0.0
    disk_pct = (disk_b / (disk_lim * 1_048_576) * 100) if disk_lim > 0 else 0.0

    badge, color = _state_line(state)
    is_online    = state == "running"

    # ── Build embed ──────────────────────────────────────────────────────────────
    embed = discord.Embed(color=color, timestamp=datetime.datetime.utcnow())
    embed.set_author(name="PTERODACTYL  ·  SERVER MANAGER")
    embed.title = f"{'⚡' if is_online else '💤'}  {name}"

    embed.description = (
        f"{badge}\n"
        f"{'━' * 34}\n"
        f"🌐  **IP / Port** ` {ip_port} `\n"
        f"🆔  **ID** ` {sid} `   •   🔑  **Identifier** ` {identifier} `"
    )

    if is_online:
        # CPU
        embed.add_field(
            name=f"{_pct_emoji(cpu_pct)}  CPU",
            value=(
                f"` {_bar(cpu_pct)} `\n"
                f"**{cpu_abs:.1f}%** used"
                + (f"  *(cap {cpu_lim}%)*" if cpu_lim else "")
            ),
            inline=True,
        )
        # Memory
        embed.add_field(
            name=f"{_pct_emoji(mem_pct)}  Memory",
            value=(
                f"` {_bar(mem_pct)} `\n"
                f"**{_bytes(mem_b)}** / {fmt_bytes(mem_lim)}"
            ),
            inline=True,
        )
        # Invisible spacer to force 2-column layout
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Disk
        embed.add_field(
            name=f"{_pct_emoji(disk_pct)}  Disk",
            value=(
                f"` {_bar(disk_pct)} `\n"
                f"**{_bytes(disk_b)}** / {fmt_bytes(disk_lim)}"
            ),
            inline=True,
        )
        # Uptime
        embed.add_field(
            name="⏱️  Uptime",
            value=f"**{_uptime(uptime)}**",
            inline=True,
        )
        # Network
        embed.add_field(
            name="📡  Network",
            value=f"▼ {_bytes(net_rx)}\n▲ {_bytes(net_tx)}",
            inline=True,
        )
    else:
        # Offline — show configured limits only (no fake zeros)
        embed.add_field(
            name="⚙️  CPU Limit",
            value=f"**{cpu_lim}%**" if cpu_lim else "Unlimited",
            inline=True,
        )
        embed.add_field(
            name="💾  Memory Limit",
            value=fmt_bytes(mem_lim),
            inline=True,
        )
        embed.add_field(
            name="💿  Disk Limit",
            value=fmt_bytes(disk_lim),
            inline=True,
        )

    embed.set_footer(text=f"🕐  Updated  •  Server #{sid}")
    return embed


# ══════════════════════════════════════════════════════════════════════════════════
# Reinstall confirmation view
# ══════════════════════════════════════════════════════════════════════════════════

class _ConfirmReinstall(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.confirmed = False

    @discord.ui.button(label="✅  Yes, reinstall", style=discord.ButtonStyle.danger)
    async def yes(self, interaction: discord.Interaction, _btn: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="❌  Cancel", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, _btn: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()


# ══════════════════════════════════════════════════════════════════════════════════
# Action buttons view  (shown below the status embed)
# ══════════════════════════════════════════════════════════════════════════════════

class ServerActionsView(discord.ui.View):
    """▶ Start  ■ Stop  ↺ Restart  ☠ Kill  |  🔁 Reinstall  🔄 Refresh"""

    def __init__(self, app_attr: dict):
        super().__init__(timeout=300)
        self._attr       = app_attr
        self._identifier = app_attr.get("identifier", "")
        self._name       = app_attr.get("name", "Server")

    # ── shared power action handler ───────────────────────────────────────────────

    async def _power(self, interaction: discord.Interaction, signal: str, label: str):
        await interaction.response.defer(ephemeral=True)
        try:
            await _client_api.power(self._identifier, signal)
            await asyncio.sleep(2)                        # let panel catch up
            embed = await _build_embed(self._attr)
            await interaction.edit_original_response(embed=embed, view=self)
            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"✅  **{label}** sent to `{self._name}`.",
                    color=discord.Color.from_rgb(0, 210, 130),
                ),
                ephemeral=True,
            )
        except Exception as exc:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"❌  Failed: `{exc}`",
                    color=discord.Color.from_rgb(220, 50, 50),
                ),
                ephemeral=True,
            )

    # ── Row 0 — power signals ─────────────────────────────────────────────────────

    @discord.ui.button(label="▶  Start",   style=discord.ButtonStyle.success, row=0)
    async def btn_start(self, interaction: discord.Interaction, _btn: discord.ui.Button):
        await self._power(interaction, "start", "Start")

    @discord.ui.button(label="■  Stop",    style=discord.ButtonStyle.danger,  row=0)
    async def btn_stop(self, interaction: discord.Interaction, _btn: discord.ui.Button):
        await self._power(interaction, "stop", "Stop")

    @discord.ui.button(label="↺  Restart", style=discord.ButtonStyle.primary, row=0)
    async def btn_restart(self, interaction: discord.Interaction, _btn: discord.ui.Button):
        await self._power(interaction, "restart", "Restart")

    @discord.ui.button(label="☠  Kill",    style=discord.ButtonStyle.danger,  row=0)
    async def btn_kill(self, interaction: discord.Interaction, _btn: discord.ui.Button):
        await self._power(interaction, "kill", "Kill")

    # ── Row 1 — management ────────────────────────────────────────────────────────

    @discord.ui.button(label="🔁  Reinstall", style=discord.ButtonStyle.secondary, row=1)
    async def btn_reinstall(self, interaction: discord.Interaction, _btn: discord.ui.Button):
        confirm = _ConfirmReinstall()
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️  Confirm Reinstall",
                description=(
                    f"Reinstall **{self._name}**?\n\n"
                    "⚠️  This will **wipe ALL server files** and reinstall from scratch.\n"
                    "This action **cannot be undone**."
                ),
                color=discord.Color.from_rgb(255, 130, 0),
            ),
            view=confirm,
            ephemeral=True,
        )
        await confirm.wait()
        if confirm.confirmed:
            try:
                await _client_api.reinstall(self._identifier)
                await interaction.followup.send(
                    embed=discord.Embed(
                        description=f"✅  Reinstall initiated for `{self._name}`.",
                        color=discord.Color.from_rgb(0, 210, 130),
                    ),
                    ephemeral=True,
                )
            except Exception as exc:
                await interaction.followup.send(
                    embed=discord.Embed(
                        description=f"❌  Failed: `{exc}`",
                        color=discord.Color.from_rgb(220, 50, 50),
                    ),
                    ephemeral=True,
                )
        else:
            await interaction.followup.send(
                embed=discord.Embed(
                    description="Reinstall cancelled.",
                    color=discord.Color.greyple(),
                ),
                ephemeral=True,
            )

    @discord.ui.button(label="🔄  Refresh", style=discord.ButtonStyle.secondary, row=1)
    async def btn_refresh(self, interaction: discord.Interaction, _btn: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = await _build_embed(self._attr)
        await interaction.edit_original_response(embed=embed, view=self)
        await interaction.followup.send(
            embed=discord.Embed(
                description="🔄  Stats refreshed.",
                color=discord.Color.blurple(),
            ),
            ephemeral=True,
        )


# ══════════════════════════════════════════════════════════════════════════════════
# Server picker dropdown
# ══════════════════════════════════════════════════════════════════════════════════

class ServerPickerView(discord.ui.View):
    """Dropdown of all servers → on selection opens the status embed + action buttons."""

    def __init__(self, servers: list[dict]):
        super().__init__(timeout=120)
        # Map  str(id) → attributes  for quick lookup
        self._servers = {str(s["attributes"]["id"]): s["attributes"] for s in servers}

        opts = [
            discord.SelectOption(
                label=trunc(s["attributes"]["name"], 100),
                value=str(s["attributes"]["id"]),
                description=f"ID {s['attributes']['id']}  ·  {s['attributes'].get('identifier','')[:8]}",
                emoji="🖥️",
            )
            for s in servers[:25]
        ]
        sel           = discord.ui.Select(
            placeholder="🔍  Choose a server to inspect…",
            options=opts,
            min_values=1,
            max_values=1,
        )
        sel.callback  = self._on_select
        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):
        sid  = interaction.data["values"][0]
        attr = self._servers.get(sid)
        if not attr:
            await interaction.response.send_message("Server not found.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        embed = await _build_embed(attr)
        view  = ServerActionsView(attr)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════════════════════════════════════════

class ManageCog(commands.Cog, name="Manage"):

    def __init__(self, bot: commands.Bot):
        self.bot   = bot
        self.ptero: PterodactylClient = bot.ptero  # type: ignore

    manage_group = app_commands.Group(
        name="manage",
        description="Premium live server management panel.",
    )

    @manage_group.command(
        name="servers",
        description="Open the premium server management panel (live stats + power control).",
    )
    @is_owner()
    async def manage_servers(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not PTERODACTYL_CLIENT_KEY:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="⚙️  Configuration Required",
                    description=(
                        "**`PTERODACTYL_CLIENT_KEY`** is not set in your `.env` file.\n\n"
                        "To get your Client API key:\n"
                        "1. Log in to your Pterodactyl panel\n"
                        "2. Go to **Account → API Credentials**\n"
                        "3. Create a new key and paste it as `PTERODACTYL_CLIENT_KEY` in `.env`\n"
                        "4. Restart the bot"
                    ),
                    color=discord.Color.from_rgb(255, 130, 0),
                ),
                ephemeral=True,
            )
            return

        try:
            servers = await self.ptero.list_servers()
        except PterodactylError as e:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌  API Error",
                    description=e.message,
                    color=discord.Color.from_rgb(220, 50, 50),
                ),
                ephemeral=True,
            )
            return

        if not servers:
            await interaction.followup.send(
                embed=discord.Embed(
                    description="⚠️  No servers found on this panel.",
                    color=discord.Color.from_rgb(255, 200, 0),
                ),
                ephemeral=True,
            )
            return

        header = discord.Embed(
            title="🦅  Pterodactyl  ·  Server Management",
            description=(
                f"**{len(servers)}** server(s) on this panel.\n"
                "Select a server from the dropdown below to view its **live stats**\n"
                "and send power / management actions.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "▶ Start  ·  ■ Stop  ·  ↺ Restart  ·  ☠ Kill  ·  🔁 Reinstall"
            ),
            color=discord.Color.from_rgb(88, 101, 242),
            timestamp=datetime.datetime.utcnow(),
        )
        header.set_footer(text="Only visible to you  ·  Pterodactyl Admin Bot")

        await interaction.followup.send(
            embed=header,
            view=ServerPickerView(servers),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ManageCog(bot))

