# 工程化与代码质量

本仓库把「能跑的真机实验」升级为「可审阅、可测试、可复现的工程」。

## 1. 目录与模块划分

| 路径 | 职责 |
|---|---|
| `src/piper_towel_folding/safety.py` | 纯 numpy 安全校验器，可独立单测 |
| `src/piper_towel_folding/reset_pose.py` | 安全归位（慢速走廊，永不 disable） |
| `src/piper_towel_folding/eval_rollout.py` | 同步安全优先 rollout |
| `src/piper_towel_folding/piper/` | Piper 总线 / 双臂 + 相机驱动封装 |
| `configs/` | 训练 / 评测 / 机器人示例配置 |
| `scripts/` | 训练、评测、部署、dry-run、环境检查 |
| `tests/` | 安全层 + 配置 + checkpoint 加载单测 |
| `results/` | 评测模板（须回填真实数据） |

## 2. 测试策略

- `tests/test_dry_run.py`：安全层行为（限位、步长、跟踪、起点、夹爪裁剪）——纯 numpy，无硬件无 GPU。
- `tests/test_action_shape.py`：动作形状与有限性契约。
- `tests/test_config.py`：示例配置可解析，且关键参数与审计事实一致（防止复制时悄悄改掉 28/14 维、chunk 100 等）。
- `tests/test_policy_loading.py`：设置 `POLICY_CHECKPOINT` 后验证真实权重可加载且 action=14（无 checkpoint 时自动跳过）。

运行：`python -m pytest tests/ -q`。

## 3. 脚本默认安全

- `evaluate_act.sh` / `train_act.sh` 默认 **dry-run**；`--execute` 才允许真动作。
- 执行还需键入 `EXECUTE` + 显式 `--max-steps`。
- `run_act.sh` 启动前校验相机设备为合法 `/dev/video*`。
- `check_environment.sh` 输出硬依赖缺失即非零退出。

## 4. 配置即文档

- 示例配置与 `tests/test_config.py` 双重锁定真实参数，避免「README 一个数字、代码一个数字」。
- 配置用 `<DATASET_ROOT>` / `<CHECKPOINT_PATH>` / `.env` 占位符隔离本机路径与隐私信息。

## 5. 代码质量工具

- `pyproject.toml` 含 ruff 配置（待定规约：line-length、规则集）。
- 所有 Python 源文件通过 `py_compile` 校验（「ALL COMPILE OK」）。
- lint / format：`ruff check .`、`ruff format .`（未入库检查 CI，可选添加）。

## 6. 版本控制红线

见 [safety-system.md](safety-system.md) 第 4 节的操作红线：本仓库独立于原始 ACT 项目，只读不改；权重、数据、`.env`、原始视频均不入库（`.gitignore` 已覆盖）。

## 7. 待确认项

- 是否补充 CI（lint + 单测 + 大文件扫描）：**待确认**。
- 是否生成精确版本锁文件：**待确认**。
