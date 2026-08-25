# 数据与权重发布（Hugging Face）

> **现状（2026-08-25）：已发布。**
>
> - 数据集：<https://huggingface.co/datasets/d1112222/towel_fold_dataset_aug_v1>
> - 权重：<https://huggingface.co/d1112222/towel_fold_act_v4_040000>
>
> 控制主机无法直连 huggingface.co，经 `hf-mirror.com` 镜像完成上传。
> 隐私抽检：中相机全时段均匀采样 16 帧，未见人脸；遥操作期操作员手/前臂可能入镜，
> 已接受。此为采样而非逐帧全审，日后若发现隐私问题可删除仓库（内容公开后不可完全撤回）。

## 1. 发布什么

| 项 | 源（控制主机） | HF 目标 repo | 说明 |
|---|---|---|---|
| 数据集 | `~/.cache/huggingface/lerobot/local/towel_fold_dataset_aug_v1` | `d1112222/towel_fold_dataset_aug_v1` | **120 条 demo / 85,187 帧 / 30 fps**，10/10 视频模型（v4）的训练集 |
| 权重 | `.../towel_fold_act_v4_scratch60k/checkpoints/040000/pretrained_model` | `d1112222/towel_fold_act_v4_040000` | 部署所用 checkpoint 040000（= last），SHA256 `e11823…a4c28c` |

## 2. 明确不发布（红线 / 早期实验）

- **早期 run `towel_fold_act_v1/v2/v3`、`cube_r2l_act_v1`** —— 历史迭代（v2 用 60 条
  demo 的 `towel_fold_dataset`），不是 10/10 声明里的模型；不发布，除非你另行决定。
- 原始视频（10/10 连续录像 mp4、素材）—— 只发 GIF / 封面 / 链接。
- RealSense 序列号、lab 内网拓扑、用户名、机柜标签等任何可定位身份的信息。
- 训练主机上的中间产物 / 日志（训练墙钟等未记录，不编造）。

## 3. 隐私与合规检查清单（上传前必过）

Hugging Face 上传是**公开且基本不可撤销**的，比 GitHub 更敏感：

- [ ] **人脸**：逐帧抽查每一条 episode 的视频，确认没有操作员 / 旁观者的脸。
      teleop 采集期通常拍到操作员手臂，手臂可接受，**脸不可接受**。
- [ ] **身份信息**：画面里不得出现 lab 名称、工牌、电脑屏幕、可辨识工位。
- [ ] **序列号**：数据集里不得含相机序列号（episode 元数据里如果带，需脱敏）。
- [ ] **数据授权**：确认这些 demo 属于可公开发布的范畴（公司 / 学校 IP 边界）。
- [ ] **许可选择**：给数据集 repo 补 `LICENSE`（例如 CC-BY-4.0）与 README card；
      权重 repo 用 Apache-2.0。发布前定好，后续更换许可麻烦。

## 4. 控制主机执行步骤

```bash
conda activate lerobot_v30

# 1) 先跑一次 DRY-RUN，只看计划、不碰网络
DATASET_SOURCE="$HOME/.cache/huggingface/lerobot/local/towel_fold_dataset_aug_v1" \
MODEL_SOURCE="/path/to/towel_fold_act_v4_scratch60k/checkpoints/040000/pretrained_model" \
./scripts/publish_to_hf.sh

# 2) 确认隐私检查清单全过 + 设置 token
export HF_TOKEN="hf_..."        # huggingface-cli login 也可

# 3) 真正发布（会要求你输入 REVIEWED 和 PUBLISH）
DATASET_SOURCE="$HOME/.cache/huggingface/lerobot/local/towel_fold_dataset_aug_v1" \
MODEL_SOURCE="/path/to/towel_fold_act_v4_scratch60k/checkpoints/040000/pretrained_model" \
./scripts/publish_to_hf.sh --publish
```

发布完成后把两个 URL 回填到：

- `docs/publishing.md` 顶部状态行（改「已发布」）
- `.env.example` 的 `HF_DATASET_REPO` / `HF_MODEL_REPO` 注释里的链接
- `README.md` / `README_zh-CN.md` 下载段
- `docs/reproducibility.md` 第 3 节 —— 把「数据 / 权重需导出」改成可从 HF 下载

## 5. 别人怎么用（发布后）

```bash
# 数据
huggingface-cli download d1112222/towel_fold_dataset_aug_v1 --repo-type dataset --local-dir ./towel_fold_dataset_aug_v1
# 权重
huggingface-cli download d1112222/towel_fold_act_v4_040000 --local-dir ./040000
export POLICY_CHECKPOINT="$(pwd)/040000"
export DATASET_ROOT="$(pwd)/towel_fold_dataset_aug_v1"
```

然后按 `docs/reproducibility.md` 的流程走即可。
