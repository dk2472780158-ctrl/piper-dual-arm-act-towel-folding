# 可复现性

目标：拿到本仓库 + 数据 + 权重 + 一套 Piper 硬件，就能复现「连续 10/10」的实验。

## 1. 环境

完整硬件 / CAN / udev / 相机细节见 [environment-setup.md](environment-setup.md)。软件：

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # torch / lerobot / piper-sdk / opencv-python / ...
./scripts/setup_piper_dual.sh      # 把 piper_dual 机器人类型装进 LeRobot（必须，见 lerobot_piper/README.md）
./scripts/check_environment.sh     # 确认依赖 + piper_dual 注册 + CAN + 相机 + checkpoint
```

依赖：Python ≥ 3.10、torch、lerobot（Apache 2.0）、piper-sdk、opencv-python、python-dotenv、pyyaml；测试需要 pytest。

> 训练 / CUDA 推理需要 NVIDIA GPU。参考部署主机为 **NVIDIA A10（24 GB）**，
> Driver 595.84 / CUDA 13.2（已确认）。无 GPU 也能跑安全层单测与 dry-run。

## 2. 首次验证（无硬件）

```bash
./scripts/check_environment.sh    # 依赖 / CUDA / CAN / 相机 / checkpoint
./scripts/dry_run.sh              # 全流程 dry-run
python -m pytest tests/ -q        # 安全层 + 配置单测
```

## 3. 下载数据与权重（不入库）

- **数据集**：LeRobot 格式 episodes，从原始采集端导出（本仓库不含数据，避免大文件入库）。
- **权重**：`pretrained_model` 目录（`model.safetensors` + `config.json`），从训练输出或部署机导出。
- 下载/导出完成后设置 `POLICY_CHECKPOINT` 与 `DATASET_ROOT`。

> 按红线规则：大型数据集与模型权重不提交到 Git，提供独立下载/导出说明即可。

## 4. 固定参数清单

复现所需的关键固定点（全部来自审计到的实际配置）：

| 维度 | 固定值 |
|---|---|
| obs.state | 28 维（每臂 7 电机 × 位置+力矩） |
| action | 14 维，位置控制，夹爪单位米 |
| ACT | chunk 100 / exec 50，VAE 32，ResNet18，dim 512 |
| 归一化 | MEAN_STD + ImageNet 统计覆盖 |
| 推理 | actions_per_chunk=30，weighted_average，30 Hz |
| 安全 | 起点 0.15/0.02，步长 0.10/0.01，跟踪 0.35/0.03 |
| 相机 | 三目 640×480 @ 30 |

> 040000 与 030000 的配置已核对为完全一致（040000 的 `config.json` 已导出，且其
> `pretrained_path` 指向 030000，即 040000 是 030000 的续训结果），因此上表同时
> 覆盖部署所用的 040000 与审计材料中的 030000。
>
> 参考模型的训练集：`local/towel_fold_dataset`（60 条 demo / 42,373 帧 / 30 fps，
> 增强关闭，见 [data-collection.md](data-collection.md)）。120 条 demo 的
> `towel_fold_dataset_aug_v1` 与 v4 模型是独立实验，不计入 10/10 声明。

## 5. 复现流程（硬件）

1. `setup_piper_dual.sh` 成功，`check_environment.sh` + `dry_run.sh` 通过。
2. 复位到训练起点（`piper-towel-reset`）。
3. `evaluate_act.sh --execute --max-steps <预算>`（或异步 `run_act.sh`）。
4. 录像并逐帧回填 `results/consecutive_10_trials.csv` 等模板。

## 6. 环境差异注意

- 关节滤波默认关闭；若宿主机噪声大，显式设置 `PIPER_ACTION_FILTER_ALPHA` 并在报告中注明。
- 相机实际设备编号因机器而异：用 udev 符号链接（`/dev/camera_*`）保证稳定，仓库不写死。
  RealSense 序列号是设备唯一标识，**本仓库不发布任何真实序列号**（占位符见
  [environment-setup.md](environment-setup.md)）。
- 单位制：任何外部数据集必须先归一化到本项目的米/弧度约定。
- piper_sdk 的 pip 安装名在不同来源不一致：以你环境的 `pip list | grep -i piper` 为准（**待确认**）。

## 7. 版本固定

`pyproject.toml` 声明了依赖范围；`NOTICE` 记录了 LeRobot / ACT / Piper SDK 的归属与许可。
`lerobot_piper/`（`lerobot_piper/README.md`）vendors 了参考运行所用的 LeRobot fork 中
`piper_dual` 相关的全部差异文件，`scripts/setup_piper_dual.sh` 负责装进你的 LeRobot 安装。
由于参考 fork 未带版本号（部署主机上是目录安装而非 pip），LeRobot 的精确 commit / 版本
**待确认**（部署主机上 `pip show lerobot` 或 fork 目录 `git log -1` 可补齐）。
若锁定到精确版本，建议补充 `requirements-lock.txt`（待确认发布前是否生成）。
