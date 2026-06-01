"""Cryptography challenge solving tools."""

from __future__ import annotations

import base64
import codecs

from ctf_agent.tools.base import BaseTool


class CryptoTool(BaseTool):
    name = "crypto"
    description = "Cryptography analysis and decoding tool"

    async def run(self, input_data: str | dict) -> str:
        if isinstance(input_data, str):
            return self.auto_decode(input_data)
        action = input_data.get("action", "auto_decode")
        data = input_data.get("data", "")
        if action == "auto_decode":
            return self.auto_decode(data)
        elif action == "base64_decode":
            return self.base64_decode(data)
        elif action == "hex_decode":
            return self.hex_decode(data)
        elif action == "rot13":
            return self.rot13(data)
        elif action == "caesar":
            shift = input_data.get("shift", 0)
            return self.caesar(data, shift)
        return f"Unknown crypto action: {action}"

    @staticmethod
    def auto_decode(data: str) -> str:
        """Try multiple decodings and return all that produce readable output."""
        results: list[str] = []

        # Base64
        try:
            decoded = base64.b64decode(data).decode(errors="replace")
            if decoded.isprintable() or "flag" in decoded.lower():
                results.append(f"[Base64] {decoded}")
        except Exception:
            pass

        # Multi-round base64
        try:
            temp = data
            for i in range(5):
                temp = base64.b64decode(temp).decode(errors="replace")
                if "flag" in temp.lower() or (temp.isprintable() and len(temp) > 5):
                    results.append(f"[Base64 x{i + 1}] {temp}")
                    break
        except Exception:
            pass

        # Hex
        try:
            decoded = bytes.fromhex(data.replace(" ", "")).decode(errors="replace")
            if decoded.isprintable() or "flag" in decoded.lower():
                results.append(f"[Hex] {decoded}")
        except Exception:
            pass

        # ROT13
        try:
            decoded = codecs.decode(data, "rot_13")
            if "flag" in decoded.lower():
                results.append(f"[ROT13] {decoded}")
        except Exception:
            pass

        # Caesar brute force
        for shift in range(1, 26):
            decoded = CryptoTool.caesar(data, shift)
            if "flag" in decoded.lower():
                results.append(f"[Caesar shift={shift}] {decoded}")
                break

        # Base32
        try:
            decoded = base64.b32decode(data).decode(errors="replace")
            if decoded.isprintable() or "flag" in decoded.lower():
                results.append(f"[Base32] {decoded}")
        except Exception:
            pass

        if results:
            return "\n".join(results)
        return "未能自动解码，请尝试其他方法"

    @staticmethod
    def base64_decode(data: str) -> str:
        try:
            return base64.b64decode(data).decode(errors="replace")
        except Exception as e:
            return f"Base64 解码失败: {e}"

    @staticmethod
    def hex_decode(data: str) -> str:
        try:
            return bytes.fromhex(data.replace(" ", "")).decode(errors="replace")
        except Exception as e:
            return f"Hex 解码失败: {e}"

    @staticmethod
    def rot13(data: str) -> str:
        return codecs.decode(data, "rot_13")

    @staticmethod
    def caesar(data: str, shift: int) -> str:
        result = []
        for c in data:
            if c.isalpha():
                base = ord("A") if c.isupper() else ord("a")
                result.append(chr((ord(c) - base + shift) % 26 + base))
            else:
                result.append(c)
        return "".join(result)
