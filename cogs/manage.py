"""
cogs/manage.py  –  /manage servers  (owner-only admin panel)

FIX: Uses PTERODACTYL_CLIENT_KEY for all /api/client calls.
     The Client API key must belong to an admin account so it
     can see and control ALL servers on the panel.

How to get the right key:
  1. Log into Pterodactyl as an ADMIN user
  2. Click your avatar (top-right) → Account → API Credentials
  3. Create a key — this is your PTERODACTYL_CLIENT_KEY
  4. Make sure that account has admin privileges on the panel
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
from config import PTERODACTYL_URL, PTERODACTYL_API_KEY, PTERODACTYL_CLIENT_KEY
from cogs.utils import is_owner, trunc, fmt_bytes


# ══════════════════════════════════════════════════════════════════════════════════
# Client API wrapper  —  uses PTERODACTYL_CLIENT_KEY
# ══════════════════════════════════════════════════════════════════════════════════

class _ClientAPI:
    """
    Wraps /api/client endpoints.
    MUST use a CLIENT key (ptlc_...) from an admin panel account.
    """

    def __init__(self):
        self._base = f"{PTERODACTYL_URL}/api/client"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {PTERODACTYL_CLIENT_KEY}",
            "Accept":        "application/json",
            "Content-Type":  "application/json",
        }

    async def _req(self, method: str, path: str, body: Optional[dict] = None) -> tuple[int, dict]:
        """Returns (status_code, response_dict)."""
        url = f"{self._base}{path}"
        async with aiohttp.ClientSession(
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=20),
        ) as s:
            async with s.request(method, url, json=body) as r:
                status = r.status
                if status == 204:
                    return status, {}
                text = await r.text()
                if not text.strip():
                    return status, {}
                try:
                    data = await r.json(content_type=None)
                    return status, data
                except Exception:
                    return status, {"_raw": text[:300]}

    async def resources(self, ident: str) -> tuple[bool, dict]:
        """
        Returns (success, attributes_dict).
        On failure returns (False, {error info}).
        """
        status, data = await self._req("GET", f"/servers/{ident}/resources")
        if status == 200:
            return True, data.get("attributes", {})
        return False, {"status": status, "data": data}

    async def power(self, ident: str, signal: str) -> tuple[bool, str]:
        """
        Returns (success, error_message).
        """
        status, data = await self._req("POST", f"/servers/{ident}/power", {"signal": signal})
        if status in (200, 204):
            return True, ""
        errors = data.get("errors", [])
        msg = errors[0].get("detail", str(data)) if errors else str(data)
        return False, f"HTTP {status}: {msg}"

    async def reinstall(self, ident: str) -> tuple[bool, str]:
        status, data = await self._req("POST", f"/servers/{ident}/reinstall")
        if status in (200, 204):
            return True, ""
        errors = data.get("errors", [])
        msg = errors[0].get("detail", str(data)) if errors else str(data)
        return False, f"HTTP {status}: {msg}"


_api = _ClientAPI()


# ══════════════════════════════════════════════════════════════════════════════════
# Pure helpers
# ══════════════════════════════════════════════════════════════════════════════════

def _ident(attr: dict) -> str:
    return attr.get("identifier") or attr.get("uuid", "")[:8]


def _ip(attr: dict) -> str:
    data = (
        attr.get("relationships", {})
            .get("allocations", {})
            .get("data", [])
    )
    if data:
        a = data[0].get("attributes", {})
        return f"{a.get('alias') or a.get('ip', '?')}:{a.get('port', '?')}"
    return "N/A"


def _bar(pct: float, width: int = 12) -> str:
    filled = max(0, min(width, round(pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def _heat(pct: float) -> str:
    if pct >= 90: return "🔴"
    if pct >= 70: return "🟠"
    if pct >= 40: return "🟡"
    return "🟢"


def _state(raw: str) -> tuple[str, discord.Color]:
    return {
        "running":  ("🟢  **ONLINE**",    discord.Color.from_rgb(0, 210, 130)),
        "starting": ("🟡  **STARTING…**", discord.Color.from_rgb(255, 200, 0)),
        "stopping": ("🟠  **STOPPING…**", discord.Color.from_rgb(255, 130, 0)),
    }.get(raw.lower(), ("🔴  **OFFLINE**", discord.Color.from_rgb(200, 40, 40)))


def _uptime(ms: int) -> str:
    if ms <= 0:
        return "—"
    s = ms // 1000
    m = s // 60;  s %= 60
    h = m // 60;  m %= 60
    d = h // 24;  h %= 24
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts[:3])


def _size(b: int) -> str:
    if b <= 0:
        return "0 B"
    mb = b / 1_048_576
    return f"{mb / 1024:.2f} GB" if mb >= 1024 else f"{mb:.1f} MB"


def _ok(msg: str) -> discord.Embed:
    return discord.Embed(description=f"✅  {msg}", color=discord.Color.from_rgb(0, 210, 130))


def _err(msg: str) -> discord.Embed:
    return discord.Embed(description=f"❌  {msg}", color=discord.Color.from_rgb(220, 50, 50))


def _warn(msg: str) -> discord.Embed:
    return discord.Embed(description=f"⚠️  {msg}", color=discord.Color.from_rgb(255, 200, 0))


# ══════════════════════════════════════════════════════════════════════════════════
# Embed builder
# ══════════════════════════════════════════════════════════════════════════════════

async def _build_embed(attr: dict) -> discord.Embed:
    name     = attr.get("name", "Unknown")
    sid      = attr.get("id", "?")
    ident    = _ident(attr)
    ip_port  = _ip(attr)
    limits   = attr.get("limits", {})
    mem_lim  = limits.get("memory", 0)
    disk_lim = limits.get("disk",   0)
    cpu_lim  = limits.get("cpu",    0)

    # ── Fetch live stats ─────────────────────────────────────────────────────────
    fetch_ok = False
    status   = "offline"
    cpu_abs = mem_b = disk_b = net_rx = net_tx = uptime = 0
    cpu_abs = 0.0

    if ident:
        fetch_ok, res = await _api.resources(ident)
        if fetch_ok:
            status  = res.get("current_state", "offline")
            stats   = res.get("resources", {})
            cpu_abs = stats.get("cpu_absolute",     0.0)
            mem_b   = stats.get("memory_bytes",     0)
            disk_b  = stats.get("disk_bytes",       0)
            net_rx  = stats.get("network_rx_bytes", 0)
            net_tx  = stats.get("network_tx_bytes", 0)
            uptime  = stats.get("uptime",           0)

    cpu_pct  = min(float(cpu_abs), 100.0)
    mem_pct  = (mem_b  / (mem_lim  * 1_048_576) * 100) if mem_lim  > 0 else 0.0
    disk_pct = (disk_b / (disk_lim * 1_048_576) * 100) if disk_lim > 0 else 0.0

    badge, color = _state(status)
    online       = status == "running"

    embed = discord.Embed(color=color, timestamp=datetime.datetime.utcnow())
    embed.set_author(name="PTERODACTYL ADMIN  ·  SERVER CONTROL PANEL")
    embed.title = f"{'⚡' if online else '💤'}  {name}"

    # Description
    desc_lines = [
        badge,
        "━" * 36,
        f"🌐  **IP / Port**  ` {ip_port} `",
        f"🆔  **Server ID**  ` {sid} `",
        f"🔑  **Identifier** ` {ident} `",
    ]
    if not fetch_ok and ident:
        desc_lines.append("")
        desc_lines.append("⚠️  *Could not fetch live stats — check `PTERODACTYL_CLIENT_KEY`*")
    embed.description = "\n".join(desc_lines)

    # Resource fields
    if online and fetch_ok:
        embed.add_field(
            name=f"{_heat(cpu_pct)}  CPU",
            value=f"` {_bar(cpu_pct)} `\n**{cpu_abs:.1f}%**" + (f"  of {cpu_lim}%" if cpu_lim else ""),
            inline=True,
        )
        embed.add_field(
            name=f"{_heat(mem_pct)}  Memory",
            value=f"` {_bar(mem_pct)} `\n**{_size(mem_b)}** / {fmt_bytes(mem_lim)}",
            inline=True,
        )
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(
            name=f"{_heat(disk_pct)}  Disk",
            value=f"` {_bar(disk_pct)} `\n**{_size(disk_b)}** / {fmt_bytes(disk_lim)}",
            inline=True,
        )
        embed.add_field(
            name="⏱️  Uptime",
            value=f"**{_uptime(uptime)}**",
            inline=True,
        )
        embed.add_field(
            name="📡  Network",
            value=f"▼ {_size(net_rx)}  ▲ {_size(net_tx)}",
            inline=True,
        )
    else:
        embed.add_field(
            name="⚙️  CPU Limit",
            value=f"**{cpu_lim}%**" if cpu_lim else "Unlimited",
            inline=True,
        )
        embed.add_field(
            name="💾  Memory",
            value=fmt_bytes(mem_lim),
            inline=True,
        )
        embed.add_field(
            name="💿  Disk",
            value=fmt_bytes(disk_lim),
            inline=True,
        )

    embed.set_footer(text=f"🕐  Refreshed  •  Admin Panel  •  Server #{sid}")
    return embed


# ══════════════════════════════════════════════════════════════════════════════════
# Reinstall confirmation
# ══════════════════════════════════════════════════════════════════════════════════

class _ReinstallConfirm(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.confirmed = False

    @discord.ui.button(label="⚠️  Yes — wipe & reinstall", style=discord.ButtonStyle.danger)
    async def yes(self, inter: discord.Interaction, _: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await inter.response.defer()

    @discord.ui.button(label="✖  Cancel", style=discord.ButtonStyle.secondary)
    async def no(self, inter: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await inter.response.defer()


# ══════════════════════════════════════════════════════════════════════════════════
# Control view  (power buttons + refresh)
# ══════════════════════════════════════════════════════════════════════════════════

class ControlView(discord.ui.View):

    def __init__(self, attr: dict):
        super().__init__(timeout=600)
        self._attr  = attr
        self._ident = _ident(attr)
        self._name  = attr.get("name", "Server")

    async def _power(self, inter: discord.Interaction, signal: str, label: str):
        await inter.response.defer(ephemeral=True)

        if not PTERODACTYL_CLIENT_KEY:
            await inter.followup.send(
                embed=_err(
                    "**`PTERODACTYL_CLIENT_KEY` is not set in `.env`.**\n\n"
                    "Power actions require a Client API key.\n"
                    "Get it from: **Panel → Account → API Credentials**\n"
                    "Make sure the account is an **admin**."
                ),
                ephemeral=True,
            )
            return

        ok, error = await _api.power(self._ident, signal)
        if ok:
            await asyncio.sleep(2)
            embed = await _build_embed(self._attr)
            await inter.edit_original_response(embed=embed, view=self)
            await inter.followup.send(
                embed=_ok(f"**{label}** sent to `{self._name}`."),
                ephemeral=True,
            )
        else:
            await inter.followup.send(
                embed=_err(f"Power action failed:\n```\n{error}\n```"),
                ephemeral=True,
            )

    # Row 0 ── power signals
    @discord.ui.button(label="▶  Start",   style=discord.ButtonStyle.success, row=0)
    async def btn_start(self, inter: discord.Interaction, _: discord.ui.Button):
        await self._power(inter, "start", "Start")

    @discord.ui.button(label="■  Stop",    style=discord.ButtonStyle.danger,  row=0)
    async def btn_stop(self, inter: discord.Interaction, _: discord.ui.Button):
        await self._power(inter, "stop", "Stop")

    @discord.ui.button(label="↺  Restart", style=discord.ButtonStyle.primary, row=0)
    async def btn_restart(self, inter: discord.Interaction, _: discord.ui.Button):
        await self._power(inter, "restart", "Restart")

    @discord.ui.button(label="☠  Kill",    style=discord.ButtonStyle.danger,  row=0)
    async def btn_kill(self, inter: discord.Interaction, _: discord.ui.Button):
        await self._power(inter, "kill", "Kill")

    # Row 1 ── management
    @discord.ui.button(label="🔁  Reinstall", style=discord.ButtonStyle.secondary, row=1)
    async def btn_reinstall(self, inter: discord.Interaction, _: discord.ui.Button):
        if not PTERODACTYL_CLIENT_KEY:
            await inter.response.send_message(
                embed=_err("`PTERODACTYL_CLIENT_KEY` is not set. Cannot reinstall."),
                ephemeral=True,
            )
            return

        confirm = _ReinstallConfirm()
        await inter.response.send_message(
            embed=discord.Embed(
                title="⚠️  Confirm Reinstall",
                description=(
                    f"Reinstall **{self._name}**?\n\n"
                    "This will **permanently wipe all server files**\n"
                    "and reinstall the egg from scratch.\n\n"
                    "**This cannot be undone.**"
                ),
                color=discord.Color.from_rgb(255, 100, 0),
            ),
            view=confirm,
            ephemeral=True,
        )
        await confirm.wait()
        if confirm.confirmed:
            ok, error = await _api.reinstall(self._ident)
            if ok:
                await inter.followup.send(
                    embed=_ok(f"Reinstall started for `{self._name}`."),
                    ephemeral=True,
                )
            else:
                await inter.followup.send(
                    embed=_err(f"Reinstall failed:\n```\n{error}\n```"),
                    ephemeral=True,
                )
        else:
            await inter.followup.send(
                embed=discord.Embed(description="Reinstall cancelled.", color=discord.Color.greyple()),
                ephemeral=True,
            )

    @discord.ui.button(label="🔄  Refresh", style=discord.ButtonStyle.secondary, row=1)
    async def btn_refresh(self, inter: discord.Interaction, _: discord.ui.Button):
        await inter.response.defer(ephemeral=True)
        embed = await _build_embed(self._attr)
        await inter.edit_original_response(embed=embed, view=self)
        await inter.followup.send(
            embed=discord.Embed(description="🔄  Stats refreshed.", color=discord.Color.blurple()),
            ephemeral=True,
        )


# ══════════════════════════════════════════════════════════════════════════════════
# Server picker
# ══════════════════════════════════════════════════════════════════════════════════

class _PickerView(discord.ui.View):
    def __init__(self, servers: list[dict]):
        super().__init__(timeout=180)
        self._map = {str(s["attributes"]["id"]): s["attributes"] for s in servers}

        opts = [
            discord.SelectOption(
                label=trunc(s["attributes"]["name"], 100),
                value=str(s["attributes"]["id"]),
                description=f"ID {s['attributes']['id']}  ·  {_ident(s['attributes'])}",
                emoji="🖥️",
            )
            for s in servers[:25]
        ]
        sel = discord.ui.Select(
            placeholder="🔍  Select a server…",
            options=opts,
            min_values=1,
            max_values=1,
        )
        sel.callback = self._pick
        self.add_item(sel)

    async def _pick(self, inter: discord.Interaction):
        attr = self._map.get(inter.data["values"][0])
        if not attr:
            await inter.response.send_message(embed=_err("Server not found."), ephemeral=True)
            return
        await inter.response.defer(ephemeral=True)
        embed = await _build_embed(attr)
        await inter.followup.send(embed=embed, view=ControlView(attr), ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════════════════════════════════════════

class ManageCog(commands.Cog, name="Manage"):

    def __init__(self, bot: commands.Bot):
        self.bot   = bot
        self.ptero: PterodactylClient = bot.ptero  # type: ignore

    manage_group = app_commands.Group(
        name="manage",
        description="Admin server control — manage any server on the panel.",
    )

    @manage_group.command(
        name="servers",
        description="Open the live admin control panel for any server.",
    )
    @is_owner()
    async def manage_servers(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)

        # Warn if Client key is missing — panel will open but buttons won't work
        client_key_ok = bool(PTERODACTYL_CLIENT_KEY)

        try:
            servers = await self.ptero._paginate(
                "/servers",
                params={"include": "allocations"},
            )
        except PterodactylError as e:
            await inter.followup.send(embed=_err(e.message), ephemeral=True)
            return

        if not servers:
            await inter.followup.send(
                embed=_warn("No servers found on this panel."),
                ephemeral=True,
            )
            return

        warning = ""
        if not client_key_ok:
            warning = (
                "\n\n"
                "⚠️  **`PTERODACTYL_CLIENT_KEY` not set!**\n"
                "Power actions & live stats require a Client API key.\n"
                "Get it from: **Panel Account → API Credentials** (admin account)"
            )

        header = discord.Embed(
            title="🦅  Pterodactyl Admin  ·  Server Control Panel",
            description=(
                f"**{len(servers)}** server(s) on this panel.\n\n"
                "Select any server from the dropdown to view **live stats**\n"
                "and send power actions for **any server, any owner**.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "▶ Start  ·  ■ Stop  ·  ↺ Restart  ·  ☠ Kill  ·  🔁 Reinstall"
                + warning
            ),
            color=discord.Color.from_rgb(88, 101, 242) if client_key_ok else discord.Color.from_rgb(255, 130, 0),
            timestamp=datetime.datetime.utcnow(),
        )
        header.set_footer(text="Admin view  ·  All servers  ·  Pterodactyl Admin Bot")

        await inter.followup.send(
            embed=header,
            view=_PickerView(servers),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ManageCog(bot))

