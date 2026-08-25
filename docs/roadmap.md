# 路线图与未来工作

## 1. 已达成（本仓库当前状态）

- 双 Piper 双臂 + ACT 叠毛巾：数据 → 训练 → 推理 → 真机部署闭环。
- 异步 gRPC 推理（actions_per_chunk=30，weighted_average，30 Hz）。
- 完整安全层：起点 / 步长 / 跟踪 / 限位 / 夹爪裁剪 / 永不下电，默认 dry-run + 双重确认。
- 可单测的安全层、配置契约测试、checkpoint 加载测试。
- 报告口径「10/10 consecutive trials」，结果模板可逐帧回填。

## 2. 近期（可立即做）

| 项 | 说明 |
|---|---|
| 回填结果模板 | 用一次连续录像逐帧填 `consecutive_10_trials.csv`，再汇总到 `evaluation_summary.json` |
| 时延摸底 | 录 `latency_results.csv`（推理 / chunk / gRPC / 控制环 mean & p95） |
| 失败分析补全 | 每次失败按阶段 + 现象 + 原因 + 处置记录进 `failure_analysis` |
| 三份视频 | Hero Demo、连续十次完整版、技术分析（见 `docs/video-script.md`） |
| 精确版本锁定 | 生成 `requirements-lock.txt`，固定 lerobot / torch / piper-sdk 版本 |

## 3. 中期

| 项 | 说明 |
|---|---|
| 起点泛化 | 在起点容差边缘做网格测试，量化容忍区间 |
| 鲁棒性 | 不同毛巾规格、不同光照 / 背景、夹爪磨损 |
| 负样本与失败恢复 | 采集失败 demo，训练重试 / 恢复策略 |
| 延迟优化 | gRPC 批量、tensorRT / trt 转换、模型量化 |
| 对照基线 | Diffuser / SmolVLA / 非 ACT 策略在同任务上的量化对比（无记录不做对比声明） |

## 4. 远期

| 项 | 说明 |
|---|---|
| 跨任务复用 | 把「数据-训练-部署-安全」框架泛化到其它双臂柔性物体操作 |
| sim2real | 迁移到仿真验证与 sim2real 流程（实习方向，见简历） |
| 在线学习 | 从真实失败中增量微调（LoRA / replay buffer 重训） |
| 端侧部署 | RK3588 等 NPU 端侧推理（参考个人橙派跌倒检测项目经验） |

## 5. 诚实边界

- 当前可对外声明的只有「连续 10 次录像证据」；≥20 次统计、鲁棒性、基线对比均**待确认**，未做实验不写结论。
- 040000 checkpoint 的完整配置与训练集已确认（与 030000 一致、同 run 续训；训练集 60 条 demo / 42,373 帧，见 [training.md](training.md)）；GPU 规格仍**待确认**，见各 doc。
- 120 条 demo 的 `towel_fold_dataset_aug_v1` 数据集与 v4 模型是**后续实验**，不并入 10/10 连续成功视频的声明。
