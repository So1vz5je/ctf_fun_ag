"""Misc / general-purpose CTF tools."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from ctf_agent.tools.base import BaseTool


class MiscTool(BaseTool):
    name = "misc"
    description = "General-purpose CTF analysis tool"

    async def run(self, input_data: str | dict) -> str:
        if isinstance(input_data, str):
            return self.search_flag_pattern(input_data)
        action = input_data.get("action", "search_flag")
        if action == "search_flag":
            return self.search_flag_pattern(input_data.get("data", ""))
        elif action == "extract_zip":
            return self.extract_zip(
                input_data.get("path", ""),
                input_data.get("password", None),
            )
        elif action == "file_info":
            return self.file_info(input_data.get("path", ""))
        elif action == "strings":
            return self.extract_strings(input_data.get("path", ""))
        return f"Unknown misc action: {action}"

    @staticmethod
    def search_flag_pattern(data: str, pattern: str = r"flag\{[^}]+\}") -> str:
        """Search for flag patterns in text."""
        matches = re.findall(pattern, data, re.IGNORECASE)
        if matches:
            return "发现 Flag:\n" + "\n".join(f"  - {m}" for m in matches)
        # Also try common CTF flag formats
        alt_patterns = [
            r"ctf\{[^}]+\}",
            r"CTF\{[^}]+\}",
            r"FLAG\{[^}]+\}",
            r"[A-Za-z]+\{[^}]+\}",
        ]
        for pat in alt_patterns:
            matches = re.findall(pat, data)
            if matches:
                return "发现可能的 Flag:\n" + "\n".join(f"  - {m}" for m in matches)
        return "未发现 flag 模式"

    @staticmethod
    def extract_zip(path: str, password: str | None = None) -> str:
        """Extract a ZIP file and return contents listing."""
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"
        try:
            extract_dir = p.parent / p.stem
            extract_dir.mkdir(parents=True, exist_ok=True)
            pwd = password.encode() if password else None
            with zipfile.ZipFile(p) as zf:
                zf.extractall(extract_dir, pwd=pwd)
                names = zf.namelist()
            return f"解压到 {extract_dir}:\n" + "\n".join(f"  - {n}" for n in names)
        except Exception as e:
            return f"解压失败: {e}"

    @staticmethod
    def file_info(path: str) -> str:
        """Get basic file information."""
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"
        size = p.stat().st_size
        # Read magic bytes
        with open(p, "rb") as f:
            magic = f.read(16)
        magic_hex = magic.hex(" ")

        info = f"文件: {p.name}\n大小: {size} bytes\n魔数: {magic_hex}\n"

        # Identify common file types
        if magic[:4] == b"\x89PNG":
            info += "类型: PNG 图片"
        elif magic[:2] == b"\xff\xd8":
            info += "类型: JPEG 图片"
        elif magic[:4] == b"PK\x03\x04":
            info += "类型: ZIP 压缩包"
        elif magic[:3] == b"GIF":
            info += "类型: GIF 图片"
        elif magic[:4] == b"\x7fELF":
            info += "类型: ELF 可执行文件"
        elif magic[:2] == b"MZ":
            info += "类型: PE/Windows 可执行文件"
        elif magic[:5] == b"%PDF-":
            info += "类型: PDF 文档"
        elif magic[:4] == b"Rar!":
            info += "类型: RAR 压缩包"
        else:
            info += f"类型: 未知 (magic: {magic_hex})"

        return info

    @staticmethod
    def extract_strings(path: str, min_len: int = 6) -> str:
        """Extract printable strings from a file."""
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"
        try:
            raw = p.read_bytes()
            # Extract ASCII strings
            strings = re.findall(rb"[\x20-\x7e]{" + str(min_len).encode() + rb",}", raw)
            decoded = [s.decode() for s in strings[:200]]

            # Highlight potential flags
            flag_strings = [s for s in decoded if re.search(r"flag|ctf", s, re.I)]
            result = f"共发现 {len(decoded)} 个字符串 (长度>={min_len})\n"
            if flag_strings:
                result += "可能包含 flag 的字符串:\n"
                result += "\n".join(f"  - {s}" for s in flag_strings)
            else:
                result += "前 30 个字符串:\n"
                result += "\n".join(f"  - {s}" for s in decoded[:30])
            return result
        except Exception as e:
            return f"提取字符串失败: {e}"
