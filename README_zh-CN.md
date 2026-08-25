<div align="center">

# 双臂 ACT 叠毛巾（Dual-Arm ACT Towel Folding）

**基于真实双 AgileX Piper 机械臂的模仿学习项目：柔性物体（毛巾）双臂协同操作完整闭环。**

ACT（Action Chunking Transformer）· LeRobot · gRPC 异步推理 · 30 Hz 实时控制 · 完整安全层

**English version**: [README.md](README.md)

</div>

---

## 这个项目展示什么

一套跑在**两台真实机械臂**上的叠毛巾技能，端到端闭环：

| 维度 | 说明 |
|---|---|
| 模仿学习与 ACT | CVAE + Transformer，预测整段动作块 |
| 双臂协同 | 单个 14 维动作向量同时驱动双臂与双夹爪 |
| 柔性物体操作 | 折叠可形变毛巾，不是刚性抓取 |
| 完整闭环 | 遥操作采集 → 数据集 → 训练 → gRPC 异步部署 → 30 Hz 真机控制 |
| 实时控制与安全 | 每个动作下发前经纯 numpy 安全层校验；默认 dry-run |
| 定量评测与失败分析 | 报告口径「10/10 consecutive trials」，不编造成功率 |
| 工程化与可复现 | 可运行脚本、可单测安全码、配置契约测试、结果模板须真实回填 |

> 🎬 Hero 演示 —— 连续十次录像中的第 1 次试验：

![Hero demo](assets/demo_hero.gif)

---

## 结果卡片：10/10 consecutive trials

> 在一次连续录制的实验中，系统完成 10 次测试并成功 10 次（10/10 consecutive trials）。

| 项 | 值 |
|---|---|
| 录制 | 单次连续拍摄，无内部剪辑 |
| 试验区间 | 1.5 – 314.0 s（约 34 秒/次） |
| 完成 / 成功 | 10 / 10 |
| 人工复位 | 是 —— 每次试验前由操作员重新摆放毛巾 |
| 时间精度 | ±0.5 s |
| Checkpoint | 040000 |
| 分阶段表现 | 每次试验的 approach / 左右抓取 / 抬升 / 折叠 / 释放均可见且成功 |

逐次时间戳与阶段标志：`results/consecutive_10_trials.csv` · 逐帧审阅全文：`results/consecutive_10_trials_review.md`

---

## 系统架构

![Architecture](assets/architecture.svg)

```
遥操作采集 → LeRobot 数据集 → ACT 训练 → 权重检查点
        → gRPC policy_server（CUDA）→ robot_client（CPU）→ 双 Piper（CAN）
        → 30 Hz 观测反馈 → 生成下一 chunk
```

安全层**每个控制步强制执行**：起点位姿校验（0.15 rad / 0.02 m）、逐命令步长限制（0.10 rad / 0.01 m）、跟踪误差（0.35 rad / 0.03 m）、硬件限位、夹爪裁剪到 [0, 0.08] m，以及**永不下发 disable 指令**（机械臂保持 ENABLED 以防坠落）。

---

## 关键参数（读取自真实运行，非猜测）

| 维度 | 值 |
|---|---|
| 观测 `observation.state` | 28（双臂 × 7 电机 × 位置+力矩） |
| 动作 | 14 = [左 j1..j6, 左夹爪, 右 j1..j6, 右夹爪]，位置控制 |
| 相机 | 三目 640×480 @ 30 fps |
| ACT 分块 | chunk 100 · 训练执行 50 · 部署执行 30 |
| 异步推理 | gRPC，`weighted_average`（0.3·old + 0.7·new），`chunk_size_threshold=0.6` |
| 控制环 | 30 Hz |
| 检查点 | `pretrained_model/`（部署使用 global step 040000） |

> ⚠️ 任何未经审计日志确认的项一律标注 **待确认**，不编造数据。

---

## 仓库结构

```
assets/   架构图 + Hero GIF
configs/  训练 / 评测 / 机器人示例配置
docs/     架构 · 数据采集 · 训练 · 部署 · 安全系统 · 环境准备 · 复现 · 工程化 · 路线图
lerobot_piper/   piper_dual 机器人类型的 LeRobot 模块（从参考 fork 原样 vendored）
results/  仅回填模板（evaluation_summary.json / trial_results.csv /
          latency_results.csv / consecutive_10_trials.csv）
scripts/  setup_piper_dual · 训练 · 评测 · 部署 · dry-run · 环境检查
src/      safety.py（纯 numpy 校验器）· reset_pose · eval_rollout · piper 驱动
tests/    安全行为 / 动作形状 / 配置契约 / checkpoint 加载
```

## 快速开始（无需硬件）

```bash
pip install -e ".[dev]"

./scripts/check_environment.sh     # 依赖 / CUDA / CAN / 相机 / checkpoint
python -m pytest tests/ -q         # 安全层 + 配置单测
```

`check_environment.sh` 与 `pytest` 不需要机器人、不需要 CAN 总线、不需要 checkpoint。
`dry_run.sh` 额外需要 `POLICY_CHECKPOINT` 指向导出的 `pretrained_model/` 目录（它要
证明 ACT 策略能加载、整条链路已接好），但同样不动作：

```bash
POLICY_CHECKPOINT=/path/to/pretrained_model ./scripts/dry_run.sh
```

真实执行**永远不是默认**：需要 `--execute` + 键入 `EXECUTE` + 显式 `--max-steps` 预算。
详见 `docs/inference-deployment.md` 与 `docs/safety-system.md`。

## 环境（硬件）

| 部件 | 规格 | 说明 |
|---|---|---|
| 双臂 | 2 × AgileX Piper（六自由度 + 夹爪） | 左臂 `can1`，右臂 `can0` |
| 相机 | 3 × 640×480 @ 30 fps | `/dev/camera_{left,middle,right}` udev 符号链接 |
| 主机 | Ubuntu + NVIDIA GPU | 训练 + CUDA 推理 |
| 驱动 / CUDA | 595.84 / 13.2（已确认） | 显卡型号待确认 |

```bash
# 每台机器一次：把 piper_dual 机器人类型装进 LeRobot
./scripts/setup_piper_dual.sh
```

CAN / udev / 相机 / piper-sdk 的完整细节（序列号已脱敏）：`docs/environment-setup.md`。

## 端到端流程（本仓库复现的完整闭环）

**1. 采集** —— 操作员遥操作 leader 臂；`lerobot-record` 写入 LeRobot episodes
（parquet + mp4）。见 `docs/data-collection.md`：

```bash
lerobot-record --robot.type=piper_dual --robot.left_port=can1 --robot.right_port=can0 \
  --robot.cameras="{left: {type: opencv, index_or_path: /dev/camera_left, width: 640, height: 480, fps: 30}, \
    middle: {type: opencv, index_or_path: /dev/camera_middle, width: 640, height: 480, fps: 30}, \
    right: {type: opencv, index_or_path: /dev/camera_right, width: 640, height: 480, fps: 30}}" \
  --dataset.repo_id=local/towel_fold_dataset --dataset.num_episodes=30 \
  --dataset.single_task="Fold the towel with both Piper arms."
```

**2. 训练** —— `lerobot-train` + ACT（chunk 100、ResNet18、VAE 32、kl 10.0）。见 `docs/training.md`：

```bash
DATASET_ROOT="$DATASET_ROOT" ./scripts/train_act.sh
```

**3. 部署** —— 异步 gRPC：`policy_server`（CUDA）持有模型，`robot_client`（CPU）以
30 Hz 驱动双臂。见 `docs/inference-deployment.md`：

```bash
./scripts/run_act.sh --server      # 终端 A：gRPC 策略服务
./scripts/run_act.sh --client      # 终端 B：机器人 + 相机，30 Hz 控制环
```

**4. 评测** —— `results/` 模板从真实录像回填（见下）。参考结果是单次连续拍摄的 10/10。

## 复现清单

- [ ] `./scripts/setup_piper_dual.sh` → `piper_dual` 注册成功
- [ ] `./scripts/check_environment.sh` → 所有硬性依赖通过
- [ ] `./scripts/dry_run.sh` → 全流程 dry-run 通过，无动作
- [ ] `python -m pytest tests/ -q` → 全绿
- [ ] CAN `can0`/`can1` 已 up；`/dev/camera_*` 符号链接可解析
- [ ] `POLICY_CHECKPOINT` 指向导出的 `pretrained_model/` 目录
- [ ] 双臂复位到训练起点（`piper-towel-reset`）
- [ ] `./scripts/run_act.sh --server` + `--client`（或 `evaluate_act.sh --execute`）

任何未经审计日志确认的项一律标注 **待确认**，不编造数据。

## 常见问题

**为什么用「10/10 consecutive trials」而不是成功率？** 一次连续、无内部剪辑、每次复位
都可见的录制，比聚合成功率更可信，也无法靠挑片段注水。逐帧审阅全文见
`results/consecutive_10_trials_review.md`。

**权重和数据在哪里？** 不入库——仓库只给导出 / 安装说明与必须由真实运行回填的结果
模板（`docs/reproducibility.md`）。GitHub 放代码，不放几百 MB 的权重。

**必须要 GPU 吗？** 只有训练和 CUDA 推理需要。安全层、配置契约测试与 dry-run 都能
在 CPU 上跑。

**用这个仓库必须依赖原始 ACT 项目吗？** 不用。`lerobot_piper/` + `scripts/setup_piper_dual.sh`
就能让标准 LeRobot 安装识别 `piper_dual`。本仓库独立成站，原始项目不会被修改。

**相机序列号会公开吗？** 不会——设备序列号属隐私且因机器而异。文档用占位符，
你自己填自己的（`docs/environment-setup.md`）。

**有没有可能未经确认就给机械臂发指令？** 没有。真实执行需要 `--execute` + 键入
`EXECUTE` + 显式 `--max-steps` 预算；且 Ctrl+C 后机械臂保持 ENABLED 不自动下电，
防止负载坠落。

## 下载（数据与权重——不入库）

- **数据集**（LeRobot episodes）：由采集主机导出，见 `docs/reproducibility.md`。
- **检查点**（`pretrained_model/`）：由训练主机导出，设置 `POLICY_CHECKPOINT`。
- **视频**：仓库只放 GIF / 封面 / 链接，原始素材保留在本机。

## 操作红线（逐字保留）

1. 原始 ACT 项目只能读取，不能直接修改。
2. 必须创建一个新的、独立的 GitHub 发布目录。
3. 不允许覆盖原始训练配置、推理代码、模型或数据。
4. 不允许修改正在使用的 ACT checkpoint。
5. 不允许未经确认连接或控制机械臂。
6. 不允许未经确认执行 CAN 命令。
7. 不允许未经确认向 GitHub 推送。
8. 所有修改先保存在新的发布目录中，完成审查后再由我决定是否上传。

## 致谢与许可

- LeRobot / ACTPolicy — Apache 2.0，基于 Tony Z. Zhao 的 ALOHA 工作。见 `NOTICE` 与 `CITATION.cff`。
- AgileX Piper SDK — 按其自身许可（见 `NOTICE`）。
- 本仓库以 Apache 2.0 发布（`LICENSE`）。

**待确认审计项**与诚实边界记录在 `docs/evaluation.md` 与 `docs/roadmap.md`。
