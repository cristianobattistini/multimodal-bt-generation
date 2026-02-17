# Multimodal Behavior Tree Generation

The first multimodal dataset for Behavior Tree generation from text and images, together with a complete pipeline for fine-tuning Vision-Language Models and evaluating them in robotic simulation.

## Overview

This project introduces a novel approach to robot task planning by creating the **first multimodal dataset** that pairs visual scene observations and natural language instructions with executable **Behavior Trees (BehaviorTree.CPP XML)**. The pipeline:

1. **Dataset Creation** - Transforms Open-X-Embodiment (OXE) robot demonstration episodes into supervised `(image + instruction) -> BT XML` pairs, with augmentation and lexical variation strategies
2. **VLM Fine-tuning** - Trains lightweight Vision-Language Models (Gemma3-4B, Qwen2.5-VL-3B, Qwen3-VL-8B, SmolVLM2) via LoRA adapters to generate BT XML from multimodal input
3. **Simulation Execution** - Deploys generated Behavior Trees in OmniGibson simulation with BDDL grounding for the BEHAVIOR-1K benchmark
4. **Evaluation** - Ablation study comparing zero-shot vs Chain-of-Thought prompting across multiple models

## Repository Structure

```
multimodal-bt-generation/
|
|-- behavior_integration/     Core pipeline: VLM inference -> BT generation -> OmniGibson execution
|   |-- scripts/              Main entry points (run_continuous_pipeline.py, vlm_server.py)
|   |-- pipeline/             BT executor, environment manager, episode runner
|   |-- vlm/                  VLM client, BT generation, object mapping
|   |-- camera/               Camera control, image capture, video recording
|   |-- bddl/                 BDDL task parsing, grounding, task selection
|   |-- constants/            Task mappings, primitive config, task overrides
|   +-- ui/                   Interactive control, ablation controller
|
|-- embodied_bt_brain/        Agentic teacher system and runtime
|   |-- runtime/              BT execution runtime, VLM inference bridge
|   |-- agentic_teacher/      LLM-driven BT repair, augmentation, validation
|   |-- dataset_proposer_agentic/  Dataset generation pipeline
|   |-- primitive_library/    BT node definitions (PAL v1)
|   +-- data/                 Training and validation datasets
|
|-- nb_agentic/               Jupyter notebooks for VLM training and evaluation
|-- processing/               OXE dataset export and processing pipeline
|-- scripts/                  Benchmarking and prompt generation utilities
|-- tools/                    Dataset transformation and splitting tools
|-- bt_templates/             Reference BT XML templates (50 BEHAVIOR-1K tasks)
|-- prompts/                  Task-specific prompt definitions
|-- config/                   Lexical transformation configuration
|-- experiments/              Experiment tracking metadata
|-- behavior-1k-ablation/     Ablation study results (zero-shot vs CoT, 20 tasks x 4 models)
+-- dataset_agentic*/         Training datasets (4 variants: base, augmented, lexical, augmented+lexical)
```

## Setup

### Prerequisites

- Python 3.10
- NVIDIA GPU with CUDA support
- OmniGibson and BEHAVIOR-1K datasets (for simulation execution)

### Installation

```bash
# Create conda environment
conda env create -f environment.yml
conda activate multimodal-bt-generation

# Or install with pip
pip install -r requirement.txt
```

## Usage

### VLM Fine-tuning

Training notebooks are in `nb_agentic/`. Each notebook handles a specific model:

| Notebook | Model | Parameters |
|----------|-------|------------|
| `Gemma3_(4B)_Vision.ipynb` | Gemma3-4B | LoRA r=16 |
| `qwen25_3B_Vision.ipynb` | Qwen2.5-VL-3B | LoRA r=16 |
| `Qwen3_VL_(8B)_Vision_ok.ipynb` | Qwen3-VL-8B | LoRA r=16 |
| `smolvlm2_oxe_bt_finetune_wandb.ipynb` | SmolVLM2-2.2B | QLoRA r=16 |

### Running Experiments in Simulation

```bash
# 1. Start the VLM inference server
python behavior_integration/scripts/vlm_server.py --model qwen --port 7860

# 2. Run the continuous pipeline (keeps OmniGibson alive between episodes)
./run_continuous_pipeline.sh \
    --instruction "put the book on the nightstand" \
    --task tidying_bedroom \
    --colab-url http://127.0.0.1:7860
```

### Evaluation

- **Automatic metrics**: `nb_agentic/evalutation.ipynb` (BLEU, ROUGE scores)
- **Inference testing**: `nb_agentic/*_Inference_Testing.ipynb` (per-model evaluation)
- **Ablation results**: `behavior-1k-ablation/` (zero-shot vs CoT comparison)

## Ablation Study

The `behavior-1k-ablation/` directory contains results comparing two prompting strategies across 20 BEHAVIOR-1K tasks:

- **Zero-shot**: Clean prompts with only instruction + BDDL goal + available actions/objects
- **CoT (Chain-of-Thought)**: Prompts with explicit workflow steps

Models evaluated: fine-tuned adapter, GPT-5, Qwen2.5-VL, SmolVLM2

## Dataset

Four dataset variants are provided (all in JSONL format with image + BT XML pairs):

| Variant | Description | Size |
|---------|-------------|------|
| `dataset_agentic/` | Base dataset | 2,205 train / 228 val |
| `dataset_agentic_augmented/` | With scene augmentation | - |
| `dataset_agentic_lexical/` | With lexical variations (synonym substitution) | - |
| `dataset_agentic_augmented_lexical/` | Both augmentations combined | - |
