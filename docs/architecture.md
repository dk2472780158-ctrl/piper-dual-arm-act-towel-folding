# 系统架构

本仓库把一个真实运行在双机械臂硬件上的「双臂 Piper + ACT 叠毛巾」项目整理为可公开、可复现的开源工程。整体是数据 → 训练 → 推理 → 真机部署的完整闭环。

## 1. 数据流一览

```
遥操作采集 → LeRobot 数据集 → ACT 训练 → 权重检查点 → gRPC 异步推理 → 双 Piper 真机执行
                                    （30 Hz 观测反馈回到推理端，闭环）
```

架构图见 [assets/architecture.svg](../assets/architecture.svg)。

## 2. 硬件与接口

| 部件 | 型号/规格 | 说明 |
|---|---|---|
| 机械臂 ×2 | AgileX Piper，6 关节 + 1 夹爪（每臂 7 电机） | 左臂 `can1`，右臂 `can0`，通过 `piper_sdk` 通讯 |
| 夹爪 | 1-DOF，行程 [0, 0.08] m | 位置指令，单位米 |
| 相机 ×3 | RealSense（左/中/右） | 640×480 @ 30 fps，实际序列号已脱敏 |
| 控制环 | 30 Hz | 位置控制 |

> 相机序列号等设备标识属于隐私信息，已从仓库移除，改为 `.env` / udev 符号链接配置。

## 3. 观测与动作约定

- **观测 `observation.state`（28 维）** = 左臂 7 电机 ×（位置 + 力矩）+ 右臂 7 电机 ×（位置 + 力矩）。
- **图像观测（3 个）**：`observation.images.left / middle / right`，各 `[3, 480, 640]`。
- **动作 `action`（14 维）** = `[左 j1..j6, 左夹爪, 右 j1..j6, 右夹爪]`，位置控制，关节单位弧度、夹爪单位米。

这些维度是**从实际训练配置中读取**的（见 `configs/train_example.yaml` 与 `tests/test_config.py` 的断言）。

## 4. 训练：ACT

ACT（Action Chunking Transformer，LeRobot 实现，Apache 2.0）核心超参数来自训练运行的 `train_config.json`：

| 参数 | 值 |
|---|---|
| chunk_size / n_action_steps | 100 / 50 |
| n_obs_steps | 1 |
| 视觉骨干 | ResNet18（ImageNet 预训练权重） |
| VAE latent | 32 |
| dim_model / n_heads / dim_feedforward | 512 / 8 / 3200 |
| 编码器 / 解码器层数 | 4 / 1 |
| kl_weight | 10.0 |
| 归一化 | VISUAL / STATE / ACTION 全部 MEAN_STD，并覆盖 ImageNet 统计 |
| batch_size / steps / save_freq | 8 / 50000 / 10000 |
| 优化器 | AdamW，lr 1e-5，grad_clip 10.0 |

## 5. 推理：gRPC 异步部署（生产路径）

参照部署脚本 `act_inference_towel_client.sh`：

- `policy_server`（CUDA）持有模型；`robot_client`（CPU）负责相机、关节读取与下发。
- ACT 预测 100 步 chunk，**每次只执行 30 步**（`actions_per_chunk=30`）。
- 重叠 chunk 用 `weighted_average` 聚合（`0.3·old + 0.7·new`），`chunk_size_threshold=0.6`。
- 控制频率 30 Hz。客户端不发多余关节滤波（`PIPER_ACTION_FILTER_ALPHA=1.0`，避免双重延迟）。

## 6. 安全层（逐控制步强制执行）

安全校验器位于 `src/piper_towel_folding/safety.py`（纯 numpy、可单测），每个动作下发前依次检查：

1. 形状与有限性：14 维且无 NaN/Inf。
2. 硬件限位：Piper SDK 物理关节范围。
3. 逐命令步长：关节 ≤ 0.10 rad、夹爪 ≤ 0.01 m。
4. 跟踪误差：关节 ≤ 0.35 rad、夹爪 ≤ 0.03 m。
5. 起点位姿校验：距训练起点关节 ≤ 0.15 rad、夹爪 ≤ 0.02 m，否则拒绝启动。
6. 夹爪裁剪至 [0, 0.08] m（Piper 对负目标取 `abs()`，显式裁剪保证行为确定）。
7. 连接 / 断开时**永不发送 disable 指令**，机械臂保持 ENABLED 以防坠落。

真实执行前必须经过 `--execute` + 键入 `EXECUTE` + 显式 `--max-steps` 预算三重确认，且默认全部流程为 dry-run。详见 [safety-system.md](safety-system.md)。

## 7. 目录结构

```
piper-dual-arm-act-towel-folding/
├─ assets/architecture.svg        # 架构图
├─ configs/                       # 训练 / 评测 / 机器人示例配置
├─ docs/                          # 本文档集
├─ results/                       # 评测模板（须回填真实数据，不伪造数字）
├─ scripts/                       # 训练 / 评测 / 部署 / dry-run / 环境检查
├─ src/piper_towel_folding/       # 安全层、复位、评测、Piper 驱动
└─ tests/                         # 纯 numpy 安全层与配置单测
```
