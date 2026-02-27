"""
api_client.py
FULL Production Pterodactyl Application + Client API
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
        self.status  = status
        self.message = message
        super().__init__(f"[HTTP {status}] {message}")


# ═══════════════════════════════════════════════════════════════
# APPLICATION API CLIENT
# ═══════════════════════════════════════════════════════════════

class PterodactylClient:

    def __init__(self):
        self._base    = f"{PTERODACTYL_URL}/api/application"
        self._session: Optional[aiohttp.ClientSession] = None

    # ───────── SESSION ─────────

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {PTERODACTYL_API_KEY}",
            "Accept":        "application/json",
            "Content-Type":  "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ───────── CORE REQUEST ─────────

    async def _request(
        self,
        method:  str,
        endpoint: str,
        payload: Optional[Dict] = None,
        params:  Optional[Dict] = None,
    ) -> Any:
        session = await self._get_session()
        url     = f"{self._base}{endpoint}"

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
                errors  = data.get("errors", [])
                message = errors[0].get("detail") if errors else str(data)
                raise PterodactylError(resp.status, message)

            return data

    # ───────── PAGINATION ─────────

    async def _paginate(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        results: List[Dict] = []
        page = 1

        while True:
            p    = {"page": page, "per_page": 100, **(params or {})}
            data = await self._request("GET", endpoint, params=p)
            results.extend(data.get("data", []))

            meta = data.get("meta", {}).get("pagination", {})
            if meta.get("current_page", 1) >= meta.get("total_pages", 1):
                break
            page += 1

        return results


    # ═══════════════════════════════════════════════════════════════
    # NODES
    # ═══════════════════════════════════════════════════════════════

    async def list_nodes(self) -> List[Dict]:
        return await self._paginate("/nodes")

    async def get_node(self, node_id: int) -> Dict:
        return await self._request("GET", f"/nodes/{node_id}")

    async def create_node(self, payload: Dict) -> Dict:
        return await self._request("POST", "/nodes", payload)

    async def update_node(self, node_id: int, payload: Dict) -> Dict:
        return await self._request("PATCH", f"/nodes/{node_id}", payload)

    async def delete_node(self, node_id: int) -> Dict:
        return await self._request("DELETE", f"/nodes/{node_id}")

    # ── Allocations ──────────────────────────────────────────────

    async def list_allocations(self, node_id: int) -> List[Dict]:
        return await self._paginate(f"/nodes/{node_id}/allocations")

    async def create_allocation(self, node_id: int, payload: Dict) -> Dict:
        return await self._request("POST", f"/nodes/{node_id}/allocations", payload)

    async def delete_allocation(self, node_id: int, alloc_id: int) -> Dict:
        return await self._request("DELETE", f"/nodes/{node_id}/allocations/{alloc_id}")


    # ═══════════════════════════════════════════════════════════════
    # NESTS & EGGS
    # ═══════════════════════════════════════════════════════════════

    async def list_nests(self) -> List[Dict]:
        return await self._paginate("/nests")

    async def get_nest(self, nest_id: int) -> Dict:
        return await self._request("GET", f"/nests/{nest_id}")

    async def list_eggs(self, nest_id: int) -> List[Dict]:
        return await self._paginate(f"/nests/{nest_id}/eggs")

    async def get_egg(self, nest_id: int, egg_id: int) -> Dict:
        return await self._request(
            "GET",
            f"/nests/{nest_id}/eggs/{egg_id}",
            params={"include": "variables,nest,servers,config,script"},
        )

    async def list_all_eggs(self) -> List[Dict]:
        nests = await self.list_nests()
        eggs: List[Dict] = []
        for nest in nests:
            eggs.extend(await self.list_eggs(nest["attributes"]["id"]))
        return eggs


    # ═══════════════════════════════════════════════════════════════
    # MOUNTS
    # ═══════════════════════════════════════════════════════════════

    async def list_mounts(self) -> List[Dict]:
        return await self._paginate("/mounts")

    async def get_mount(self, mount_id: int) -> Dict:
        return await self._request("GET", f"/mounts/{mount_id}")

    async def create_mount(self, payload: Dict) -> Dict:
        return await self._request("POST", "/mounts", payload)

    async def update_mount(self, mount_id: int, payload: Dict) -> Dict:
        return await self._request("PUT", f"/mounts/{mount_id}", payload)

    async def delete_mount(self, mount_id: int) -> Dict:
        return await self._request("DELETE", f"/mounts/{mount_id}")


    # ═══════════════════════════════════════════════════════════════
    # DATABASE HOSTS
    # ═══════════════════════════════════════════════════════════════

    async def list_database_hosts(self) -> List[Dict]:
        return await self._paginate("/database-hosts")

    async def get_database_host(self, host_id: int) -> Dict:
        return await self._request("GET", f"/database-hosts/{host_id}")

    async def create_database_host(self, payload: Dict) -> Dict:
        return await self._request("POST", "/database-hosts", payload)

    async def update_database_host(self, host_id: int, payload: Dict) -> Dict:
        return await self._request("PATCH", f"/database-hosts/{host_id}", payload)

    async def delete_database_host(self, host_id: int) -> Dict:
        return await self._request("DELETE", f"/database-hosts/{host_id}")


    # ═══════════════════════════════════════════════════════════════
    # USERS
    # ═══════════════════════════════════════════════════════════════

    async def list_users(self) -> List[Dict]:
        return await self._paginate("/users")

    async def get_user(self, user_id: int) -> Dict:
        return await self._request("GET", f"/users/{user_id}")

    async def create_user(self, payload: Dict) -> Dict:
        return await self._request("POST", "/users", payload)

    async def update_user(self, user_id: int, payload: Dict) -> Dict:
        return await self._request("PATCH", f"/users/{user_id}", payload)

    async def delete_user(self, user_id: int) -> Dict:
        return await self._request("DELETE", f"/users/{user_id}")


    # ═══════════════════════════════════════════════════════════════
    # SERVERS  (Application API)
    # ═══════════════════════════════════════════════════════════════

    async def list_servers(self) -> List[Dict]:
        return await self._paginate("/servers")

    async def get_server(self, server_id: int) -> Dict:
        return await self._request(
            "GET",
            f"/servers/{server_id}",
            params={"include": "allocations,user,egg,nest,variables,location,node,databases"},
        )

    async def create_server(self, payload: Dict) -> Dict:
        return await self._request("POST", "/servers", payload)

    async def update_server_details(self, server_id: int, payload: Dict) -> Dict:
        """PATCH /api/application/servers/{id}/details"""
        return await self._request("PATCH", f"/servers/{server_id}/details", payload)

    async def update_server_build(self, server_id: int, payload: Dict) -> Dict:
        """PATCH /api/application/servers/{id}/build"""
        return await self._request("PATCH", f"/servers/{server_id}/build", payload)

    async def update_server_startup(self, server_id: int, payload: Dict) -> Dict:
        """PATCH /api/application/servers/{id}/startup"""
        return await self._request("PATCH", f"/servers/{server_id}/startup", payload)

    async def suspend_server(self, server_id: int) -> Dict:
        return await self._request("POST", f"/servers/{server_id}/suspend")

    async def unsuspend_server(self, server_id: int) -> Dict:
        return await self._request("POST", f"/servers/{server_id}/unsuspend")

    async def reinstall_server(self, server_id: int) -> Dict:
        return await self._request("POST", f"/servers/{server_id}/reinstall")

    async def delete_server(self, server_id: int, force: bool = False) -> Dict:
        ep = f"/servers/{server_id}/force" if force else f"/servers/{server_id}"
        return await self._request("DELETE", ep)

    # ── Server databases ─────────────────────────────────────────

    async def list_server_databases(self, server_id: int) -> List[Dict]:
        return await self._paginate(f"/servers/{server_id}/databases")

    async def create_server_database(self, server_id: int, payload: Dict) -> Dict:
        return await self._request("POST", f"/servers/{server_id}/databases", payload)

    async def delete_server_database(self, server_id: int, db_id: int) -> Dict:
        return await self._request("DELETE", f"/servers/{server_id}/databases/{db_id}")


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
        return results


    # ═══════════════════════════════════════════════════════════════
    # NODES
    # ═══════════════════════════════════════════════════════════════

    async def list_nodes(self) -> List[Dict]:
        return await self._paginate("/nodes")

    async def get_node(self, node_id: int) -> Dict:
        return await self._request("GET", f"/nodes/{node_id}")

    async def create_node(self, payload: Dict) -> Dict:
        return await self._request("POST", "/nodes", payload)

    async def update_node(self, node_id: int, payload: Dict) -> Dict:
        return await self._request("PATCH", f"/nodes/{node_id}", payload)

    async def delete_node(self, node_id: int) -> Dict:
        return await self._request("DELETE", f"/nodes/{node_id}")

    # Allocations

    async def list_allocations(self, node_id: int) -> List[Dict]:
        return await self._paginate(f"/nodes/{node_id}/allocations")

    async def create_allocation(self, node_id: int, payload: Dict) -> Dict:
        return await self._request("POST", f"/nodes/{node_id}/allocations", payload)

    async def delete_allocation(self, node_id: int, alloc_id: int) -> Dict:
        return await self._request("DELETE", f"/nodes/{node_id}/allocations/{alloc_id}")


    # ═══════════════════════════════════════════════════════════════
    # NESTS & EGGS
    # ═══════════════════════════════════════════════════════════════

    async def list_nests(self) -> List[Dict]:
        return await self._paginate("/nests")

    async def get_nest(self, nest_id: int) -> Dict:
        return await self._request("GET", f"/nests/{nest_id}")

    async def list_eggs(self, nest_id: int) -> List[Dict]:
        return await self._paginate(f"/nests/{nest_id}/eggs")

    async def get_egg(self, nest_id: int, egg_id: int) -> Dict:
        return await self._request(
            "GET",
            f"/nests/{nest_id}/eggs/{egg_id}",
            params={"include": "variables,nest,servers,config,script"},
        )

    async def list_all_eggs(self) -> List[Dict]:
        nests = await self.list_nests()
        eggs: List[Dict] = []

        for nest in nests:
            nid = nest["attributes"]["id"]
            eggs.extend(await self.list_eggs(nid))

        return eggs


    # ═══════════════════════════════════════════════════════════════
    # MOUNTS
    # ═══════════════════════════════════════════════════════════════

    async def list_mounts(self) -> List[Dict]:
        return await self._paginate("/mounts")

    async def get_mount(self, mount_id: int) -> Dict:
        return await self._request("GET", f"/mounts/{mount_id}")

    async def create_mount(self, payload: Dict) -> Dict:
        return await self._request("POST", "/mounts", payload)

    async def update_mount(self, mount_id: int, payload: Dict) -> Dict:
        return await self._request("PUT", f"/mounts/{mount_id}", payload)

    async def delete_mount(self, mount_id: int) -> Dict:
        return await self._request("DELETE", f"/mounts/{mount_id}")


    # ═══════════════════════════════════════════════════════════════
    # USERS
    # ═══════════════════════════════════════════════════════════════

    async def list_users(self) -> List[Dict]:
        return await self._paginate("/users")

    async def get_user(self, user_id: int) -> Dict:
        return await self._request("GET", f"/users/{user_id}")

    async def create_user(self, payload: Dict) -> Dict:
        return await self._request("POST", "/users", payload)

    async def update_user(self, user_id: int, payload: Dict) -> Dict:
        return await self._request("PATCH", f"/users/{user_id}", payload)

    async def delete_user(self, user_id: int) -> Dict:
        return await self._request("DELETE", f"/users/{user_id}")


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
        endpoint = f"/servers/{server_id}/force" if force else f"/servers/{server_id}"
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
