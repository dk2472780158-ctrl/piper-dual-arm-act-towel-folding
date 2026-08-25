# 数据采集

本仓库发布的数据采集流程与 LeRobot 生态一致（episodes 为 parquet + mp4），并针对真实硬件做了三处关键修正。

## 1. 流程

```
操作员遥操作 master 臂 → slave 臂跟随 → 三目相机与关节状态同步记录 → 生成 episode
```

- 每段 episode 保存 `observation.state`、`observation.images.{left,middle,right}` 与 `action`。
- 数据格式为 LeRobot 数据集（`datasets/*` 目录结构 + `meta/info.json`）。
- 采样器 `EpisodeAwareSampler` 按 episode 边界组织训练样本，避免跨 episode 拼接。

### 采集命令（参考运行）

用 LeRobot 的 `lerobot-record`，机器人类型为 `piper_dual`（须先跑
`scripts/setup_piper_dual.sh`）：

```bash
lerobot-record \
  --robot.type=piper_dual \
  --robot.left_port="${ROBOT_LEFT_CAN:-can1}" \
  --robot.right_port="${ROBOT_RIGHT_CAN:-can0}" \
  --robot.id=piper_towel \
  --robot.cameras="{
    left:   {type: opencv, index_or_path: /dev/camera_left,   width: 640, height: 480, fps: 30},
    middle: {type: opencv, index_or_path: /dev/camera_middle, width: 640, height: 480, fps: 30},
    right:  {type: opencv, index_or_path: /dev/camera_right,  width: 640, height: 480, fps: 30}}" \
  --dataset.repo_id="${DATASET_REPO_ID:-local/towel_fold_dataset_aug_v1}" \
  --dataset.num_episodes=120 \
  --dataset.single_task="Fold the towel with both Piper arms." \
  --display_data=true
```

- 遥操作：操作员拉动 leader（master）臂，follower 跟随。leader 侧驱动是参考 fork
  的 `lerobot/teleoperators/piper/`（本仓库审计材料不含该目录），`--teleop.type`
  的确切取值**待确认**；`lerobot_piper/motors/piper/piper_master.py` 是读 leader
  控制帧的只读总线实现，可作为移植参考。
- 部署模型（v4）的训练集为 **120 条 demo / 85,187 帧**（见上文「数据集（已确认）」）；
  上面的 `num_episodes=120` 与之对齐，请按你的任务调整。

## 2. 观测 / 动作定义

| 字段 | 维度 | 内容 |
|---|---|---|
| `observation.state` | 28 | 每臂 7 电机 ×（位置 + 力矩）× 2 臂 |
| `observation.images.*` | [3,480,640] ×3 | 左/中/右相机 |
| `action` | 14 | [左 j1..j6, 左夹爪, 右 j1..j6, 右夹爪]，位置控制 |

## 3. 单位制修正（重要）

原始遥操作数据中夹爪 / 部分关节存在单位不一致（`RANGE_M100_100` 等标记），发布前做了修正：

- 夹爪统一为**米**，行程 [0, 0.08] m。
- 关节统一为**弧度**。
- 相关修正逻辑保留在驱动与安全层中（`normalize_gripper_commands` 将负夹爪指令裁剪到 0，防止 Piper 总线 `abs()` 造成「负数指令被静默解读为张开」的隐患）。

> 若你的数据集来自其他源，务必核对单位，否则动作超出物理限位会被安全层拦截（这不是 bug，而是保护）。

## 4. 相机配置

- 三目（左/中/右）RealSense，640×480 @ 30 fps。
- 仓库不保存设备序列号；部署时通过 `.env`（`CAMERA_LEFT/MIDDLE/RIGHT`）或 udev 符号链接指向 `/dev/camera_*`。
- 采集时需保证三路相机时间对齐（同为 30 fps，逐帧同步写入 episode）。

## 5. 数据集（已确认）

部署模型（checkpoint 040000 = last，run `towel_fold_act_v4_scratch60k`）的训练集已从主机确认：

| 项 | 值 |
|---|---|
| repo_id | `local/towel_fold_dataset_aug_v1`（本地数据集，无 Hub 仓库 ID） |
| episodes | 120 |
| frames | 85,187 |
| FPS | 30 |
| robot_type | `piper_dual` |
| observation.state | 28（每臂 7 电机 × 位置/力矩交错：`left_joint_1.pos/effort … right_gripper.pos/effort`） |
| action | 14（`left_joint_1.pos … left_gripper.pos, right_joint_1.pos … right_gripper.pos`） |
| 图像 | `left` / `middle` / `right`，RGB 640×480 @ 30 fps |
| 增强 | 关闭（`image_transforms.enable=false`） |

早期 run `towel_fold_act_v2` 用 **60 条 demo** 的 `local/towel_fold_dataset`（42,373 帧），
属历史迭代，**不**是 10/10 连续成功视频所用模型（见
[train_example.yaml](../configs/train_example.yaml) 中 `repo_id: local/towel_fold_dataset_aug_v1`）。

## 6. 待确认项

- leader 遥操作的 `--teleop.type` 确切取值：**待确认**（参考 fork 的 `teleoperators/piper` 不在审计材料内）。
- 是否包含「失败 / 中断」demo 作为负样本：**待确认**。
