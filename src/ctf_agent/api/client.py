"""GZCTF platform API client."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from rich.console import Console

from ctf_agent.config import GZCTFConfig
from ctf_agent.models.schemas import (
    ChallengeDetail,
    ChallengeInfo,
    ContainerInfo,
    GameDetail,
    GameInfo,
    UserProfile,
)

console = Console()


class GZCTFClient:
    """Async HTTP client for the GZCTF REST API."""

    def __init__(self, config: GZCTFConfig) -> None:
        self.base_url = config.url.rstrip("/")
        self._username = config.username
        self._password = config.password
        self._token = config.token
        self._team_id = config.team_id
        cookies = None
        if self._token:
            cookies = httpx.Cookies()
            cookies.set("GZCTF_Token", self._token)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            follow_redirects=True,
            cookies=cookies,
        )
        self._logged_in = bool(self._token)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> GZCTFClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def login(self) -> UserProfile:
        """Authenticate via username/password or pre-set cookie token."""
        if self._logged_in and self._token:
            console.print("[green]✓ 使用 Token 登录[/green]")
            return await self.get_profile()
        resp = await self._client.post(
            "/api/account/login",
            json={"userName": self._username, "password": self._password},
        )
        resp.raise_for_status()
        self._logged_in = True
        console.print(f"[green]✓ 登录成功: {self._username}[/green]")
        return await self.get_profile()

    async def get_profile(self) -> UserProfile:
        resp = await self._client.get("/api/account/profile")
        resp.raise_for_status()
        return UserProfile.model_validate(resp.json())

    # ------------------------------------------------------------------
    # Games
    # ------------------------------------------------------------------

    async def list_games(self, count: int = 50, skip: int = 0) -> list[GameInfo]:
        """List available games."""
        resp = await self._client.get("/api/game", params={"count": count, "skip": skip})
        resp.raise_for_status()
        payload = resp.json()
        items = payload if isinstance(payload, list) else payload.get("data", payload)
        if isinstance(items, list):
            return [GameInfo.model_validate(g) for g in items]
        return []

    async def get_game(self, game_id: int) -> GameDetail:
        resp = await self._client.get(f"/api/game/{game_id}")
        resp.raise_for_status()
        return GameDetail.model_validate(resp.json())

    async def join_game(
        self,
        game_id: int,
        team_id: int | None = None,
        division_id: int | None = None,
    ) -> None:
        """Join / register for a game."""
        tid = team_id or self._team_id
        if tid is None:
            raise ValueError("team_id is required to join a game")
        body: dict = {"teamId": tid}
        if division_id is not None:
            body["divisionId"] = division_id
        resp = await self._client.post(f"/api/game/{game_id}", json=body)
        resp.raise_for_status()
        console.print(f"[green]✓ 已加入比赛 {game_id}[/green]")

    # ------------------------------------------------------------------
    # Challenges
    # ------------------------------------------------------------------

    async def get_challenges(self, game_id: int) -> dict[str, list[ChallengeInfo]]:
        """Get all challenges grouped by category."""
        resp = await self._client.get(f"/api/game/{game_id}/details")
        resp.raise_for_status()
        data = resp.json()
        challenges_raw = data.get("challenges", {})
        result: dict[str, list[ChallengeInfo]] = {}
        for category, items in challenges_raw.items():
            result[category] = [ChallengeInfo.model_validate(c) for c in items]
        return result

    async def get_challenge_detail(self, game_id: int, challenge_id: int) -> ChallengeDetail:
        resp = await self._client.get(f"/api/game/{game_id}/challenges/{challenge_id}")
        resp.raise_for_status()
        return ChallengeDetail.model_validate(resp.json())

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    async def download_attachment(self, url: str, dest_dir: str | Path = "downloads") -> Path:
        """Download a challenge attachment file."""
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        if url.startswith("/"):
            url = f"{self.base_url}{url}"

        async with self._client.stream("GET", url) as resp:
            resp.raise_for_status()
            # Try to get filename from header or URL
            cd = resp.headers.get("content-disposition", "")
            if "filename=" in cd:
                fname = cd.split("filename=")[-1].strip('" ')
            else:
                fname = url.split("/")[-1].split("?")[0] or "attachment"

            dest = dest_dir / fname
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(8192):
                    f.write(chunk)

        console.print(f"[cyan]↓ 附件已下载: {dest}[/cyan]")
        return dest

    # ------------------------------------------------------------------
    # Containers
    # ------------------------------------------------------------------

    async def create_container(self, game_id: int, challenge_id: int) -> ContainerInfo:
        """Start a challenge container instance."""
        resp = await self._client.post(f"/api/game/{game_id}/challenges/{challenge_id}/container")
        resp.raise_for_status()
        info = ContainerInfo.model_validate(resp.json())
        console.print(f"[green]✓ 靶机已启动: {info.entry}[/green]")
        return info

    async def get_container(self, game_id: int, challenge_id: int) -> ContainerInfo | None:
        resp = await self._client.get(f"/api/game/{game_id}/challenges/{challenge_id}/container")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return ContainerInfo.model_validate(resp.json())

    async def destroy_container(self, game_id: int, challenge_id: int) -> None:
        resp = await self._client.delete(f"/api/game/{game_id}/challenges/{challenge_id}/container")
        resp.raise_for_status()
        console.print("[yellow]✗ 靶机已销毁[/yellow]")

    # ------------------------------------------------------------------
    # Flag submission
    # ------------------------------------------------------------------

    async def submit_flag(self, game_id: int, challenge_id: int, flag: str) -> str:
        """Submit a flag. Returns submission status string."""
        resp = await self._client.post(
            f"/api/game/{game_id}/challenges/{challenge_id}",
            json={"answer": flag},
        )
        resp.raise_for_status()
        data = resp.json()
        status = str(data) if isinstance(data, int) else data.get("status", data)
        return str(status)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    async def wait_for_container(
        self,
        game_id: int,
        challenge_id: int,
        timeout: float = 60,
        poll_interval: float = 2,
    ) -> ContainerInfo:
        """Poll until the container is ready."""
        elapsed = 0.0
        while elapsed < timeout:
            info = await self.get_container(game_id, challenge_id)
            if info and info.entry:
                return info
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"Container not ready after {timeout}s")
