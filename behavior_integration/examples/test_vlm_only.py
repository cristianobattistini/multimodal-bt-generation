#!/usr/bin/env python3
"""Test VLM + BT generation without full BEHAVIOR-1K"""

import sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

print("="*80)
print("VLM + BT Generation Test (No Simulation)")
print("="*80)

# Test 1: BT Executor
print("\n[1/3] Testing BT Executor...")
from embodied_bt_brain.runtime import BehaviorTreeExecutor

example_bt = """<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <SubTree ID="T_Navigate" target="bread"/>
      <Action ID="GRASP" obj="bread"/>
      <SubTree ID="T_Navigate" target="table"/>
      <Action ID="PLACE_ON_TOP" obj="table"/>
      <Action ID="RELEASE"/>
    </Sequence>
  </BehaviorTree>
  <BehaviorTree ID="T_Navigate">
    <Action ID="NAVIGATE_TO" obj="{target}"/>
  </BehaviorTree>
</root>"""

executor = BehaviorTreeExecutor()
bt_root = executor.parse_xml_string(example_bt)
print("✓ BT parsed successfully")
print("\nBT Structure:")
executor.print_tree(bt_root)

# Test 2: Load example image from dataset
print("\n[2/3] Loading example from dataset...")
dataset_dir = Path(__file__).parent / "dataset_agentic_v1" / "train"
img_dir = dataset_dir / "images"

# Find first image
images = list(img_dir.glob("*/*/frame0.jpg"))
if images:
    test_image_path = images[0]
    print(f"✓ Found test image: {test_image_path}")
    test_image = Image.open(test_image_path)
    print(f"  Image size: {test_image.size}")
else:
    print("✗ No images found, creating dummy image")
    test_image = Image.new('RGB', (224, 224), color='gray')

# Test 3: Load LoRA and generate BT
print("\n[3/3] Testing VLM Inference...")
lora_dir = Path.home() / "lora_models"

# Try Qwen first (smaller)
qwen_lora = lora_dir / "qwen2dot5-3B-Instruct_bt_lora_05012026"
gemma_lora = lora_dir / "gemma3_4b_vision_bt_lora_06012026"

if qwen_lora.exists():
    lora_path = qwen_lora
    model_type = "qwen25-vl-3b"
elif gemma_lora.exists():
    lora_path = gemma_lora
    model_type = "gemma3-4b"
else:
    print("✗ No LoRA found, skipping VLM test")
    sys.exit(0)

print(f"Loading {model_type} with LoRA from {lora_path}...")
print("⚠️  This will download base model (~4-8GB) on first run...")

from embodied_bt_brain.runtime import VLMInference

vlm = VLMInference(
    model_type=model_type,
    lora_path=str(lora_path),
    temperature=0.2,
    load_in_4bit=True
)

print("✓ VLM loaded")

# Generate BT
instruction = "pick up the bread and place it on the table"
print(f"\nGenerating BT for: '{instruction}'")

bt_xml = vlm.generate_bt(
    image=test_image,
    instruction=instruction,
    max_new_tokens=1024
)

print("\n" + "="*80)
print("GENERATED BT:")
print("="*80)
print(bt_xml)

# Parse generated BT
print("\n" + "="*80)
print("PARSING GENERATED BT:")
print("="*80)
try:
    bt_root = executor.parse_xml_string(bt_xml)
    print("✓ Generated BT is valid!")
    print("\nStructure:")
    executor.print_tree(bt_root)
except Exception as e:
    print(f"✗ Generated BT parse error: {e}")

print("\n" + "="*80)
print("✅ VLM + BT Test Complete!")
print("="*80)
print("\nNext: Install BEHAVIOR-1K to test full simulation")
print("  cd $BEHAVIOR_1K_DIR && ./install.sh")
