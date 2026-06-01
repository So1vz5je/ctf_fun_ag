"""Core CTF Agent: orchestrates challenge solving with LLM + tools."""

from __future__ import annotations

import json
import re
import traceback
from pathlib import Path

from openai import AsyncOpenAI
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ctf_agent.agent.prompts import SYSTEM_PROMPT, build_challenge_prompt
from ctf_agent.api.client import GZCTFClient
from ctf_agent.config import AppConfig
from ctf_agent.models.schemas import ChallengeDetail, ChallengeInfo
from ctf_agent.tools.sandbox import run_code_in_sandbox

console = Console()


class CTFAgent:
    """Orchestrates the full CTF solving pipeline."""

    def __init__(self, config: AppConfig, client: GZCTFClient) -> None:
        self.config = config
        self.api = client
        self.llm = AsyncOpenAI(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
        )
        self.model = config.llm.model
        self.download_dir = Path(config.agent.download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # High-level pipeline
    # ------------------------------------------------------------------

    async def run_game(self, game_id: int) -> dict[int, str]:
        """Run the agent on all unsolved challenges in a game.

        Returns a dict of {challenge_id: result_status}.
        """
        console.print(Panel(f"[bold]开始比赛 #{game_id} 自动解题[/bold]"))

        categories = await self.api.get_challenges(game_id)
        results: dict[int, str] = {}

        # Build flat list
        all_challenges: list[tuple[str, ChallengeInfo]] = []
        for cat, challenges in categories.items():
            for ch in challenges:
                all_challenges.append((cat, ch))

        # Print summary table
        table = Table(title="题目列表")
        table.add_column("ID", style="cyan")
        table.add_column("分类", style="magenta")
        table.add_column("标题")
        table.add_column("分值", style="green")
        table.add_column("状态")
        for cat, ch in all_challenges:
            status = "[green]已解决[/green]" if ch.is_solved else "[red]未解决[/red]"
            table.add_row(str(ch.id), cat, ch.title, str(ch.score), status)
        console.print(table)

        allowed_cats = self.config.agent.categories
        for cat, ch in all_challenges:
            if self.config.agent.skip_solved and ch.is_solved:
                console.print(f"[dim]跳过已解决: {ch.title}[/dim]")
                results[ch.id] = "skipped_solved"
                continue
            if allowed_cats and cat not in allowed_cats:
                console.print(f"[dim]跳过分类 {cat}: {ch.title}[/dim]")
                results[ch.id] = "skipped_category"
                continue

            result = await self.solve_challenge(game_id, ch.id, cat)
            results[ch.id] = result

        # Summary
        solved = sum(1 for v in results.values() if v == "Accepted")
        total = len(results)
        console.print(
            Panel(
                f"[bold]比赛完成: {solved}/{total} 题解决[/bold]",
                style="green" if solved > 0 else "red",
            )
        )
        return results

    async def solve_challenge(self, game_id: int, challenge_id: int, category: str = "") -> str:
        """Attempt to solve a single challenge. Returns result status."""
        console.print(f"\n[bold cyan]═══ 正在解题: #{challenge_id} ═══[/bold cyan]")

        try:
            detail = await self.api.get_challenge_detail(game_id, challenge_id)
        except Exception as e:
            console.print(f"[red]获取题目详情失败: {e}[/red]")
            return "error"

        console.print(f"  标题: {detail.title}")
        console.print(f"  分类: {category or detail.tag}")
        console.print(f"  类型: {detail.type}")
        console.print(f"  分值: {detail.score}")

        # Step 1: Download attachment if exists
        attachment_info = "无附件"
        file_content = "无附件内容"
        if detail.has_attachment:
            try:
                path = await self.api.download_attachment(
                    detail.attachment.url,  # type: ignore[union-attr]
                    self.download_dir / str(challenge_id),
                )
                attachment_info = f"已下载到: {path}"
                file_content = self._read_file_preview(path)
            except Exception as e:
                attachment_info = f"下载失败: {e}"

        # Step 2: Start container if needed
        container_info = "无靶机"
        if detail.is_container_based and self.config.agent.auto_start_container:
            try:
                existing = await self.api.get_container(game_id, challenge_id)
                if existing and existing.entry:
                    container_info = f"靶机地址: {existing.entry}"
                else:
                    info = await self.api.create_container(game_id, challenge_id)
                    info = await self.api.wait_for_container(game_id, challenge_id, timeout=60)
                    container_info = f"靶机地址: {info.entry}"
            except Exception as e:
                container_info = f"靶机启动失败: {e}"

        # Step 3: LLM solving loop
        result = await self._llm_solve_loop(
            game_id=game_id,
            detail=detail,
            category=category,
            attachment_info=attachment_info,
            container_info=container_info,
            file_content=file_content,
        )

        # Step 4: Cleanup container
        if detail.is_container_based:
            try:
                await self.api.destroy_container(game_id, challenge_id)
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------
    # LLM interaction loop
    # ------------------------------------------------------------------

    async def _llm_solve_loop(
        self,
        game_id: int,
        detail: ChallengeDetail,
        category: str,
        attachment_info: str,
        container_info: str,
        file_content: str,
    ) -> str:
        """Iterative LLM loop: analyze → act → observe → repeat."""
        prompt = build_challenge_prompt(
            title=detail.title,
            category=category or detail.tag,
            score=detail.score,
            challenge_type=detail.type,
            content=detail.content,
            hints=detail.hints,
            attachment_info=attachment_info,
            container_info=container_info,
            file_content=file_content,
        )

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        max_rounds = self.config.agent.max_retries * 2 + 1
        for round_num in range(max_rounds):
            console.print(f"\n  [dim]第 {round_num + 1} 轮推理...[/dim]")

            try:
                response = await self.llm.chat.completions.create(
                    model=self.model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=self.config.llm.temperature,
                    max_tokens=self.config.llm.max_tokens,
                    response_format={"type": "json_object"},
                )
            except Exception as e:
                console.print(f"[red]  LLM 调用失败: {e}[/red]")
                return "llm_error"

            raw = response.choices[0].message.content or "{}"
            try:
                action_data = json.loads(raw)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
                if json_match:
                    action_data = json.loads(json_match.group(1))
                else:
                    console.print("[red]  无法解析 LLM 响应[/red]")
                    messages.append({"role": "assistant", "content": raw})
                    messages.append(
                        {
                            "role": "user",
                            "content": "请以有效的 JSON 格式回复。",
                        }
                    )
                    continue

            thinking = action_data.get("thinking", "")
            action = action_data.get("action", "")
            action_input = action_data.get("action_input", "")
            confidence = action_data.get("confidence", 0)

            console.print(f"  [dim]思考: {thinking[:120]}...[/dim]")
            console.print(f"  动作: [yellow]{action}[/yellow] (置信度: {confidence})")

            messages.append({"role": "assistant", "content": raw})

            # Dispatch action
            if action == "submit_flag":
                flag = str(action_input).strip()
                if not flag:
                    messages.append({"role": "user", "content": "Flag 不能为空，请继续分析。"})
                    continue
                return await self._try_submit(game_id, detail.id, flag)

            elif action == "run_code":
                code = str(action_input)
                observation = await self._execute_code(code)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"代码执行结果:\n```\n{observation}\n```\n\n"
                            "请根据结果继续分析。如果发现了 flag，请使用 submit_flag 提交。"
                        ),
                    }
                )

            elif action == "analyze":
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "分析完成。请决定下一步行动：执行代码(run_code)、提交flag(submit_flag)或放弃(give_up)。"
                        ),
                    }
                )

            elif action == "interact":
                # Network interaction with target
                if isinstance(action_input, dict):
                    host = action_input.get("host", "")
                    port = action_input.get("port", 0)
                    commands = action_input.get("commands", [])
                    observation = await self._interact_with_target(host, port, commands)
                else:
                    observation = "interact 需要提供 {host, port, commands} 参数"
                messages.append(
                    {
                        "role": "user",
                        "content": f"交互结果:\n```\n{observation}\n```\n\n请根据结果继续分析。",
                    }
                )

            elif action == "give_up":
                console.print("  [yellow]Agent 决定放弃此题[/yellow]")
                return "gave_up"

            else:
                messages.append(
                    {
                        "role": "user",
                        "content": f"未知动作: {action}。请使用 analyze/run_code/submit_flag/interact/give_up。",
                    }
                )

        console.print("  [yellow]达到最大轮次，放弃[/yellow]")
        return "max_rounds"

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    async def _try_submit(self, game_id: int, challenge_id: int, flag: str) -> str:
        """Submit flag and return result."""
        console.print(f"  [bold]提交 Flag: {flag}[/bold]")
        if not self.config.agent.auto_submit:
            console.print("  [yellow]自动提交已禁用，跳过[/yellow]")
            return "not_submitted"
        try:
            result = await self.api.submit_flag(game_id, challenge_id, flag)
            console.print(f"  [bold green]提交结果: {result}[/bold green]")
            return result
        except Exception as e:
            console.print(f"  [red]提交失败: {e}[/red]")
            return "submit_error"

    async def _execute_code(self, code: str) -> str:
        """Run Python code in sandbox and return output."""
        console.print("  [dim]执行代码...[/dim]")
        try:
            result = await run_code_in_sandbox(code, timeout=30)
            output = result[:2000] if len(result) > 2000 else result
            console.print(f"  [dim]输出: {output[:200]}...[/dim]")
            return output
        except Exception as e:
            tb = traceback.format_exc()
            return f"执行出错: {e}\n{tb}"

    async def _interact_with_target(self, host: str, port: int, commands: list[str]) -> str:
        """Simple TCP interaction with a challenge target."""
        import asyncio

        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=10)
            output_parts: list[str] = []

            # Read initial banner
            try:
                banner = await asyncio.wait_for(reader.read(4096), timeout=5)
                output_parts.append(banner.decode(errors="replace"))
            except TimeoutError:
                pass

            for cmd in commands:
                writer.write((cmd + "\n").encode())
                await writer.drain()
                try:
                    data = await asyncio.wait_for(reader.read(4096), timeout=5)
                    output_parts.append(data.decode(errors="replace"))
                except TimeoutError:
                    output_parts.append("[timeout reading response]")

            writer.close()
            await writer.wait_closed()
            return "\n".join(output_parts)

        except Exception as e:
            return f"连接失败: {e}"

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_file_preview(path: Path, max_bytes: int = 4096) -> str:
        """Read a file preview (text or hex)."""
        try:
            # Try text first
            text = path.read_text(errors="replace")
            if len(text) > max_bytes:
                return text[:max_bytes] + f"\n... (truncated, total {len(text)} chars)"
            return text
        except Exception:
            # Fall back to hex preview
            raw = path.read_bytes()[:max_bytes]
            hex_str = raw.hex(" ", 1)
            return f"[binary file, hex preview]\n{hex_str}"
