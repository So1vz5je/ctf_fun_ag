"""Sandboxed Python code execution for CTF solving."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path


async def run_code_in_sandbox(code: str, timeout: int = 30) -> str:
    """Execute Python code in a subprocess and return combined stdout+stderr.

    Uses a temporary file to avoid shell injection issues.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir="/tmp") as f:
        f.write(code)
        script_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3",
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp",
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return f"[TIMEOUT] 代码执行超过 {timeout} 秒"

        output = stdout.decode(errors="replace")
        errors = stderr.decode(errors="replace")
        result = ""
        if output:
            result += output
        if errors:
            result += f"\n[STDERR]\n{errors}"
        return result.strip() or "[无输出]"
    finally:
        Path(script_path).unlink(missing_ok=True)
