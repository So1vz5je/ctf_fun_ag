"""CLI entry point for the CTF Agent."""

from __future__ import annotations

import asyncio
import sys

import click
from rich.console import Console
from rich.panel import Panel

from ctf_agent.config import load_config

console = Console()


@click.group()
@click.option(
    "--config",
    "-c",
    "config_path",
    default="config.yaml",
    help="配置文件路径",
)
@click.pass_context
def main(ctx: click.Context, config_path: str) -> None:
    """CTF Agent - 基于 LLM 的 GZCTF 自动解题系统"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path


@main.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """显示当前配置信息"""
    config = load_config(ctx.obj["config_path"])
    console.print(Panel("[bold]CTF Agent 配置信息[/bold]"))
    console.print(f"  GZCTF URL: {config.gzctf.url or '[未设置]'}")
    console.print(f"  用户名: {config.gzctf.username or '[未设置]'}")
    console.print(f"  LLM 模型: {config.llm.model}")
    console.print(f"  LLM Provider: {config.llm.provider}")
    console.print(f"  自动提交: {config.agent.auto_submit}")
    console.print(f"  题目分类: {', '.join(config.agent.categories)}")


@main.command()
@click.pass_context
def games(ctx: click.Context) -> None:
    """列出所有可用比赛"""
    config = load_config(ctx.obj["config_path"])
    asyncio.run(_list_games(config))


async def _list_games(config):  # noqa: ANN001
    from ctf_agent.api.client import GZCTFClient

    async with GZCTFClient(config.gzctf) as client:
        await client.login()
        game_list = await client.list_games()
        if not game_list:
            console.print("[yellow]暂无比赛[/yellow]")
            return
        from rich.table import Table

        table = Table(title="比赛列表")
        table.add_column("ID", style="cyan")
        table.add_column("标题")
        table.add_column("状态", style="green")
        table.add_column("队伍数")
        for g in game_list:
            table.add_row(str(g.id), g.title, g.status, str(g.team_count))
        console.print(table)


@main.command()
@click.argument("game_id", type=int)
@click.pass_context
def challenges(ctx: click.Context, game_id: int) -> None:
    """列出比赛中的所有题目"""
    config = load_config(ctx.obj["config_path"])
    asyncio.run(_list_challenges(config, game_id))


async def _list_challenges(config, game_id: int):  # noqa: ANN001
    from ctf_agent.api.client import GZCTFClient

    async with GZCTFClient(config.gzctf) as client:
        await client.login()
        categories = await client.get_challenges(game_id)
        from rich.table import Table

        table = Table(title=f"比赛 #{game_id} 题目列表")
        table.add_column("ID", style="cyan")
        table.add_column("分类", style="magenta")
        table.add_column("标题")
        table.add_column("分值", style="green")
        table.add_column("状态")
        for cat, items in categories.items():
            for ch in items:
                status = "[green]已解决[/green]" if ch.is_solved else "[red]未解决[/red]"
                table.add_row(str(ch.id), cat, ch.title, str(ch.score), status)
        console.print(table)


@main.command()
@click.argument("game_id", type=int)
@click.option("--challenge", "-ch", type=int, default=None, help="仅解指定题目")
@click.pass_context
def solve(ctx: click.Context, game_id: int, challenge: int | None) -> None:
    """自动解题（整场比赛或单道题）"""
    config = load_config(ctx.obj["config_path"])

    if not config.gzctf.url:
        console.print("[red]请先配置 GZCTF URL (config.yaml 或 GZCTF_URL 环境变量)[/red]")
        sys.exit(1)
    if not config.llm.api_key:
        console.print("[red]请先配置 LLM API Key (config.yaml 或 LLM_API_KEY 环境变量)[/red]")
        sys.exit(1)

    asyncio.run(_solve(config, game_id, challenge))


async def _solve(config, game_id: int, challenge_id: int | None):  # noqa: ANN001
    from ctf_agent.agent.core import CTFAgent
    from ctf_agent.api.client import GZCTFClient

    async with GZCTFClient(config.gzctf) as client:
        await client.login()
        agent = CTFAgent(config, client)

        if challenge_id:
            result = await agent.solve_challenge(game_id, challenge_id)
            console.print(f"\n[bold]结果: {result}[/bold]")
        else:
            results = await agent.run_game(game_id)
            console.print(f"\n[bold]总结: {results}[/bold]")


if __name__ == "__main__":
    main()
