#!/usr/bin/env python3
"""
Generate BT using VLM (run in 'vlm' environment).

Usage:
    conda activate vlm
    python generate_bt_only.py \
        --lora ~/lora_models/gemma3_4b_vision_bt_lora_06012026 \
        --model gemma3-4b \
        --instruction "pick up the bread" \
        --output /tmp/generated_bt.xml
"""

import argparse
import sys
from pathlib import Path
from PIL import Image
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from embodied_bt_brain.runtime.vlm_inference import VLMInference


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lora", required=True, help="Path to LoRA adapter")
    parser.add_argument("--model", default="gemma3-4b", choices=["gemma3-4b", "qwen25-vl-3b"])
    parser.add_argument("--instruction", required=True, help="Task instruction")
    parser.add_argument("--image", default=None, help="Path to observation image (optional)")
    parser.add_argument("--output", required=True, help="Output XML file")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--variants", type=int, default=1, help="Number of BT variants to generate")

    args = parser.parse_args()

    print("="*80)
    print("VLM BT Generation (vlm environment)")
    print("="*80)
    print(f"LoRA: {args.lora}")
    print(f"Model: {args.model}")
    print(f"Instruction: {args.instruction}")
    print(f"Output: {args.output}")

    # Load image
    if args.image:
        print(f"Loading image: {args.image}")
        image = Image.open(args.image).convert("RGB")
    else:
        print("No image provided, using dummy gray image")
        image = Image.new('RGB', (224, 224), color='gray')

    # Load VLM
    print("\nLoading VLM...")
    vlm = VLMInference(
        model_type=args.model,
        lora_path=args.lora,
        temperature=args.temperature
    )

    # Generate BT variants
    print(f"\nGenerating {args.variants} BT variant(s) for: '{args.instruction}'")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    variants_generated = []

    for i in range(args.variants):
        # Vary temperature slightly for each variant
        temp = args.temperature + (i * 0.1)
        print(f"\n  Variant {i+1}/{args.variants} (temperature={temp:.2f})...")

        bt_xml = vlm.generate_bt(
            image=image,
            instruction=args.instruction,
            max_new_tokens=1536
        )

        # Save variant
        if args.variants == 1:
            variant_path = output_path
        else:
            variant_path = output_path.parent / f"{output_path.stem}_v{i+1}{output_path.suffix}"

        with open(variant_path, 'w') as f:
            f.write(bt_xml)

        variants_generated.append(variant_path)
        print(f"    ✓ Saved to: {variant_path} ({len(bt_xml)} chars)")

        # Update temperature for next variant
        vlm.set_temperature(temp)

    print(f"\n✓ Generated {len(variants_generated)} BT variant(s)")

    # Show preview
    print("\nBT Preview (first 500 chars):")
    print("-"*80)
    print(bt_xml[:500] + ("..." if len(bt_xml) > 500 else ""))
    print("-"*80)

    print("\n✅ Generation complete!")
    print(f"\nNext: Run in behavior env:")
    print(f"  conda activate behavior")
    print(f"  python execute_bt_sim.py --bt-file {output_path}")


if __name__ == "__main__":
    main()
