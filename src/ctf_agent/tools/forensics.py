"""Forensics / steganography challenge tools."""

from __future__ import annotations

import re
import struct
from pathlib import Path

from ctf_agent.tools.base import BaseTool


class ForensicsTool(BaseTool):
    name = "forensics"
    description = "Digital forensics and steganography tool"

    async def run(self, input_data: str | dict) -> str:
        if isinstance(input_data, str):
            return self.analyze_file(input_data)
        action = input_data.get("action", "analyze")
        path = input_data.get("path", "")
        if action == "analyze":
            return self.analyze_file(path)
        elif action == "check_lsb":
            return self.check_lsb_hint(path)
        elif action == "find_hidden":
            return self.find_hidden_data(path)
        elif action == "hex_dump":
            offset = input_data.get("offset", 0)
            length = input_data.get("length", 256)
            return self.hex_dump(path, offset, length)
        return f"Unknown forensics action: {action}"

    @staticmethod
    def analyze_file(path: str) -> str:
        """Comprehensive file analysis for forensics challenges."""
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"

        raw = p.read_bytes()
        size = len(raw)
        results: list[str] = [f"文件: {p.name}", f"大小: {size} bytes"]

        # Check for embedded files (file carving)
        signatures = {
            b"PK\x03\x04": "ZIP 压缩包",
            b"\x89PNG": "PNG 图片",
            b"\xff\xd8\xff": "JPEG 图片",
            b"Rar!": "RAR 压缩包",
            b"%PDF": "PDF 文档",
            b"\x7fELF": "ELF 可执行文件",
            b"GIF8": "GIF 图片",
        }

        for sig, desc in signatures.items():
            positions = []
            start = 0
            while True:
                pos = raw.find(sig, start)
                if pos == -1:
                    break
                positions.append(pos)
                start = pos + 1
            if positions:
                results.append(f"发现 {desc} 签名于偏移: {', '.join(hex(p) for p in positions)}")

        # Check for strings containing "flag"
        flag_matches = re.findall(rb"flag\{[^}]+\}", raw, re.IGNORECASE)
        if flag_matches:
            results.append("发现 flag 模式:")
            for m in flag_matches:
                results.append(f"  - {m.decode(errors='replace')}")

        # Check file trailer
        if raw[-10:] != b"\x00" * 10:
            results.append(f"文件末尾 (hex): {raw[-32:].hex(' ')}")

        # PNG specific checks
        if raw[:4] == b"\x89PNG":
            results.extend(ForensicsTool._analyze_png(raw))

        return "\n".join(results)

    @staticmethod
    def _analyze_png(raw: bytes) -> list[str]:
        """PNG-specific analysis."""
        results: list[str] = []
        pos = 8  # Skip PNG signature
        while pos < len(raw):
            if pos + 8 > len(raw):
                break
            length = struct.unpack(">I", raw[pos : pos + 4])[0]
            chunk_type = raw[pos + 4 : pos + 8].decode(errors="replace")
            results.append(f"PNG Chunk: {chunk_type} (长度: {length}, 偏移: {hex(pos)})")
            if chunk_type == "tEXt" or chunk_type == "iTXt":
                chunk_data = raw[pos + 8 : pos + 8 + length]
                results.append(f"  文本数据: {chunk_data.decode(errors='replace')}")
            if chunk_type == "IEND":
                remaining = len(raw) - (pos + 12)
                if remaining > 0:
                    results.append(f"[!] IEND 后还有 {remaining} bytes 隐藏数据!")
                    hidden = raw[pos + 12 :]
                    results.append(f"  隐藏数据 (hex): {hidden[:64].hex(' ')}")
                    try:
                        text = hidden.decode(errors="replace")
                        results.append(f"  隐藏数据 (text): {text[:200]}")
                    except Exception:
                        pass
                break
            pos += 12 + length

        return results

    @staticmethod
    def check_lsb_hint(path: str) -> str:
        """Check if an image might contain LSB steganography."""
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"

        raw = p.read_bytes()
        if not (raw[:4] == b"\x89PNG" or raw[:2] == b"\xff\xd8"):
            return "不是图片文件，LSB 分析不适用"

        return (
            "该图片可能包含 LSB 隐写。建议使用以下工具:\n"
            "  - stegsolve (Java GUI)\n"
            "  - zsteg (Ruby, 用于 PNG)\n"
            "  - steghide (用于 JPEG)\n"
            "  - python3 PIL 手动提取 LSB\n\n"
            "可以尝试运行代码:\n"
            "```python\n"
            "from PIL import Image\n"
            "img = Image.open('{path}')\n"
            "pixels = list(img.getdata())\n"
            "bits = ''.join(str(p[0] & 1) for p in pixels[:1000])\n"
            "text = ''.join(chr(int(bits[i:i+8], 2)) for i in range(0, len(bits), 8))\n"
            "print(text)\n"
            "```"
        )

    @staticmethod
    def find_hidden_data(path: str) -> str:
        """Look for data hidden after file EOF markers."""
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"

        raw = p.read_bytes()
        results: list[str] = []

        # JPEG: look for data after FFD9
        if raw[:2] == b"\xff\xd8":
            end_pos = raw.find(b"\xff\xd9")
            if end_pos != -1:
                remaining = raw[end_pos + 2 :]
                if remaining:
                    results.append(f"JPEG 结束标记后有 {len(remaining)} bytes 数据")
                    results.append(f"  Hex: {remaining[:64].hex(' ')}")

        # ZIP: might be appended
        zip_pos = raw.find(b"PK\x03\x04")
        if zip_pos > 0:
            results.append(f"发现嵌入的 ZIP 文件于偏移 {hex(zip_pos)}")

        if not results:
            return "未发现隐藏数据"
        return "\n".join(results)

    @staticmethod
    def hex_dump(path: str, offset: int = 0, length: int = 256) -> str:
        """Generate a hex dump of a file region."""
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"

        raw = p.read_bytes()
        chunk = raw[offset : offset + length]
        lines: list[str] = []
        for i in range(0, len(chunk), 16):
            row = chunk[i : i + 16]
            hex_part = " ".join(f"{b:02x}" for b in row)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
            lines.append(f"{offset + i:08x}  {hex_part:<48}  |{ascii_part}|")

        return "\n".join(lines)
