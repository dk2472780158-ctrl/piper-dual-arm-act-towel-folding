# 模型训练

训练基于 LeRobot 的 `lerobot-train`，ACT 策略。所有数值来自实际训练运行的 `train_config.json`（部署所用 run `towel_fold_act_v4_scratch60k` 已从主机确认；v2/030000 的 4 份 JSON 作为早期 run 依据保留在审计材料）。

## 1. 训练命令

```bash
lerobot-train --config configs/train_example.yaml \
  --dataset.root "$DATASET_ROOT" --steps 50000
```

- 传入仓库自带的 `configs/train_example.yaml`。
- `DATASET_ROOT` 指向你的 LeRobot 数据集目录（不入库，见 [reproducibility.md](reproducibility.md)）。

## 2. 策略架构（ACT）

| 参数 | 值 | 说明 |
|---|---|---|
| type | `act` | LeRobot ACTPolicy |
| n_obs_steps | 1 | 单帧观测即可输出整块动作 |
| chunk_size | 100 | 一次预测 100 步动作 |
| n_action_steps | 50 | 训练时每步执行 50 步 |
| use_vae | true | CVAE 建模多模态动作 |
| latent_dim | 32 | VAE 潜变量维度 |
| vision_backbone | resnet18 | ImageNet 预训练 |
| dim_model / n_heads / dim_feedforward | 512 / 8 / 3200 | Transformer 结构 |
| n_encoder_layers / n_decoder_layers | 4 / 1 | |
| kl_weight | 10.0 | CVAE KL 权重 |
| normalization_mapping | VISUAL/STATE/ACTION → MEAN_STD | 覆盖 ImageNet 统计 |

## 3. 训练超参数

| 参数 | 值 |
|---|---|
| batch_size | 8 |
| steps | 60000（目标；每 10000 步保存一次 checkpoint，实际保存到 040000 = last） |
| optimizer | AdamW，lr 1e-5，weight_decay 1e-4，grad_clip 10.0 |
| seed | 1000 |
| eval_freq | 0（参考运行未在训练中做仿真评测） |
| 数据增强 | 关闭（`image_transforms.enable=false`） |
| 视频后端 | torchcodec |

## 4. 归一化

- 图像与状态动作统一用 MEAN_STD 归一化。
- 图像显式覆盖为 ImageNet mean/std（`use_imagenet_stats: true`），保证与预训练骨干一致。

## 5. 检查点

- 训练产出 LeRobot `pretrained_model` 目录（`model.safetensors` + `config.json`）。
- **部署所用（已确认）**：run `towel_fold_act_v4_scratch60k` 的 `checkpoint 040000`，
  与 `checkpoints/last` 的 `model.safetensors` SHA256 完全一致，二者为同一份权重。
- 该 run **从零训练**（`resume=false`，run 名 `scratch60k`），目标 steps 60000，
  save_freq 10000；`last` 的 `config.json` 中 `pretrained_path` 指向同 run 的
  `.../030000/pretrained_model`（即 040000/last 是同 run 030000 的续训产物）。
  本节的架构与超参数表即该 run 的 `train_config.json` 实测值。
- **模型溯源（已确认）**：run `towel_fold_act_v4_scratch60k`，checkpoint 040000
  (=last)，target steps 60000，batch_size 8；训练集 `local/towel_fold_dataset_aug_v1`
  （**120 条 demo / 85,187 帧 / 30 fps，增强关闭**）；模型 SHA256
  `e118230cb7be20e307a64598fced077f50c631651b243deb2cf0db8366a4c28c`。
- 早期 run `towel_fold_act_v1/v2/v3`、`cube_r2l_act_v1` 均在本机存在；v2 训练集为
  60 条 demo 的 `local/towel_fold_dataset`（本地审计保留 v2/030000 的 4 份 JSON），
  它们**不**是 10/10 视频所用模型。
- 权重文件**不入库**，提供独立下载说明（见 README「下载」一节）。

## 6. 待确认项

- GPU：**NVIDIA A10（24 GB），Driver 595.84 / CUDA 13.2，已确认**。单步耗时 /
  训练墙钟时间：**待确认**（审计材料未含日志）。
- 是否进行过消融 / 对照实验：**待确认**。

## 7. 复现要点

1. 数据集单位制必须与 `observation.state=28 / action=14` 约定一致。
2. 保持 `use_imagenet_stats=true` 与归一化配置不变，否则图像分布偏移会导致真机表现退化。
3. 训练脚本 `scripts/train_act.sh` 封装了上述命令并校验环境（dry-run 默认）。
