"""Web challenge solving tools."""

from __future__ import annotations

import re

import httpx

from ctf_agent.tools.base import BaseTool


class WebTool(BaseTool):
    name = "web"
    description = "Web challenge analysis and exploitation tool"

    async def run(self, input_data: str | dict) -> str:
        if isinstance(input_data, str):
            return await self.fetch_url(input_data)
        action = input_data.get("action", "fetch")
        if action == "fetch":
            return await self.fetch_url(input_data.get("url", ""))
        elif action == "post":
            return await self.post_url(
                input_data.get("url", ""),
                input_data.get("data", {}),
                input_data.get("headers", {}),
            )
        elif action == "scan_comments":
            return await self.scan_comments(input_data.get("url", ""))
        elif action == "scan_robots":
            return await self.scan_robots(input_data.get("url", ""))
        elif action == "check_headers":
            return await self.check_headers(input_data.get("url", ""))
        return f"Unknown web action: {action}"

    @staticmethod
    async def fetch_url(url: str) -> str:
        """Fetch a URL and return its content."""
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url)
                return f"[Status: {resp.status_code}]\n{resp.text[:4000]}"
        except Exception as e:
            return f"请求失败: {e}"

    @staticmethod
    async def post_url(url: str, data: dict, headers: dict | None = None) -> str:
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.post(url, json=data, headers=headers or {})
                return f"[Status: {resp.status_code}]\n{resp.text[:4000]}"
        except Exception as e:
            return f"请求失败: {e}"

    @staticmethod
    async def scan_comments(url: str) -> str:
        """Scan HTML source for comments that might contain flags or hints."""
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url)
                comments = re.findall(r"<!--(.*?)-->", resp.text, re.DOTALL)
                if comments:
                    return "HTML 注释:\n" + "\n".join(f"  - {c.strip()}" for c in comments)
                return "未发现 HTML 注释"
        except Exception as e:
            return f"扫描失败: {e}"

    @staticmethod
    async def scan_robots(url: str) -> str:
        """Check robots.txt for hidden paths."""
        base = url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(f"{base}/robots.txt")
                if resp.status_code == 200:
                    return f"robots.txt:\n{resp.text[:2000]}"
                return "robots.txt 不存在"
        except Exception as e:
            return f"请求失败: {e}"

    @staticmethod
    async def check_headers(url: str) -> str:
        """Check HTTP response headers for flags or hints."""
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url)
                header_lines = [f"  {k}: {v}" for k, v in resp.headers.items()]
                return "响应头:\n" + "\n".join(header_lines)
        except Exception as e:
            return f"请求失败: {e}"
