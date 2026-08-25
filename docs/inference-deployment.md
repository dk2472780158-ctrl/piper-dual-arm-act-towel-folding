# 推理与部署

部署分两条路径：**异步 gRPC（生产，参考运行采用）** 与 **同步安全优先评测（仓库自带）**。两者共享同一 ACT 权重与安全层。

## 1. 异步 gRPC 部署（参考运行）

镜像审计到的部署脚本 `act_inference_towel_client.sh`：

```
policy_server（CUDA，持模型，gRPC）
        ↑ 观测 / 动作      127.0.0.1:8082
robot_client（CPU，相机 + CAN 关节，30 Hz 控制环）
        ↓
双 Piper 臂（左 can1，右 can0）+ 三目相机
```

### 关键推理参数

| 参数 | 值 | 来源 |
|---|---|---|
| server 地址 | 127.0.0.1:8082 | 部署脚本 |
| checkpoint | `pretrained_model/`（含 040000 等） | 部署脚本 |
| actions_per_chunk | 30 | ACT 预测 100 步，执行 30 步后重规划 |
| chunk_size_threshold | 0.6 | 判定何时需要新 chunk |
| aggregate_fn | `weighted_average`（0.3·old + 0.7·new） | 重叠区时间集成 |
| 控制频率 | 30 Hz | 部署脚本 |
| 关节滤波 | `PIPER_ACTION_FILTER_ALPHA=1.0`（关闭） | 避免双重延迟 |

### 启动方式

```bash
# 终端 A
./scripts/run_act.sh --server
# 终端 B（需先设置 .env）
./scripts/run_act.sh --client
```

### `.env` 配置

复制 `.env.example` 为 `.env` 并填入：

| 变量 | 示例 | 说明 |
|---|---|---|
| ROBOT_LEFT_CAN / ROBOT_RIGHT_CAN | `can1` / `can0` | 左右臂 CAN 总线 |
| CAMERA_LEFT/MIDDLE/RIGHT | `/dev/camera_left` 等 | 相机 udev 符号链接 |
| POLICY_CHECKPOINT | `/data/pretrained_model` | 权重目录 |
| SERVER_ADDRESS | `127.0.0.1:8082` | gRPC 地址 |
| ACTIONS_PER_CHUNK / CHUNK_SIZE_THRESHOLD / AGGREGATE_FN | 30 / 0.6 / `weighted_average` | 推理参数 |
| CONTROL_FPS | `30` | 控制频率 |

`run_act.sh` 会先解析相机设备为 `/dev/video*` 并校验合法性，避免错误的设备编号静默使用。

## 2. 同步安全优先评测（仓库自带）

- 入口 `src/piper_towel_folding/eval_rollout.py`（console script：`piper-towel-eval`）。
- **默认 dry-run**：只读相机与关节，不使能电机、不发动作。真实执行需要 `--execute` + 键入 `EXECUTE` + 显式 `--max-steps`。
- 每个动作经过完整安全层（见 [safety-system.md](safety-system.md)）。
- 启动前需机械臂已在训练起点（用 `piper-towel-reset` / `scripts/reset_piper_pose.py` 慢速归位）。

```bash
# dry-run
./scripts/evaluate_act.sh
# 真实执行（600 步 = 20 秒 @ 30Hz）
./scripts/evaluate_act.sh --execute --max-steps 600
```

## 3. 复位工具

`src/piper_towel_folding/reset_pose.py`：

- 以训练起点为参照，慢速、走「走廊」路径回到训练起点。目标位姿固定为数据集 frame-0 动作（`TRAINING_START_ACTION`），与评测的起点校验使用**同一个**基准，保证复位后必然通过起点门禁。
- 全程不发送 disable 指令，机械臂保持 ENABLED。
- 执行前需显式 `--execute` 并确认（`MOVE` 确认提示）。

## 4. 首次上机检查顺序

```bash
./scripts/check_environment.sh   # 依赖 / CUDA / CAN / 相机 / checkpoint
./scripts/dry_run.sh             # 全流程 dry-run（不动作）
./scripts/evaluate_act.sh        # 同步评测 dry-run
```

全部通过后再考虑 `--execute`。

## 5. 待确认项

- 040000 与 030000 检查点的推理延迟差异：**待确认**（无延迟日志）。
- gRPC 批量 / 吞吐上限：**待确认**。
