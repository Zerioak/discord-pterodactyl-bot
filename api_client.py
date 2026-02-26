"""
api_client.py
Async Pterodactyl Application API client.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import aiohttp
from config import PTERODACTYL_URL, PTERODACTYL_API_KEY


# ═══════════════════════════════════════════════════════════════
# ERROR
# ═══════════════════════════════════════════════════════════════

class PterodactylError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"[HTTP {status}] {message}")


# ═══════════════════════════════════════════════════════════════
# CLIENT
# ═══════════════════════════════════════════════════════════════

class PterodactylClient:

    def __init__(self):
        self._base = f"{PTERODACTYL_URL}/api/application"
        self._session: Optional[aiohttp.ClientSession] = None

    # ───────── SESSION ─────────

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {PTERODACTYL_API_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(
                headers=self._headers(),
                timeout=timeout,
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ───────── REQUEST ─────────

    async def _request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:

        session = await self._get_session()
        url = f"{self._base}{endpoint}"

        async with session.request(method, url, json=payload, params=params) as resp:

            if resp.status == 204:
                return {}

            text = await resp.text()
            if not text.strip():
                return {}

            try:
                data = await resp.json(content_type=None)
            except Exception:
                raise PterodactylError(resp.status, text[:500])

            if resp.status >= 400:
                errors = data.get("errors", [])
                message = errors[0].get("detail") if errors else str(data)
                raise PterodactylError(resp.status, message)

            return data

    # ───────── PAGINATION ─────────

    async def _paginate(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:

        results: List[Dict] = []
        page = 1

        while True:
            query = {"per_page": 100, "page": page, **(params or {})}
            data = await self._request("GET", endpoint, params=query)

            results.extend(data.get("data", []))

            meta = data.get("meta", {}).get("pagination", {})
            if meta.get("current_page", 1) >= meta.get("total_pages", 1):
                break

            page += 1

        return results

    # ═══════════════════════════════════════════════════════════════
    # SERVERS
    # ═══════════════════════════════════════════════════════════════

    async def list_servers(self) -> List[Dict]:
        return await self._paginate("/servers")

    async def get_server(self, server_id: int) -> Dict:
        return await self._request(
            "GET",
            f"/servers/{server_id}",
            params={
                "include": "allocations,user,egg,nest,variables,location,node,databases"
            },
        )

    async def create_server(self, payload: Dict) -> Dict:
        return await self._request("POST", "/servers", payload)

    async def suspend_server(self, server_id: int) -> Dict:
        return await self._request("POST", f"/servers/{server_id}/suspend")

    async def unsuspend_server(self, server_id: int) -> Dict:
        return await self._request("POST", f"/servers/{server_id}/unsuspend")

    async def reinstall_server(self, server_id: int) -> Dict:
        return await self._request("POST", f"/servers/{server_id}/reinstall")

    async def delete_server(self, server_id: int, force: bool = False) -> Dict:
        endpoint = (
            f"/servers/{server_id}/force"
            if force
            else f"/servers/{server_id}"
        )
        return await self._request("DELETE", endpoint)

    # ═══════════════════════════════════════════════════════════════
    # ROLES
    # ═══════════════════════════════════════════════════════════════

    async def list_roles(self) -> List[Dict]:
        return await self._paginate("/roles")

    async def get_role(self, role_id: int) -> Dict:
        return await self._request("GET", f"/roles/{role_id}")

    async def create_role(self, payload: Dict) -> Dict:
        return await self._request("POST", "/roles", payload)

    async def update_role(self, role_id: int, payload: Dict) -> Dict:
        return await self._request("PATCH", f"/roles/{role_id}", payload)

    async def delete_role(self, role_id: int) -> Dict:
        return await self._request("DELETE", f"/roles/{role_id}")