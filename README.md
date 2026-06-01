# CTF Agent

基于 LLM 智能体的 [GZCTF](https://github.com/GZTimeWalker/GZCTF) 自动解题系统。

**Web 界面** + CLI 双模式，自动读取比赛题目 → 下载附件 → 启动靶机 → AI 分析解题 → 提交 Flag，全流程自动化。

## 功能特性

### Web 界面
- **设置页面** — 可视化配置 GZCTF 平台地址/账号、LLM API Key/模型、Agent 行为参数
- **比赛列表** — 一键加载所有比赛，点击进入题目列表
- **题目浏览** — 按分类查看所有题目及解题状态，每道题可一键启动 Agent 解题
- **Agent 日志** — 通过 WebSocket 实时查看 Agent 做题全过程（思考、代码执行、靶机交互、flag 提交）
- **任务管理** — 查看所有解题任务状态和历史日志

### 核心能力
- **自动登录** GZCTF 平台并获取比赛列表
- **自动读题** 获取题目描述、提示、分值等信息
- **自动下载附件** 支持各类题目附件的自动下载
- **自动开启靶机** 对于容器类题目自动创建/销毁实例
- **AI 智能解题** 基于 LLM (GPT-4o / DeepSeek 等) 的多轮推理解题
- **自动提交 Flag** 解出后自动提交答案
- **多分类支持** Crypto / Web / Misc / Forensics / PPC / OSINT
- **内置工具集**：
  - 密码学工具（Base64/Hex/ROT13/Caesar 等自动解码）
  - Web 工具（HTTP 请求、注释扫描、robots.txt 检查）
  - 取证工具（文件分析、隐写检测、PNG 块分析、数据提取）
  - 沙箱执行（安全的 Python 代码执行环境）
  - TCP 交互（与靶机的网络通信）

## 架构

```
src/ctf_agent/
├── cli.py              # CLI 命令入口 (info/games/challenges/solve/serve)
├── config.py           # 配置管理（YAML + 环境变量）
├── api/
│   └── client.py       # GZCTF REST API 客户端
├── agent/
│   ├── core.py         # Agent 核心编排（LLM 多轮推理循环）
│   └── prompts.py      # 系统提示词和模板
├── web/
│   ├── app.py          # FastAPI 应用（REST API + WebSocket）
│   └── state.py        # 应用状态管理
├── tools/
│   ├── base.py         # 工具基类
│   ├── crypto.py       # 密码学工具
│   ├── web.py          # Web 渗透工具
│   ├── misc.py         # 杂项工具（flag 搜索、解压、strings）
│   ├── forensics.py    # 取证 / 隐写工具
│   └── sandbox.py      # Python 沙箱执行
└── models/
    └── schemas.py      # Pydantic 数据模型

static/
├── index.html          # 前端单页应用
├── style.css           # 样式
└── app.js              # 前端逻辑
```

## 快速开始

### 1. 安装

```bash
git clone https://github.com/So1vz5je/ctf_fun_ag.git
cd ctf_fun_ag

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. 启动 Web 界面（推荐）

```bash
ctf-agent serve
# 浏览器打开 http://localhost:8000
```

然后在 Web 界面的 **设置** 页面中配置：
- GZCTF 平台地址、用户名、密码、队伍 ID
- LLM API Key、模型名称
- Agent 行为参数

### 3. 或者使用环境变量 / 配置文件

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml 填入信息

# 或通过环境变量：
export GZCTF_URL="https://your-gzctf.com"
export GZCTF_USERNAME="your_username"
export GZCTF_PASSWORD="your_password"
export GZCTF_TEAM_ID="1"
export LLM_API_KEY="sk-..."
export LLM_MODEL="gpt-4o"
```

支持任何 OpenAI 兼容的 API（DeepSeek、Qwen、本地 Ollama 等），设置 `LLM_BASE_URL` 即可：

```bash
# DeepSeek
export LLM_BASE_URL="https://api.deepseek.com"
export LLM_MODEL="deepseek-chat"

# 本地 Ollama
export LLM_BASE_URL="http://localhost:11434/v1"
export LLM_MODEL="qwen2.5:72b"
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `ctf-agent serve` | 启动 Web 界面 (默认 http://localhost:8000) |
| `ctf-agent serve -p 3000` | 指定端口启动 |
| `ctf-agent info` | 显示当前配置信息 |
| `ctf-agent games` | 列出所有比赛 |
| `ctf-agent challenges <game_id>` | 列出比赛题目 |
| `ctf-agent solve <game_id>` | 自动解整场比赛 |
| `ctf-agent solve <game_id> -ch <id>` | 解指定题目 |

## Web 界面截图

### 仪表板
仪表板显示比赛数量、解题任务数、平台连接状态，以及快速开始引导。

### 设置页面
可视化配置所有参数：GZCTF 平台地址/账号、LLM API Key/模型/Temperature、Agent 行为选项（自动提交、自动开靶机、跳过已解决题目等）。

### Agent 解题
选择比赛后一键开始解题，实时日志流显示 Agent 的完整思考过程、代码执行结果、flag 提交结果。

## Agent 工作流程

```
1. 登录 GZCTF 平台
2. 获取比赛题目列表
3. 对每道未解决题目:
   a. 获取题目详情（描述、提示、附件、靶机）
   b. 下载附件（如有）
   c. 启动靶机（如需要）
   d. 构建 prompt 发送给 LLM
   e. LLM 多轮推理循环:
      - analyze: 分析题目
      - run_code: 执行 Python 代码
      - interact: 与靶机交互
      - submit_flag: 提交答案
      - give_up: 放弃
   f. 清理靶机资源
4. 输出解题统计报告
```

## 配置说明

所有配置支持三种方式（优先级：Web 界面 > 环境变量 > config.yaml）：

| 配置项 | 环境变量 | 说明 |
|--------|----------|------|
| `gzctf.url` | `GZCTF_URL` | GZCTF 平台地址 |
| `gzctf.username` | `GZCTF_USERNAME` | 登录用户名 |
| `gzctf.password` | `GZCTF_PASSWORD` | 登录密码 |
| `gzctf.team_id` | `GZCTF_TEAM_ID` | 队伍 ID |
| `llm.api_key` | `LLM_API_KEY` | LLM API Key |
| `llm.base_url` | `LLM_BASE_URL` | 自定义 API 地址 |
| `llm.model` | `LLM_MODEL` | 模型名称 |

## 开发

```bash
pip install -e ".[dev]"

# 代码检查
ruff check src/
ruff format src/

# 类型检查
mypy src/
```

## 技术栈

- **Python 3.11+**
- **FastAPI** + **Uvicorn** — Web 服务器 + WebSocket 实时日志
- **httpx** — 异步 HTTP 客户端
- **OpenAI SDK** — LLM 接口（兼容 OpenAI API 格式）
- **Pydantic** — 数据校验和序列化
- **Click** — CLI 框架
- **Rich** — 终端美化输出
- **PyCryptodome** — 密码学工具
- 前端：纯 HTML/CSS/JS（无 Node 依赖）

## License

MIT
