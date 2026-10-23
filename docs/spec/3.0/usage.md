# Nexa 3.0 Open Programs 使用指南

Nexa 3.0.0 提供 Open Programs 的 Python 参考实现，运行平台为 Linux/macOS。按 [安装指南](../../development.md#install-a-release) 安装 wheel 后使用 `nexa`；本页的 `uv run` 命令适用于 `v3.0.0` 源码检出并执行 `uv sync --locked --all-extras` 后的环境。程序、证据和授权格式均有独立 schema。

## 一个目标，从源码到可重放产物

```nexa
language "3.0"
program Answer {
    goal answer() -> Int {
        intent "Return 42"
        implementation value 42
    }
}
```

保存为 `answer.nx`。`uv run nexa check answer.nx --json` 只进行本地解析与合同检查，无模型请求。执行需要 Docker Engine（Linux），或 macOS 上的 Docker Desktop / Colima。执行器使用当前 Docker context，也接受 `--docker-context`。

```sh
docker pull python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
uv run nexa build answer.nx --environment examples/open_programs/offline.json --state .nexa/demo.db --json
uv run nexa build answer.nx --environment examples/open_programs/offline.json --state .nexa/demo.db --locked --json
```

锁文件默认为 `answer.nx.lock`。锁定产物还依赖指定状态库内的内容寻址对象；备份、移动或重放时保留两者。锁定构建核对当前程序、环境与证据并产生零模型请求。开放目标写 `implementation open`；带 `sandbox.exec` 能力的开放目标求解为 Python `solve(inputs)`，其余目标求解为 JSON 常量。显式编写的实现可选择两种形式。

## 绑定阿里云

`examples/open_programs/aliyun.json` 使用 `ALIYUN_API_KEY`、`ALIYUN_BASE_URL` 和固定模型 `qwen3.8-max-0902`。在自己的 shell 中预先配置环境变量；产品不会执行用户的 shell 配置文件。配置中的 `provider.endpoint` 为控制器保留的派生依赖，配置文件内只填写原始依赖。

```sh
uv run nexa build examples/open_programs/sum.nx \
  --environment examples/open_programs/aliyun.json --state .nexa/sum.db \
  --max-model-calls 4 --max-tokens 16000 --timeout 90 --json
```

凭据仅在实际创建模型客户端时读取。锁定构建仍需相同 endpoint 身份，密钥可缺省。一个命令中的 build 和 runtime 阶段共用调用、累计 token 和时间预算。调用次数是硬上限；输入 token 使用量在 provider 返回 usage 后才能核算，输出请求受剩余预算限制。模型提出实现与模型评审分别计费、分别记录；费用报告需要与当次价格基准结合。

## 持续维护仓库

`maintain.nx` 把 `change_request` 事件映射为 Patch 目标。`maintain-aliyun.json` 中的固定命令与期望输出组成外部验收 oracle，适用于演示的 `calc.add` 仓库。维护自己的项目时，先编写对应检查配置。

```sh
uv run nexa run examples/open_programs/maintain.nx \
  --environment examples/open_programs/maintain-aliyun.json --state .nexa/maintain.db \
  --program-id demo --repository /absolute/path/to/repository --include calc.py \
  --request 'Fix calc.add to return the mathematical sum.' --json
```

结果包含 `activity_id`、`revision`、`proposal_id`、准确 diff 和每项证据。候选及回归命令在 OCI 内执行。选中的 UTF-8 源文件通过 stdin 传入容器内临时目录；容器无宿主目录挂载、凭据或外网。用户目录只有在准确补丁取得授权后才写入。

```sh
uv run nexa open evidence PROPOSAL_ID --environment examples/open_programs/maintain-aliyun.json --state .nexa/maintain.db
uv run nexa open approve PROPOSAL_ID --actor local-operator --state .nexa/maintain.db
uv run nexa open apply PROPOSAL_ID --grant GRANT_ID --environment examples/open_programs/maintain-aliyun.json --state .nexa/maintain.db
```

`--actor` 表示可信本地客户端签发授权时记录的操作者；本地数据库是信任边界。候选容器无法访问它。模型输出中的“已批准”字段不会创建授权。外部多用户认证服务属于后续范围。

文件或证据已变化时重新提出补丁。应用前后均检查基线；旧文件先原子移入同目录的 `.nexa-preserved-*/original`，核对移入后的内容，再用排他创建安装新文件。删除同样保留原文件。journal 的 `preserved` 字段记录恢复位置；读取快照会排除这些内部目录。并行修改触发 `workspace_conflict`，被移动的用户内容可从记录的位置取回，随后按当前工作区重新提出补丁。

中断后先运行 `nexa open recover PROPOSAL_ID --state ...`，核对后给 `open apply` 增加 `--resume`。恢复可以还原在移走原文件后中断的基线，并识别已经完成的写入。应用成功后仍保留原 inode：编辑器通过旧文件描述符写入的内容会落在恢复文件中，后续 `recover` 会报告差异。恢复目录由用户在确认后归档或清理，Nexa 不自动删除它们。跨文件操作采用写前日志，保留文件的存储量与修改量相当；应用期间应协调编辑器和构建器，文件名切换之间存在短暂空窗。

接纳产物、锁定重放和补丁授权都会查询状态库中相同候选、策略及依赖上下文的最新证据。后来的失败会阻止旧成功记录继续授权；其他输入的失败保留在各自上下文中。显式 `implementation` 优先，capsule 必须与该实现完全相同；开放实现才允许选择其他匹配候选。

## 修订、恢复与取消

修改 `.nx` 后，使用 `nexa open revise FILE --environment ... --state ... --program-id demo --expected-revision CURRENT_REVISION`。源码 CAS、产物接纳和运行版本切换各有记录。活动固定到创建时的源码与产物，切换后新活动使用新版本。

`nexa open status demo --state ...` 查看活动版本；`nexa open resume demo --environment ... --state ...` 在停止的控制器之后核对恢复状态。仍存活的操作所有者持有内核锁，恢复会返回 `operation_busy`。中断活动保留历史，由客户端显式发起新活动。`nexa open cancel ACTIVITY_ID --environment ... --state ...` 持久化协作取消请求；当前模型或 OCI 调用在返回/超时后检查它，后续步骤停止。单次 OCI 执行上限 30 秒。

外部操作进入 prepared/started/completed journal。幂等适配器恢复使用原操作键；未知非幂等结果需通过 `EffectJournal.reconcile` 记录核对结果。在核对完成前，新活动、版本切换和补丁应用保持阻塞。

## 复用

```sh
uv run nexa open capsule export repair.capsule.json --activity ACTIVITY_ID \
  --source local-repository --creator local-operator --license MIT --state .nexa/maintain.db
uv run nexa open capsule import repair.capsule.json --state .nexa/second.db
```

在新的 `nexa run` 中用 `--capsule CAPSULE_ID` 显式选择实现。合同、能力、原始来源与依赖条件参与匹配。新输入产生新的验证义务；可变模型别名跨任务重新评审。导入文件中的哈希验证完整性，本地可信证据登记决定哪些结果可以复用。新任务不能通过删掉 capsule 条件放宽原实现依赖。

## 作者 Agent、编译器演进与复现

- `nexa author --state .nexa/author.db --environment ...` 提供逐行 JSON-RPC；见 [协议](author-protocol.md)。人和 Agent 共享程序 ID、CAS 修订与活动 ID。
- `nexa open schema NAME` 从已安装包输出 schema；无需源码仓库。源码文件位于 `schemas/3.0/`，CI 核对它们与实现一致。
- 编译 pass 的固定验收、自举和选择授权见 [编译器演进](evolution.md)。
- 六阶段完整演示：`uv run python -m benchmarks.open_programs.flagship --environment examples/open_programs/maintain-aliyun.json --output .nexa/flagship-first`。输出目录必须是新的。最多 24 次请求、累计 120000 token，每阶段还有独立预算。测试工作区授权的 actor 明确标为 fixture operator。
- 使用 `--replay .nexa/flagship-first/responses.json --output .nexa/flagship-replay` 重放记录的模型回复，重新执行 OCI 检查。时间、目录身份和新活动 ID 会改变证据摘要；重放核对实际行为与锁定实现。

当前执行后端为 Python；Rust AVM 保留 2.4 子集，3.0 schema 与语义 corpus 为后续实现提供接口。源码参数必须显式具备类型；前端暂只支持本页描述的维护子集，其他 2.4 结构按 [迁移指南](../../migration/2.4-to-3.0.md) 处理。
