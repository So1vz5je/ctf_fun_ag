# 🤖 CTF Agent

基于 LLM 智能体的 [GZCTF](https://github.com/GZTimeWalker/GZCTF) 自动解题系统。

自动读取比赛题目 → 下载附件 → 启动靶机 → AI 分析解题 → 提交 Flag，全流程自动化。

## 功能特性

- **自动登录** GZCTF 平台并获取比赛列表
- **自动读题** 获取题目描述、提示、分值等信息
- **自动下载附件** 支持各类题目附件的自动下载
- **自动开启靶机** 对于容器类题目自动创建/销毁实例
- **AI 智能解题** 基于 LLM (GPT-4o 等) 的多轮推理解题
- **自动提交 Flag** 解出后自动提交答案
- **多分类支持** Crypto / Web / Misc / Forensics / PPC / OSINT
- **内置工具集**：
  - 密码学工具（Base64/Hex/ROT13/Caesar 等自动解码）
  - Web 工具（HTTP 请求、注释扫描、robots.txt 检查）
  - 取证工具（文件分析、隐写检测、数据提取）
  - 沙箱执行（安全的 Python 代码执行环境）
  - TCP 交互（与靶机的网络通信）

## 架构

```
src/ctf_agent/
├── cli.py              # CLI 命令入口
├── config.py           # 配置管理（YAML + 环境变量）
├── api/
│   └── client.py       # GZCTF REST API 客户端
├── agent/
│   ├── core.py         # Agent 核心编排（LLM 多轮推理循环）
│   └── prompts.py      # 系统提示词和模板
├── tools/
│   ├── base.py         # 工具基类
│   ├── crypto.py       # 密码学工具
│   ├── web.py          # Web 渗透工具
│   ├── misc.py         # 杂项工具（flag 搜索、解压、strings）
│   ├── forensics.py    # 取证 / 隐写工具
│   └── sandbox.py      # Python 沙箱执行
└── models/
    └── schemas.py      # Pydantic 数据模型
```

## 快速开始

### 1. 安装

```bash
# 克隆项目
git clone https://github.com/So1vz5je/ctf_fun_ag.git
cd ctf_fun_ag

# 安装（推荐使用虚拟环境）
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. 配置

```bash
# 复制示例配置
cp config.example.yaml config.yaml

# 编辑配置文件填入你的信息
# 或者使用环境变量：
export GZCTF_URL="https://your-gzctf.com"
export GZCTF_USERNAME="your_username"
export GZCTF_PASSWORD="your_password"
export GZCTF_TEAM_ID="1"
export LLM_API_KEY="sk-..."
export LLM_MODEL="gpt-4o"
```

支持任何 OpenAI 兼容的 API（如 DeepSeek、Qwen、本地 Ollama 等），只需设置 `LLM_BASE_URL`：

```bash
# 使用 DeepSeek
export LLM_BASE_URL="https://api.deepseek.com"
export LLM_MODEL="deepseek-chat"

# 使用本地 Ollama
export LLM_BASE_URL="http://localhost:11434/v1"
export LLM_MODEL="qwen2.5:72b"
```

### 3. 使用

```bash
# 查看配置信息
ctf-agent info

# 列出所有比赛
ctf-agent games

# 列出比赛中的题目
ctf-agent challenges 1

# 自动解整场比赛
ctf-agent solve 1

# 只解指定题目
ctf-agent solve 1 --challenge 5
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `ctf-agent info` | 显示当前配置信息 |
| `ctf-agent games` | 列出所有比赛 |
| `ctf-agent challenges <game_id>` | 列出比赛题目 |
| `ctf-agent solve <game_id>` | 自动解整场比赛 |
| `ctf-agent solve <game_id> -ch <id>` | 解指定题目 |

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

所有配置支持 YAML 文件和环境变量两种方式，环境变量优先级更高：

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
# 安装开发依赖
pip install -e ".[dev]"

# 代码检查
ruff check src/
ruff format src/

# 类型检查
mypy src/
```

## 技术栈

- **Python 3.11+**
- **httpx** - 异步 HTTP 客户端
- **OpenAI SDK** - LLM 接口（兼容 OpenAI API 格式）
- **Pydantic** - 数据校验和序列化
- **Click** - CLI 框架
- **Rich** - 终端美化输出
- **PyCryptodome** - 密码学工具

## License

MIT
