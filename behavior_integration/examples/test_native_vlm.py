#!/usr/bin/env python3
"""Test VLM with native transformers (no unsloth)"""

import sys
from pathlib import Path
from PIL import Image
import json

sys.path.insert(0, str(Path(__file__).parent))

print("="*80)
print("VLM BT Generation Test (Native Transformers)")
print("="*80)

# Load example
print("\n[1/4] Loading example...")
dataset_dir = Path(__file__).parent / "dataset_agentic_v1" / "train"
with open(dataset_dir / "data.jsonl") as f:
    example = json.loads(f.readline())

instruction = example['instruction']
img_path = dataset_dir / example['student_image_path']
test_image = Image.open(img_path).convert("RGB")

print(f"✓ Instruction: {instruction}")
print(f"✓ Image: {img_path}")

# Load LoRA
print("\n[2/4] Loading VLM (native transformers)...")
lora_dir = Path.home() / "lora_models"
gemma_lora = lora_dir / "gemma3_4b_vision_bt_lora_06012026"

from embodied_bt_brain.runtime.vlm_inference_native import VLMInferenceNative

vlm = VLMInferenceNative(
    model_type="gemma3-4b",
    lora_path=str(gemma_lora),
    temperature=0.3,
    load_in_4bit=True
)

# Generate
print(f"\n[3/4] Generating BT...")
bt_xml = vlm.generate_bt(
    image=test_image,
    instruction=instruction,
    max_new_tokens=1024
)

print("\n" + "="*80)
print("GENERATED BT:")
print("="*80)
print(bt_xml[:1000] + ("..." if len(bt_xml) > 1000 else ""))

# Parse
print("\n[4/4] Validating BT...")
from embodied_bt_brain.runtime import BehaviorTreeExecutor

executor = BehaviorTreeExecutor()
try:
    bt_root = executor.parse_xml_string(bt_xml)
    print("✓ BT is VALID!")
    print("\nStructure:")
    executor.print_tree(bt_root)
except Exception as e:
    print(f"✗ Parse error: {e}")

print("\n" + "="*80)
print("✅ Test Complete!")
print("="*80)
