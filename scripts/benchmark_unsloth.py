#!/usr/bin/env python3
"""Benchmark Gemma3-4B and Qwen2.5-3B on the validation dataset.

Uses Unsloth backend for both models.  Measures inference time, XML syntax
validity, and structural compliance with ground-truth BTs.

Usage:
    python scripts/benchmark_unsloth.py                       # all models, all modes
    python scripts/benchmark_unsloth.py --max-examples 5      # quick smoke test
    python scripts/benchmark_unsloth.py --models gemma3_4b    # single model
    python scripts/benchmark_unsloth.py --modes adapter       # adapter only
"""

import argparse
import gc
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from tqdm import tqdm

from benchmark_utils import (
    RESULTS_OUTPUT,
    check_structural_compliance,
    compute_action_jaccard,
    compute_node_count_ratio,
    compute_stats,
    get_gt_decorator_set,
    load_val_dataset,
    save_results,
    validate_bt_xml,
    validate_btcpp_format,
)

# ---------------------------------------------------------------------------
# Model configurations (mirrors vlm_server.py MODEL_CONFIGS)
# ---------------------------------------------------------------------------
MODELS = {
    "gemma3_4b": {
        "base_model": "unsloth/gemma-3-4b-pt",
        "adapter_path": str(Path.home() / "lora_models" / "gemma3_4b_vision_bt_lora_02022026"),
        "chat_template": "gemma-3",
        "uses_processor": True,   # FastVisionModel returns (model, processor)
        "generation_params": {
            "max_new_tokens": 4096,
            "temperature": 1.0,
            "min_p": 0.1,
            "top_p": 0.95,
            "top_k": 64,
            "do_sample": True,
            "use_cache": True,
        },
    },
    "qwen2dot5_3b": {
        "base_model": "unsloth/Qwen2.5-VL-3B-Instruct",
        "adapter_path": str(Path.home() / "lora_models" / "qwen2dot5-3B-Instruct_bt_lora_02022026"),
        "chat_template": None,
        "uses_processor": False,  # FastVisionModel returns (model, tokenizer)
        "generation_params": {
            "max_new_tokens": 4096,
            "temperature": 1.0,
            "min_p": 0.1,
            "do_sample": True,
            "use_cache": True,
        },
    },
}


# ---------------------------------------------------------------------------
# Model loading / unloading
# ---------------------------------------------------------------------------

def load_model(config: dict, with_adapter: bool):
    """Load an Unsloth model, optionally with LoRA adapter.

    Returns (model, tokenizer, processor).
    For Qwen, processor is None.  For Gemma, tokenizer == processor.tokenizer.
    """
    from unsloth import FastVisionModel, get_chat_template
    from peft import PeftModel

    processor = None
    tokenizer = None

    if config["uses_processor"]:
        # Gemma path
        model, processor = FastVisionModel.from_pretrained(
            config["base_model"],
            load_in_4bit=True,
            use_gradient_checkpointing="unsloth",
        )
        if config["chat_template"]:
            processor = get_chat_template(processor, config["chat_template"])
        tokenizer = processor.tokenizer
    else:
        # Qwen path
        model, tokenizer = FastVisionModel.from_pretrained(
            config["base_model"],
            load_in_4bit=True,
            use_gradient_checkpointing="unsloth",
        )

    if with_adapter:
        print(f"  Loading LoRA adapter from {config['adapter_path']} ...")
        model = PeftModel.from_pretrained(model, config["adapter_path"])

    FastVisionModel.for_inference(model)
    return model, tokenizer, processor


def unload_model(model, tokenizer, processor):
    """Free GPU memory."""
    del model, tokenizer, processor
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def run_inference(model, tokenizer, processor, config: dict,
                  full_prompt: str, image_path: str) -> tuple[str, float]:
    """Run a single inference and return (generated_text, elapsed_seconds)."""
    pil_image = Image.open(image_path).convert("RGB")

    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "image": pil_image},
            {"type": "text", "text": full_prompt},
        ],
    }]

    if config["uses_processor"]:
        # Gemma: processor handles chat template + tokenization
        input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(
            text=input_text,
            images=pil_image,
            add_special_tokens=False,
            return_tensors="pt",
        ).to("cuda")
        active_tokenizer = processor.tokenizer
    else:
        # Qwen: tokenizer handles both (image first!)
        input_text = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
        inputs = tokenizer(
            pil_image,
            input_text,
            add_special_tokens=False,
            return_tensors="pt",
        ).to("cuda")
        active_tokenizer = tokenizer

    gen_kwargs = {
        **inputs,
        **config["generation_params"],
        "pad_token_id": active_tokenizer.pad_token_id,
    }

    with torch.no_grad():
        t0 = time.perf_counter()
        outputs = model.generate(**gen_kwargs)
        t1 = time.perf_counter()

    # Decode only newly generated tokens
    prompt_len = inputs["input_ids"].shape[1]
    generated_text = active_tokenizer.decode(
        outputs[0][prompt_len:], skip_special_tokens=True
    )
    return generated_text, t1 - t0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Benchmark Gemma3-4B / Qwen2.5-3B")
    parser.add_argument("--models", nargs="+", default=list(MODELS.keys()),
                        choices=list(MODELS.keys()),
                        help="Which models to benchmark (default: both)")
    parser.add_argument("--modes", nargs="+", default=["adapter", "baseline"],
                        choices=["adapter", "baseline"],
                        help="Which modes to run (default: both)")
    parser.add_argument("--max-examples", type=int, default=0,
                        help="Limit examples (0 = all 228)")
    parser.add_argument("--output", type=str, default=RESULTS_OUTPUT,
                        help="Output JSON path")
    parser.add_argument("--verbose", action="store_true",
                        help="Print each generated output")
    args = parser.parse_args()

    dataset = load_val_dataset(max_examples=args.max_examples)
    total = len(dataset)

    # Pre-compute ground-truth decorator sets
    gt_decorator_sets = [get_gt_decorator_set(s["ground_truth"]) for s in dataset]

    results: dict = {}

    for model_name in args.models:
        config = MODELS[model_name]
        results[model_name] = {}

        for mode in args.modes:
            with_adapter = mode == "adapter"
            print(f"\n{'='*70}")
            print(f" {model_name} / {mode}")
            print(f"{'='*70}")

            model, tokenizer, processor = load_model(config, with_adapter)

            times: list[float] = []
            xml_valid_count = 0
            btcpp_valid_count = 0
            struct_match_count = 0
            linear_correct = 0
            linear_total = 0
            decorator_correct = 0
            decorator_total = 0
            jaccard_scores: list[float] = []
            node_count_ratios: list[float] = []

            pbar = tqdm(enumerate(dataset), total=total,
                        desc=f"{model_name}/{mode}", unit="ex")
            for i, sample in pbar:
                try:
                    generated, elapsed = run_inference(
                        model, tokenizer, processor, config,
                        sample["prompt_text"], sample["image_full_path"],
                    )
                except Exception as e:
                    tqdm.write(f"  [{model_name}/{mode}] {i+1}/{total} - ERROR: {e}")
                    generated, elapsed = "", 0.0

                times.append(elapsed)

                is_xml_valid = validate_bt_xml(generated)
                if is_xml_valid:
                    xml_valid_count += 1
                is_btcpp = validate_btcpp_format(generated)
                if is_btcpp:
                    btcpp_valid_count += 1
                    jaccard = compute_action_jaccard(generated, sample["ground_truth"])
                    jaccard_scores.append(jaccard)
                    ncr = compute_node_count_ratio(generated, sample["ground_truth"])
                    if ncr is not None:
                        node_count_ratios.append(ncr)

                gt_decs = gt_decorator_sets[i]
                is_linear_gt = len(gt_decs) == 0
                struct_ok = check_structural_compliance(generated, gt_decs)
                if struct_ok:
                    struct_match_count += 1

                if is_linear_gt:
                    linear_total += 1
                    if struct_ok:
                        linear_correct += 1
                else:
                    decorator_total += 1
                    if struct_ok:
                        decorator_correct += 1

                status = "V" if is_xml_valid else "X"
                struct_s = "S" if struct_ok else "F"
                avg_t = sum(times) / len(times)
                pbar.set_postfix(t=f"{elapsed:.1f}s", avg=f"{avg_t:.1f}s",
                                 xml=f"{xml_valid_count}/{i+1}",
                                 btcpp=f"{btcpp_valid_count}/{i+1}",
                                 struct=f"{struct_match_count}/{i+1}")

                if args.verbose:
                    tqdm.write(f"    [{status}/{struct_s}] {generated[:200]}...")

            results[model_name][mode] = compute_stats(
                times, xml_valid_count, btcpp_valid_count, struct_match_count, total,
                linear_correct, linear_total, decorator_correct, decorator_total,
                jaccard_scores=jaccard_scores, node_count_ratios=node_count_ratios,
            )

            avg_j = f"{np.mean(jaccard_scores):.2f}" if jaccard_scores else "N/A"
            avg_ncr = f"{np.mean(node_count_ratios):.2f}" if node_count_ratios else "N/A"
            print(f"\n  Summary: xml={xml_valid_count}/{total} "
                  f"btcpp={btcpp_valid_count}/{total} "
                  f"struct={struct_match_count}/{total} "
                  f"jaccard={avg_j} ncr={avg_ncr} "
                  f"time={sum(times)/len(times):.2f}s avg")

            unload_model(model, tokenizer, processor)

    save_results(results, args.output)


if __name__ == "__main__":
    main()
