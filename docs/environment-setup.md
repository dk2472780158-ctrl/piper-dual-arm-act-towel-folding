# 环境准备（Environment Setup）

参考运行跑在控制 Piper 的 Ubuntu 主机上。本节是从真实主机还原的环境清单，
所有命令均为实际用到的；序列号等敏感项用占位符表示，不入库。

## 1. 硬件清单

| 部件 | 规格 | 用途 |
|---|---|---|
| 双臂 | 2 × AgileX Piper（六自由度 + 夹爪） | 左臂 CAN `can1`，右臂 CAN `can0` |
| 相机 | 3 × RealSense，640×480 @ 30 fps | 左 / 中 / 右 三目 |
| 主机 | Ubuntu + NVIDIA GPU | 训练与 CUDA 推理 |

## 2. 软件依赖

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # torch / lerobot / piper-sdk / opencv-python / ...
./scripts/setup_piper_dual.sh  # 把 piper_dual 机器人类型装进 LeRobot（见 lerobot_piper/README.md）
```

- **piper-sdk 0.6.2（已确认）**：pip 包名 `piper-sdk`，Python 导入名 `piper_sdk`，
  核心接口 `from piper_sdk import C_PiperInterface_V2`。代码按 SDK 0.6.2 的接口与
  硬件限位设计（`start_sdk_joint_limit=True` / `start_sdk_gripper_limit=True`）。
  它安装在 conda 环境 `lerobot_v30` 里（base 环境的 `pip show piper-sdk` 查不到是
  因为不在 base）。`pyproject.toml` 已固定 `piper-sdk==0.6.2`。
- **GPU**：参考主机为 Driver 595.84、CUDA 13.2（`nvidia-smi` 头部可见）。
  显卡型号与显存未记录在审计材料中，**待确认**（可用 `nvidia-smi -L` 查询后回填）。

## 3. CAN 总线

Piper 双臂通过两个 SocketCAN 总线连接：左臂 `can1`、右臂 `can0`。

```bash
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can1 type can bitrate 1000000
sudo ip link set can0 up && sudo ip link set can1 up
```

在 `/dev/` 下应能看到 `can0`、`can1`。参考主机的 udev 规则集中在 `/etc/udev/rules.d/`
（ModemManager 相关），**没有**为 CAN 总线单独建符号链接——直接用 socketcan 的
`can0`/`can1` 设备名即可。

> 未确认连接或控制机械臂、未确认执行 CAN 命令属于红线（见 README）。上面只是
> 让总线出现在系统里，不会使能电机。

## 4. 相机 udev 规则（序列号已脱敏）

参考主机的真实相机规则用 RealSense 序列号固定符号链接，保证设备编号跨重启稳定：

```
# /etc/udev/rules.d/99-cameras.rules （示例，序列号为占位符）
SUBSYSTEM=="video4linux", KERNELS=="*:1.3", ATTR{index}=="0", ENV{ID_SERIAL_SHORT}=="<SERIAL_LEFT>",   SYMLINK+="camera_left"
SUBSYSTEM=="video4linux", KERNELS=="*:1.3", ATTR{index}=="0", ENV{ID_SERIAL_SHORT}=="<SERIAL_MIDDLE>", SYMLINK+="camera_middle"
SUBSYSTEM=="video4linux", KERNELS=="*:1.3", ATTR{index}=="0", ENV{ID_SERIAL_SHORT}=="<SERIAL_RIGHT>",  SYMLINK+="camera_right"
```

- 序列号是设备唯一标识，**本仓库不发布任何真实序列号**；用你自己的相机序列号替换。
- `run_act.sh` 通过 `/dev/camera_{left,middle,right}`（OpenCV 后端 + `index_or_path`）
  打开相机，因此这三条符号链接是异步部署路径的硬前提。
- 重载规则：`sudo udevadm control --reload-rules && sudo udevadm trigger`，
  然后 `ls -l /dev/camera_*` 验证。

### ACT 环回视频节点（参考环境备注）

参考主机 udev 中还有一组 ACT 环回节点规则：

```
# ACT loopback 节点固定 video_nr=20,21,22；非 root 用户可 OpenCV 打开
KERNEL=="video20", MODE="0666", GROUP="video"
KERNEL=="video21", MODE="0666", GROUP="video"
KERNEL=="video22", MODE="0666", GROUP="video"
```

这是原始 ACT 项目用来固定环回视频设备编号的。**本仓库的 `run_act.sh` 不依赖这组
节点**（它走 `/dev/camera_*` 符号链接）；保留在此仅供还原参考环境时对照。
是否需要这组节点才能跑通你的部署，**待确认**。

## 5. 一键检查

```bash
./scripts/check_environment.sh
```

覆盖：Python ≥ 3.10、torch/lerobot/piper_sdk/opencv/numpy、CUDA、CAN 总线、
`/dev/camera_*`、`POLICY_CHECKPOINT`。缺硬性依赖会以非零退出。

## 6. 首次上机顺序

1. `setup_piper_dual.sh` 成功（piper_dual 注册）。
2. `check_environment.sh` 通过（或只有可解释的 WARN）。
3. `python -m pytest tests/ -q` 全绿。
4. `./scripts/dry_run.sh` 全流程 dry-run（不使能电机、不发动作）。
5. 以上全通过，才考虑 `--execute`（并握住急停）。
