# 实验与评测

评测口径以严谨为先：**所有数字必须来自真实运行记录，禁止编造**。仓库只提供模板，数字由实际操作回填。

## 1. 评测模板（`results/`）

| 文件 | 内容 |
|---|---|
| `evaluation_summary.json` | 汇总：运行元数据、试验统计、分阶段成功率、时长、安全事件、失败分析 |
| `trial_results.csv` | 逐次试验记录 |
| `latency_results.csv` | 推理 / chunk / gRPC / 控制环时延（mean / p95） |
| `consecutive_10_trials.csv` | 连续十次完整录像逐帧回填 |

## 2. 报告口径：10/10 consecutive trials

报告成功结果时，采用下面的表达，**不写成「成功率 99%」或「成功率 100%」**：

> 在一次连续录制的实验中，系统完成 10 次测试并成功 10 次（10/10 consecutive trials）。

理由：单次连续拍摄的 10 次试验，比聚合出的成功率可信得多，且能对照录像逐帧核验。

## 3. `consecutive_10_trials.csv` 字段

`trial_id`、`video_start_time`、`video_end_time`、`towel_initial_position`、`towel_orientation`、`approach_success`、`left_grasp_success`、`right_grasp_success`、`lift_success`、`fold_success`、`release_success`、`final_success`、`duration_seconds`、`manual_reset_required`、`checkpoint`、`notes`。

规则：

- 每次试验的阶段成败都要标记（approach / 左抓 / 右抓 / 抬升 / 折叠 / 释放）。
- 若某次需要人工复位，`manual_reset_required` 必须记录，不得隐瞒。
- 逐阶段成败可用于失败分析（见下）。

## 4. 失败分析

`evaluation_summary.json` 的 `failure_analysis` 数组记录每次失败：

- 阶段（哪一步失败）
- 观察到的现象（图像/关节轨迹片段）
- 可能原因（如起点偏移超容差、夹爪未完全闭合、毛巾堆叠姿态偏离、光照变化）
- 处置（本次重试 / 调整复位 / 补充数据）

失败信息比成功数字更有工程价值，请如实记录。

## 5. 视频诚信要求

- 连续十次版本为**一次不间断连续拍摄**，保留完整时间线，不得剪辑拼接各次试验。
- 每次试验标记 `Trial 01`–`Trial 10`，注明人工复位。
- 变速片段必须标注（如「4× speed」）。
- 技术分析视频允许阶段标记与真实失败案例展示（见 `docs/video-script.md`）。

## 6. 待确认项

- 正式试验总次数（≥20 次的统计结论）：**待确认**。当前只有「连续 10 次」这一口径具备录像证据。
- 不同起点的泛化测试、不同毛巾/光照的鲁棒性数据：**待确认**。
- 对照基线（如 Diffuser / SmolVLA / 非 ACT 策略）量化对比：**待确认**，无记录则不做对比声明。
