# 模型训练

训练基于 LeRobot 的 `lerobot-train`，ACT 策略。所有数值来自实际训练运行的 `train_config.json`（checkpoint 030000 的 4 份 JSON 配置为审计依据）。

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
| steps | 50000（每 10000 步保存一次 checkpoint） |
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
- 参考部署使用 `checkpoint 040000`；审计到 `030000` 的配置并存有 4 份 JSON。
- 权重文件**不入库**，提供独立下载说明（见 README「下载」一节）。

## 6. 待确认项

- 040000 检查点的完整训练配置是否与 030000 完全一致：**待确认**（审计材料含 030000 的 4 份 JSON，040000 的 config 未逐份核对）。
- GPU 型号 / 显存 / 单步耗时 / 训练墙钟时间：**待确认**（审计材料未含日志）。
- 是否进行过消融 / 对照实验：**待确认**。

## 7. 复现要点

1. 数据集单位制必须与 `observation.state=28 / action=14` 约定一致。
2. 保持 `use_imagenet_stats=true` 与归一化配置不变，否则图像分布偏移会导致真机表现退化。
3. 训练脚本 `scripts/train_act.sh` 封装了上述命令并校验环境（dry-run 默认）。
