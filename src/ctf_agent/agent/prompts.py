"""Prompt templates for the CTF solving agent."""

SYSTEM_PROMPT = """\
你是一个专业的 CTF (Capture The Flag) 解题智能体。你的任务是分析 CTF 题目并尝试找到 flag。

## 你的能力
1. **分析题目描述和提示**：理解题目要求
2. **分析附件内容**：对下载的文件进行分析
3. **使用工具**：调用各种解题工具来辅助解题
4. **编写和执行代码**：编写 Python 代码来解决问题
5. **网络交互**：与靶机进行交互（如果题目提供了容器）

## 输出格式
你的回复必须是一个 JSON 对象，包含以下字段：
- `thinking`: 你的分析过程（字符串）
- `action`: 你要执行的动作（字符串），可选值：
  - `analyze`: 分析题目信息
  - `run_code`: 执行 Python 代码
  - `interact`: 与靶机交互
  - `submit_flag`: 提交 flag
  - `give_up`: 放弃当前题目
- `action_input`: 动作的输入参数（字符串或对象）
  - 对于 `run_code`: Python 代码字符串
  - 对于 `submit_flag`: flag 字符串
  - 对于 `interact`: `{"host": "...", "port": ..., "commands": [...]}`
- `confidence`: 你对当前方案的置信度 (0-1)

## 注意事项
- Flag 格式通常为 `flag{...}` 或比赛自定义格式
- 优先尝试简单方法，逐步升级复杂度
- 如果多次尝试失败，及时放弃并说明原因
- 不要猜测 flag，只提交你有把握的答案
"""

USER_PROMPT_TEMPLATE = """\
## 题目信息
- **标题**: {title}
- **分类**: {category}
- **分值**: {score}
- **类型**: {challenge_type}

## 题目描述
{content}

## 提示
{hints}

## 附件信息
{attachment_info}

## 靶机信息
{container_info}

## 附件内容
{file_content}

请分析这道题目并尝试解题。
"""


def build_challenge_prompt(
    title: str,
    category: str,
    score: int,
    challenge_type: str,
    content: str,
    hints: list[str],
    attachment_info: str = "无附件",
    container_info: str = "无靶机",
    file_content: str = "无附件内容",
) -> str:
    hints_str = "\n".join(f"- {h}" for h in hints) if hints else "无提示"
    return USER_PROMPT_TEMPLATE.format(
        title=title,
        category=category,
        score=score,
        challenge_type=challenge_type,
        content=content,
        hints=hints_str,
        attachment_info=attachment_info,
        container_info=container_info,
        file_content=file_content,
    )
