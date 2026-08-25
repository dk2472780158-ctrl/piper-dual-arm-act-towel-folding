"""Verify that the shipped example configs parse and match the audited run."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIGS = REPO_ROOT / "configs"


def _load(name: str) -> dict:
    with open(CONFIGS / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_train_config_has_expected_act_architecture():
    cfg = _load("train_example.yaml")
    policy = cfg["policy"]

    assert policy["type"] == "act"
    assert policy["chunk_size"] == 100
    assert policy["n_action_steps"] == 50
    assert policy["n_obs_steps"] == 1
    assert policy["use_vae"] is True
    assert policy["latent_dim"] == 32
    assert policy["vision_backbone"] == "resnet18"
    assert policy["dim_model"] == 512
    assert policy["n_heads"] == 8
    assert policy["dim_feedforward"] == 3200
    assert policy["n_encoder_layers"] == 4
    assert policy["n_decoder_layers"] == 1
    assert policy["kl_weight"] == 10.0
    assert policy["normalization_mapping"] == {
        "VISUAL": "MEAN_STD",
        "STATE": "MEAN_STD",
        "ACTION": "MEAN_STD",
    }


def test_train_config_observation_action_shapes():
    cfg = _load("train_example.yaml")
    policy = cfg["policy"]

    assert policy["input_features"]["observation.state"]["shape"] == [28]
    for cam in ("left", "middle", "right"):
        assert policy["input_features"][f"observation.images.{cam}"]["shape"] == [3, 480, 640]
    assert policy["output_features"]["action"]["shape"] == [14]


def test_train_config_training_hyperparameters():
    cfg = _load("train_example.yaml")

    assert cfg["batch_size"] == 8
    assert cfg["steps"] == 50000
    assert cfg["save_freq"] == 10000
    assert cfg["seed"] == 1000
    assert cfg["eval_freq"] == 0
    assert cfg["optimizer"]["type"] == "adamw"
    # PyYAML reads "1e-5" (no decimal point) as a string; draccus coerces it
    # to float when loading the config, so compare numerically.
    assert float(cfg["optimizer"]["lr"]) == 1e-5
    assert cfg["optimizer"]["grad_clip_norm"] == 10.0
    assert cfg["dataset"]["use_imagenet_stats"] is True
    assert cfg["dataset"]["image_transforms"]["enable"] is False


def test_robot_config_contract():
    cfg = _load("robot_example.yaml")

    assert set(cfg["robot"]["cameras"].keys()) == {"left", "middle", "right"}
    for cam in cfg["robot"]["cameras"].values():
        assert cam["type"] == "opencv"
        assert cam["width"] == 640
        assert cam["height"] == 480
        assert cam["fps"] == 30

    async_cfg = cfg["async"]
    assert async_cfg["actions_per_chunk"] == 30
    assert async_cfg["chunk_size_threshold"] == 0.6
    assert async_cfg["aggregate_fn_name"] == "weighted_average"
    assert async_cfg["fps"] == 30


def test_eval_config_safety_defaults():
    cfg = _load("eval_example.yaml")

    assert cfg["max_joint_step"] == 0.10
    assert cfg["max_gripper_step"] == 0.01
    assert cfg["max_tracking_error"] == 0.35
    assert cfg["max_gripper_tracking_error"] == 0.03
    assert cfg["start_joint_tolerance"] == 0.15
    assert cfg["start_gripper_tolerance"] == 0.02
    assert cfg["execute"] is False  # dry-run by default
