# Codex RSI 工具包适配

本目录将 PenguinHarness 的 OpenSkill、SkillAdam、TRACE、SkillOpt 指令接到 Codex CLI 和 Harbor。四个原始工具包保留各自的训练规则；`gdpevo-codex-bridge` 提供持续优化会话、独立解题会话、训练反馈与产物交接。

## 项目内技能

四个工具包与桥接 Skill 已安装在本目录的 `.agents/skills/`。在本目录启动 Codex 后，可以指定工具包名称，例如 `$skilladam-rsi-toolkit`，并同时使用 `$gdpevo-codex-bridge`。项目内安装不修改全局 Codex 配置。

`prepared/` 包含六个 GDPEVO Essential 场景与四种方法的 24 份配置。每份配置记录基准提交、模型 `deepseek-flash`、推理等级 `max`、方法参数、一次训练和三次固定状态测试。训练和测试使用同一份基准代码。新配置中的 SkillAdam 使用两次提案，与文章展示的三个场景一致；其余历史实验参数没有完整公开。已有配置按创建时的参数保留。

## 检查命令

以下命令在 Ubuntu/WSL 中从本目录执行。`run` 默认仅打印 Harbor 参数，不启动任务，也不访问模型：

```bash
python3 adapter.py run \
  --plan prepared/skilladam/service-ticket-resolution \
  --phase train \
  --jobs jobs/skilladam-service-train
```

为其他场景创建配置时，使用已固定的 Benchmark checkout：

```bash
python3 adapter.py prepare \
  --method skilladam \
  --domain service-ticket-resolution \
  --benchmark /home/penguin/gdpevo-benchmark \
  --output prepared/example-skilladam-service
```

`--method` 支持 `openskill`、`skilladam`、`trace`、`skillopt`。`run --phase baseline` 安排三次无学习技能测试；`run --phase test --skill <冻结的技能目录>` 使用同一份技能安排三次测试。`run` 增加 `--execute` 才会启动 Harbor 与模型调用；届时由运行环境提供模型接口与凭据，密钥不写入参数或配置文件。

执行结束后，适配器核对 Harbor 的完成数、评分和新会话；测试还会检查原技能文件在运行期间未改变。也可只检查已有结果：`python3 adapter.py verify --phase test --jobs <任务目录>`。

OpenSkill 的构造过程要求独立检索资料与独立虚拟验证，不允许使用官方训练评分器代替。为其准备经过核对的领域资料与验证依据目录后，重新调用 `prepare --research <资料目录>` 并使用新的输出目录；缺少资料时，训练命令会说明这一前提。资料不能包含目标答案、私有评分细则或测试反馈。

## 记录与验证

桥接脚本为每次子会话保存独立轨迹与 Token 用量；训练会话的最终提交应保留这些记录。`usage.py <Harbor-trial-dir>` 汇总优化器与子会话用量。评分只由训练协调者调用，OpenSkill 不调用训练评分器。TRACE 记录 Actor 的技能选择；SkillAdam、SkillOpt 和 TRACE 的数值规则可通过 `bridge/method_cli.py` 调用。

适配器使用本地虚构模型接口和模拟评分器检查 Codex 的 `max` 请求、项目技能发现、持续会话恢复、独立 Actor 文件交接与方法关键计算。真实模型实验的配置、轨迹和结果保存在 `experiments/` 与 `jobs/`；这两个目录不纳入版本控制。OpenSkill 各场景的公开候选资料在 `research/`，需根据具体公开任务确认覆盖范围。

子会话使用独立的用户目录，通过提示和轨迹检查避免访问训练评分资源；同容器的会话不是操作系统级网络隔离，对实验有效性的判断还要审阅实际轨迹。实验中断、恢复、方法设置差异和用量缺口均需随结果报告。适配器使用 Codex 认证文件，并从解题进程的环境变量中移除密钥；认证文件仍需供 Codex 读取，公开分享日志之前须检查并脱敏。
