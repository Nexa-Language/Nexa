# Nexa Code · Nexa 3.0.0

Nexa Code 是使用 `.nx` 编写的编程 Agent 示例。它通过兼容的 2.4 Agent/flow 入口和统一 AgentRunner 执行文件工具、审批、预算和恢复。3.0 Open Programs 的目标、证据与修订接口见 [接入指南](docs/open-programs.md)，仓库维护入口见 [3.0 使用指南](../../docs/spec/3.0/usage.md)。

## 运行

获取 3.0.0 的源码和锁定环境，并按 [运行契约](../../docs/runtime-v2.4.md#模型协议) 配置模型：

```sh
git clone --branch v3.0.0 --depth 1 https://github.com/Nexa-Language/Nexa.git
cd Nexa
uv sync --locked --all-extras
source .venv/bin/activate
nexa --version
```

随后进入要编辑的工作区，使用安装好的 `nexa` 命令及此示例的绝对路径。wheel 用户可从同一 tag 的源码归档取得 `examples/Nexa-Code`：

```sh
nexa agent /path/to/Nexa/examples/Nexa-Code/main.nx CodeAssistant "Fix the failing tests" --timeout 900
```

模型和 provider 从当前配置读取。工具的工作区是启动命令时的当前目录。写入文件和执行命令会返回 `waiting_approval`；检查 `pending_calls` 的名称及完整参数后批准：

```sh
nexa agent /path/to/Nexa/examples/Nexa-Code/main.nx CodeAssistant --resume RUN_ID --approve CALL_ID
```

拒绝使用 `--deny CALL_ID`。总超时包含等待时间；长任务在首次启动时设置足够的 `--timeout`。checkpoint 默认为当前工作区的 `.nexa/runs.sqlite3`。

## 工具

| 工具 | 行为 | 审批 |
|---|---|---|
| read_file | 读取工作区内 UTF-8 文件，限制 2 MB | 无 |
| search_files | 有界文本搜索，跳过常见依赖与隐藏目录 | 无 |
| list_directory | 最多列出 200 个目录项 | 无 |
| write_file | 工作区内原子替换，拒绝路径逃逸及敏感路径 | 每次调用 |
| shell_exec | 无 shell 的参数化子进程，超时 30 秒 | 每次调用 |

命令执行在宿主环境中进行。审批时检查命令的实际作用；当前实现沿用危险命令阻止规则。读写路径校验会解析符号链接并限制在工作区内。并发修改同一文件仍需由任务组织方协调。

## 评测

```sh
uv run pytest tests/test_nexa_code_eval.py -q
```

测试消费 `evals/tasks/fix-addition-v1.json`，在临时目录完成读取、两次审批、真实写入与验证脚本运行。provider 响应使用确定性 fixture；报告将其标为 `deterministic_fixture`，记录环境、事件和资源计数。该评测验证工具及恢复机制，真实模型能力、成本和延迟另外测量。

历史 REPL flow 保留在 `flows.nx`；带审批的修改任务使用 `nexa agent` 入口。

## Open Programs 3.0

[Integration guide](docs/open-programs.md): shared author protocol, versioned goals and evidence, exact patch review and recovery.
