# Multimodal Behavior Tree Generation for Robotic Task Planning

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
<!-- [![arXiv](https://img.shields.io/badge/arXiv-XXXX.XXXXX-b31b1b.svg)](https://arxiv.org/abs/XXXX.XXXXX) -->
<!-- [![HuggingFace](https://img.shields.io/badge/HuggingFace-Dataset-orange)](https://huggingface.co/datasets/AIRLab-POLIMI/multimodal-bt-dataset) -->

This repository contains the code, datasets, and experiment results for the paper:

> **Multimodal Behavior Tree Generation for Robotic Task Planning with Vision-Language Models**
>
> Cristiano Battistini, Gianluca Bardaro, Matteo Matteucci
>
> AIRLab, Politecnico di Milano

## Abstract

We present the first **multimodal dataset** for Behavior Tree (BT) generation that pairs visual scene observations and natural language instructions with executable BT XML plans. We fine-tune lightweight Vision-Language Models (Gemma3-4B, Qwen2.5-VL-3B, Qwen3-VL-8B, SmolVLM2) via LoRA adapters on this dataset and evaluate them on 20 household tasks from the BEHAVIOR-1K benchmark in OmniGibson simulation. Our ablation study compares zero-shot vs Chain-of-Thought prompting across all models, showing that fine-tuned compact VLMs can generate executable robot behavior plans from a single image and instruction.

## Pipeline Overview

```
                    ┌──────────────────────────────────────┐
                    │     Open-X-Embodiment Episodes        │
                    │   (image sequences + instructions)    │
                    └──────────────┬───────────────────────┘
                                   │  processing/
                                   ▼
                    ┌──────────────────────────────────────┐
                    │  Multimodal BT Dataset (4 variants)   │
                    │   image + instruction → BT XML pair   │
                    └──────────────┬───────────────────────┘
                                   │  nb_agentic/
                                   ▼
                    ┌──────────────────────────────────────┐
                    │    Fine-tuned VLM (LoRA adapters)     │
                    │  Gemma3 | Qwen2.5 | Qwen3 | SmolVLM2 │
                    └──────────────┬───────────────────────┘
                                   │  behavior_integration/
                                   ▼
                    ┌──────────────────────────────────────┐
                    │   OmniGibson Simulation Execution     │
                    │   BEHAVIOR-1K benchmark (20 tasks)    │
                    └──────────────────────────────────────┘
```

## Repository Structure

```
multimodal-bt-generation/
│
├── behavior_integration/        # Simulation pipeline: VLM → BT → OmniGibson execution
│   ├── scripts/                 #   Entry points (vlm_server.py, run_continuous_pipeline.py)
│   ├── pipeline/                #   BT executor, environment manager, episode runner
│   ├── vlm/                     #   VLM client, BT generation, object mapping
│   ├── camera/                  #   Camera control, image capture
│   ├── bddl/                    #   BDDL task parsing and grounding
│   ├── constants/               #   Task mappings, primitive config
│   └── ui/                      #   Interactive control, ablation controller
│
├── embodied_bt_brain/           # Agentic teacher system
│   ├── runtime/                 #   BT execution runtime, VLM inference bridge
│   ├── agentic_teacher/         #   LLM-driven BT repair and augmentation
│   ├── dataset_proposer_agentic/  # Dataset generation pipeline
│   └── primitive_library/       #   BT node definitions (PAL v1)
│
├── nb_agentic/                  # Training and evaluation notebooks (12 notebooks)
├── processing/                  # OXE dataset export and processing pipeline
├── scripts/                     # Benchmarking and prompt generation utilities
├── tools/                       # Dataset transformation and splitting tools
├── prompts/                     # Task-specific prompt definitions
├── config/                      # Lexical transformation configuration
├── experiments/                 # Experiment tracking metadata
│
├── dataset_agentic/             # Base dataset (1,470 train / 152 val)
├── dataset_agentic_augmented/   # + scene augmentation (735 train / 76 val)
├── dataset_agentic_lexical/     # + lexical variation (1,470 train / 152 val)
├── dataset_agentic_augmented_lexical/  # Both combined (735 train / 76 val)
│
└── behavior-1k-ablation/        # Ablation study results (20 tasks × 2 strategies × 4 models)
```

## Setup

### Prerequisites

- Python 3.10+
- NVIDIA GPU with CUDA support
- [OmniGibson](https://behavior.stanford.edu/omnigibson/) and BEHAVIOR-1K datasets (for simulation only)

### Installation

This project uses **two separate conda environments**:

| Environment | Purpose | GPU required |
|-------------|---------|:------------:|
| `multimodal-bt-generation` | VLM fine-tuning and inference | Yes |
| `behavior` | OmniGibson simulation (BEHAVIOR-1K) | Yes (Isaac Sim) |

```bash
git clone https://github.com/cristianobattistini/multimodal-bt-generation.git
cd multimodal-bt-generation

# VLM environment (training & inference)
conda env create -f environment.yml
conda activate multimodal-bt-generation
pip install -r requirement.txt

# Simulation environment (requires OmniGibson installed separately)
# See https://behavior.stanford.edu/omnigibson/getting_started/installation.html
```

## Usage

### 1. VLM Fine-tuning

All notebooks are in `nb_agentic/`:

**Training**

| Notebook | Model | Method |
|----------|-------|--------|
| `Gemma3_(4B)_Vision.ipynb` | Gemma3-4B | LoRA r=16 |
| `qwen25_3B_Vision.ipynb` | Qwen2.5-VL-3B | LoRA r=16 |
| `Qwen3_VL_(8B)_Vision_ok.ipynb` | Qwen3-VL-8B | LoRA r=16 |
| `smolvlm2_bt_finetune_wandb.ipynb` | SmolVLM2-2.2B | QLoRA r=16 |
| `smolvlm2_500M_bt_finetune_wandb.ipynb` | SmolVLM2-500M | QLoRA r=16 |

### 2. Inference Server

```bash
# Start the VLM inference server (Gradio)
# Models: qwen (Qwen2.5-VL-3B), qwen3 (Qwen3-VL-8B), gemma (Gemma3-4B),
#         smol2b (SmolVLM2-2.2B), smol500 (SmolVLM2-500M)
python behavior_integration/scripts/vlm_server.py --model qwen --port 7860
```

### 3. Simulation Execution

Requires the `behavior` conda environment with OmniGibson installed.

```bash
# Interactive mode
./run_continuous_pipeline.sh \
    --scene house_single_floor --robot Tiago \
    --colab-url http://127.0.0.1:7860

# Single task with retries
./run_continuous_pipeline.sh \
    --instruction "bring water to the counter" \
    --task bringing_water --retries 3 \
    --colab-url http://127.0.0.1:7860
```

**Inference testing**

| Notebook | Model |
|----------|-------|
| `Gemma3_4B_Inference_Testing.ipynb` | Gemma3-4B |
| `qwen25_3B_Inference_Testing.ipynb` | Qwen2.5-VL-3B |
| `Qwen3_VL_8B_Inference_Testing.ipynb` | Qwen3-VL-8B |
| `smolvlm2_2B_Inference_Testing.ipynb` | SmolVLM2-2.2B |

**Evaluation & utilities**

| Notebook | Purpose |
|----------|---------|
| `evaluation.ipynb` | Automatic metrics (BLEU, ROUGE) |
| `push_to_hf.ipynb` | Push dataset to HuggingFace Hub |
| `vlm_server.ipynb` | Interactive VLM server notebook |

## Dataset

The dataset is constructed from [Open-X-Embodiment](https://robotics-transformer-x.github.io/) robot demonstrations. Each sample contains an image observation, a natural language instruction, and the corresponding BT XML plan.

Four variants with different augmentation strategies are provided. The `augmented` variants contain scene-augmented samples generated by the agentic teacher (a subset of the base dataset with additional visual context descriptions). The `lexical` variants apply synonym substitution to BT node names.

| Variant | Description | Train | Val |
|---------|-------------|------:|----:|
| `dataset_agentic` | Base dataset | 1,470 | 152 |
| `dataset_agentic_augmented` | Scene augmentation subset | 735 | 76 |
| `dataset_agentic_lexical` | Base + synonym substitution | 1,470 | 152 |
| `dataset_agentic_augmented_lexical` | Augmented + synonyms | 735 | 76 |

## Ablation Study

The `behavior-1k-ablation/` directory contains results for 20 BEHAVIOR-1K household tasks, comparing:

- **Zero-shot**: instruction + BDDL goal + available actions/objects
- **Chain-of-Thought (CoT)**: explicit reasoning steps before BT generation

Models evaluated: fine-tuned LoRA adapter, GPT-5 (baseline), Qwen2.5-VL-3B (baseline), SmolVLM2-2.2B (baseline).

## Acknowledgements

- [BEHAVIOR-1K](https://behavior.stanford.edu/) benchmark and [OmniGibson](https://behavior.stanford.edu/omnigibson/) simulator (Stanford)
- [Open-X-Embodiment](https://robotics-transformer-x.github.io/) dataset
- [BehaviorTree.CPP](https://www.behaviortree.dev/) framework
- [Unsloth](https://github.com/unslothai/unsloth) for efficient LoRA fine-tuning
- [BTGenBot](https://github.com/AIRLab-POLIMI/BTGenBot) for foundational work on LLM-based BT generation

<!-- ## Citation

If you find this work useful, please cite:

```bibtex
@inproceedings{battistini2026multimodal,
  author    = {Battistini, Cristiano and Bardaro, Gianluca and Matteucci, Matteo},
  title     = {Multimodal Behavior Tree Generation for Robotic Task Planning with Vision-Language Models},
  booktitle = {TODO},
  year      = {2026},
}
```
-->

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
