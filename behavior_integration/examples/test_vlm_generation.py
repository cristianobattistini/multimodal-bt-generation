#!/usr/bin/env python3
"""
Test VLM BT generation only (no simulation).

This avoids torch_cluster conflicts while still testing the LoRA model.
"""

import sys
from pathlib import Path
from PIL import Image
import json

sys.path.insert(0, str(Path(__file__).parent))

print("="*80)
print("VLM BT Generation Test")
print("="*80)

# Load example from dataset
print("\n[1/4] Loading example from dataset...")
dataset_dir = Path(__file__).parent / "dataset_agentic_v1" / "train"
data_file = dataset_dir / "data.jsonl"

with open(data_file) as f:
    example = json.loads(f.readline())

instruction = example['instruction']
student_img_path = dataset_dir / example['student_image_path']
teacher_img_path = dataset_dir / example['teacher_image_path']

print(f"✓ Instruction: {instruction}")
print(f"✓ Student image: {student_img_path}")
print(f"✓ Teacher image: {teacher_img_path}")

# Load image
test_image = Image.open(student_img_path).convert("RGB")
print(f"✓ Image size: {test_image.size}")

# Load LoRA
print("\n[2/4] Loading VLM + LoRA...")
lora_dir = Path.home() / "lora_models"
gemma_lora = lora_dir / "gemma3_4b_vision_bt_lora_06012026"

print(f"Model: Gemma3-4B")
print(f"LoRA: {gemma_lora}")
print("⚠️  First run downloads base model (~4GB)...")

from embodied_bt_brain.runtime import VLMInference

vlm = VLMInference(
    model_type="gemma3-4b",
    lora_path=str(gemma_lora),
    temperature=0.3,  # Gemma prefers 0.3
    load_in_4bit=True
)

print("✓ VLM loaded")

# Generate BT
print(f"\n[3/4] Generating BT for: '{instruction}'")
bt_xml = vlm.generate_bt(
    image=test_image,
    instruction=instruction,
    max_new_tokens=1536,
    return_full_output=False  # Extract only XML
)

print("\n" + "="*80)
print("GENERATED BT XML:")
print("="*80)
print(bt_xml)

# Parse BT
print("\n[4/4] Validating generated BT...")
from embodied_bt_brain.runtime import BehaviorTreeExecutor

executor = BehaviorTreeExecutor()

try:
    bt_root = executor.parse_xml_string(bt_xml)
    print("✓ Generated BT is VALID!")

    print("\nBT Structure:")
    print("-"*80)
    executor.print_tree(bt_root)

except Exception as e:
    print(f"✗ BT parsing failed: {e}")
    print("\nThis means the model needs more training or temperature adjustment.")

print("\n" + "="*80)
print("✅ Test Complete!")
print("="*80)
print("\nTo test with actual simulation:")
print("1. Fix torch version conflict (downgrade to 2.6)")
print("2. Or use different environment for VLM vs simulation")
