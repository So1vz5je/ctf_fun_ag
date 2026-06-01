"""FastAPI application for CTF Agent web interface."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ctf_agent.web.state import AppState

STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static"

app = FastAPI(title="CTF Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

state = AppState()


# ── Models ────────────────────────────────────────────────────────────


class SettingsUpdate(BaseModel):
    gzctf_url: str = ""
    gzctf_username: str = ""
    gzctf_password: str = ""
    gzctf_token: str = ""
    gzctf_team_id: int | None = None
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_base_url: str | None = None
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    agent_max_retries: int = 3
    agent_auto_submit: bool = True
    agent_auto_start_container: bool = True
    agent_skip_solved: bool = True
    agent_categories: list[str] | None = None


class SolveRequest(BaseModel):
    game_id: int
    challenge_id: int | None = None
    concurrent: bool = True


# ── Settings ──────────────────────────────────────────────────────────


@app.get("/api/settings")
async def get_settings():
    cfg = state.config
    return {
        "gzctf_url": cfg.gzctf.url,
        "gzctf_username": cfg.gzctf.username,
        "gzctf_password": "••••••••" if cfg.gzctf.password else "",
        "gzctf_token": _mask_key(cfg.gzctf.token) if cfg.gzctf.token else "",
        "gzctf_team_id": cfg.gzctf.team_id,
        "llm_provider": cfg.llm.provider,
        "llm_api_key": _mask_key(cfg.llm.api_key),
        "llm_base_url": cfg.llm.base_url,
        "llm_model": cfg.llm.model,
        "llm_temperature": cfg.llm.temperature,
        "llm_max_tokens": cfg.llm.max_tokens,
        "agent_max_retries": cfg.agent.max_retries,
        "agent_auto_submit": cfg.agent.auto_submit,
        "agent_auto_start_container": cfg.agent.auto_start_container,
        "agent_skip_solved": cfg.agent.skip_solved,
        "agent_categories": cfg.agent.categories,
    }


@app.post("/api/settings")
async def update_settings(req: SettingsUpdate):
    cfg = state.config
    cfg.gzctf.url = req.gzctf_url
    cfg.gzctf.username = req.gzctf_username
    if req.gzctf_password and req.gzctf_password != "••••••••":
        cfg.gzctf.password = req.gzctf_password
    if req.gzctf_token and "••••" not in req.gzctf_token:
        cfg.gzctf.token = req.gzctf_token
    cfg.gzctf.team_id = req.gzctf_team_id
    cfg.llm.provider = req.llm_provider
    if req.llm_api_key and "••••" not in req.llm_api_key:
        cfg.llm.api_key = req.llm_api_key
    cfg.llm.base_url = req.llm_base_url
    cfg.llm.model = req.llm_model
    cfg.llm.temperature = req.llm_temperature
    cfg.llm.max_tokens = req.llm_max_tokens
    cfg.agent.max_retries = req.agent_max_retries
    cfg.agent.auto_submit = req.agent_auto_submit
    cfg.agent.auto_start_container = req.agent_auto_start_container
    cfg.agent.skip_solved = req.agent_skip_solved
    if req.agent_categories is not None:
        cfg.agent.categories = req.agent_categories

    state.save_config()
    await state.reset_client()

    return {"status": "ok"}


# ── GZCTF proxy endpoints ────────────────────────────────────────────


@app.post("/api/login")
async def login():
    client = await state.get_client()
    profile = await client.login()
    return profile.model_dump(by_alias=True)


@app.get("/api/games")
async def list_games():
    client = await state.get_client()
    games = await client.list_games()
    return [g.model_dump(by_alias=True) for g in games]


@app.get("/api/games/{game_id}")
async def get_game(game_id: int):
    client = await state.get_client()
    detail = await client.get_game(game_id)
    return detail.model_dump(by_alias=True)


@app.get("/api/games/{game_id}/challenges")
async def get_challenges(game_id: int):
    client = await state.get_client()
    categories = await client.get_challenges(game_id)
    result = {}
    for cat, items in categories.items():
        result[cat] = [c.model_dump(by_alias=True) for c in items]
    return result


@app.get("/api/games/{game_id}/challenges/{challenge_id}")
async def get_challenge_detail(game_id: int, challenge_id: int):
    client = await state.get_client()
    detail = await client.get_challenge_detail(game_id, challenge_id)
    return detail.model_dump(by_alias=True)


# ── Agent solve ───────────────────────────────────────────────────────


@app.post("/api/solve")
async def start_solve(req: SolveRequest):
    task_id = str(uuid.uuid4())[:8]
    state.tasks[task_id] = {
        "status": "running",
        "game_id": req.game_id,
        "challenge_id": req.challenge_id,
        "concurrent": req.concurrent,
        "logs": [],
    }
    asyncio.create_task(_run_solve(task_id, req.game_id, req.challenge_id, req.concurrent))
    return {"task_id": task_id, "status": "running"}


@app.get("/api/tasks")
async def list_tasks():
    return {
        tid: {
            "status": t["status"],
            "game_id": t["game_id"],
            "challenge_id": t["challenge_id"],
            "log_count": len(t["logs"]),
        }
        for tid, t in state.tasks.items()
    }


@app.get("/api/tasks/{task_id}/logs")
async def get_task_logs(task_id: str):
    task = state.tasks.get(task_id)
    if not task:
        return {"error": "task not found"}
    return {"status": task["status"], "logs": task["logs"]}


# ── WebSocket for real-time logs ──────────────────────────────────────


@app.websocket("/ws/logs/{task_id}")
async def ws_logs(websocket: WebSocket, task_id: str):
    await websocket.accept()
    seen = 0
    try:
        while True:
            task = state.tasks.get(task_id)
            if not task:
                await websocket.send_json({"type": "error", "message": "task not found"})
                break

            logs = task["logs"]
            if len(logs) > seen:
                for log in logs[seen:]:
                    await websocket.send_json(log)
                seen = len(logs)

            if task["status"] != "running":
                await websocket.send_json({"type": "done", "status": task["status"]})
                break

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


# ── Background solve runner ───────────────────────────────────────────


async def _run_solve(
    task_id: str,
    game_id: int,
    challenge_id: int | None,
    concurrent: bool = True,
):
    from ctf_agent.agent.core import CTFAgent

    task = state.tasks[task_id]

    def emit(log_type: str, message: str, **extra):
        entry = {"type": log_type, "message": message, **extra}
        task["logs"].append(entry)

    try:
        client = await state.get_client()
        await client.login()
        emit("info", "登录成功")

        agent = CTFAgent(state.config, client)

        if challenge_id:
            emit("info", f"开始解题: 比赛#{game_id} 题目#{challenge_id}")
            _patch_agent_logging(agent, emit)
            result = await agent.solve_challenge(game_id, challenge_id)
            emit("result", f"解题结果: {result}", result=result)
        elif concurrent:
            # Per-category concurrent agents
            emit(
                "info",
                f"开始并发解题: 比赛#{game_id} (每个方向一个 Agent)",
            )
            results = await _run_concurrent_by_category(agent, game_id, emit)
            solved = sum(1 for v in results.values() if v == "Accepted")
            total = len(results)
            emit(
                "result",
                f"比赛完成: {solved}/{total} 题解决",
                results=results,
            )
        else:
            emit("info", f"开始顺序解题: 比赛#{game_id}")
            _patch_agent_logging(agent, emit)
            results = await agent.run_game(game_id)
            solved = sum(1 for v in results.values() if v == "Accepted")
            total = len(results)
            emit(
                "result",
                f"比赛完成: {solved}/{total} 题解决",
                results=results,
            )

        task["status"] = "completed"
    except Exception as e:
        emit("error", f"解题出错: {e}")
        task["status"] = "error"


async def _run_concurrent_by_category(agent, game_id: int, emit):
    """Run one agent per category concurrently."""
    from ctf_agent.agent.core import CTFAgent

    categories = await agent.api.get_challenges(game_id)
    all_results: dict[int, str] = {}
    allowed = agent.config.agent.categories

    # Group challenges by category
    cat_tasks = {}
    for cat, challenges in categories.items():
        if allowed and cat not in allowed:
            for ch in challenges:
                all_results[ch.id] = "skipped_category"
                emit("info", f"[{cat}] 跳过分类: {ch.title}")
            continue

        unsolved = [ch for ch in challenges if not (agent.config.agent.skip_solved and ch.is_solved)]
        if not unsolved:
            for ch in challenges:
                if ch.is_solved:
                    all_results[ch.id] = "skipped_solved"
            continue

        cat_tasks[cat] = unsolved
        emit(
            "category_start",
            f"[{cat}] 启动 Agent — {len(unsolved)} 道题待解",
            category=cat,
            count=len(unsolved),
        )

    async def _solve_category(cat: str, challenges):
        cat_agent = CTFAgent(agent.config, agent.api)

        def cat_emit(log_type: str, message: str, **extra):
            emit(log_type, f"[{cat}] {message}", category=cat, **extra)

        _patch_agent_logging(cat_agent, cat_emit)

        results = {}
        for ch in challenges:
            cat_emit("info", f"开始: {ch.title} (#{ch.id})")
            try:
                r = await cat_agent.solve_challenge(game_id, ch.id, cat)
                results[ch.id] = r
                status_icon = "solved" if r == "Accepted" else "failed"
                cat_emit(
                    "challenge_done",
                    f"{ch.title} → {r}",
                    status=status_icon,
                )
            except Exception as e:
                results[ch.id] = "error"
                cat_emit("error", f"{ch.title} 出错: {e}")
        return results

    # Run all categories concurrently
    tasks = [_solve_category(cat, chs) for cat, chs in cat_tasks.items()]
    category_results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in category_results:
        if isinstance(result, dict):
            all_results.update(result)
        elif isinstance(result, Exception):
            emit("error", f"分类 Agent 出错: {result}")

    return all_results


def _patch_agent_logging(agent, emit):
    original_solve_loop = agent._llm_solve_loop

    async def patched_solve_loop(game_id, detail, category, attachment_info, container_info, file_content):
        emit(
            "challenge",
            f"题目: {detail.title}",
            title=detail.title,
            category=category,
            score=detail.score,
        )
        emit(
            "info",
            f"分类: {category} | 类型: {detail.type} | 分值: {detail.score}",
        )

        if detail.content:
            emit("description", detail.content[:500])
        if attachment_info != "无附件":
            emit("attachment", attachment_info)
        if container_info != "无靶机":
            emit("container", container_info)

        original_llm_create = agent.llm.chat.completions.create

        async def logged_llm_create(**kwargs):
            emit("thinking", "LLM 推理中...")
            result = await original_llm_create(**kwargs)
            raw = result.choices[0].message.content or "{}"
            try:
                data = json.loads(raw)
                emit(
                    "llm_response",
                    data.get("thinking", ""),
                    action=data.get("action", ""),
                    action_input=str(data.get("action_input", ""))[:500],
                    confidence=data.get("confidence", 0),
                )
            except json.JSONDecodeError:
                emit("llm_response", raw[:500])
            return result

        agent.llm.chat.completions.create = logged_llm_create

        original_execute = agent._execute_code

        async def logged_execute(code):
            emit("code", code[:1000])
            result = await original_execute(code)
            emit("code_output", result[:1000])
            return result

        agent._execute_code = logged_execute

        original_submit = agent._try_submit

        async def logged_submit(gid, cid, flag):
            emit("flag_submit", f"提交 Flag: {flag}", flag=flag)
            result = await original_submit(gid, cid, flag)
            emit("flag_result", f"提交结果: {result}", result=result)
            return result

        agent._try_submit = logged_submit

        return await original_solve_loop(
            game_id=game_id,
            detail=detail,
            category=category,
            attachment_info=attachment_info,
            container_info=container_info,
            file_content=file_content,
        )

    agent._llm_solve_loop = patched_solve_loop


# ── Static files & SPA ────────────────────────────────────────────────


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "CTF Agent API is running."}


def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return key
    return key[:4] + "••••" + key[-4:]
