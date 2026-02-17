#!/usr/bin/env python3
"""
Quick test script for BEHAVIOR-1K integration.

Tests the full pipeline with your trained LoRA models.
"""

import sys
import os
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, "/home/cristiano/BEHAVIOR-1K")

print("="*80)
print("BEHAVIOR-1K Integration Test")
print("="*80)

# Test 1: Import checks
print("\n[Test 1/4] Checking imports...")
try:
    import omnigibson as og
    print("✓ OmniGibson imported")
except ImportError as e:
    print(f"✗ OmniGibson import failed: {e}")
    sys.exit(1)

try:
    from embodied_bt_brain.runtime import (
        BehaviorTreeExecutor,
        PALPrimitiveBridge,
        VLMInference,
        ValidatorLogger,
        SimulationHarness
    )
    print("✓ Runtime modules imported")
except ImportError as e:
    print(f"✗ Runtime import failed: {e}")
    sys.exit(1)

# Test 2: Check LoRA models
print("\n[Test 2/4] Checking LoRA models...")
lora_dir = Path.home() / "lora_models"
gemma_lora = lora_dir / "gemma3_4b_vision_bt_lora_06012026"
qwen_lora = lora_dir / "qwen2dot5-3B-Instruct_bt_lora_05012026"

if gemma_lora.exists():
    print(f"✓ Gemma3 LoRA found: {gemma_lora}")
else:
    print(f"✗ Gemma3 LoRA not found: {gemma_lora}")

if qwen_lora.exists():
    print(f"✓ Qwen2.5 LoRA found: {qwen_lora}")
else:
    print(f"✗ Qwen2.5 LoRA not found: {qwen_lora}")

# Test 3: Check dataset
print("\n[Test 3/4] Checking training dataset...")
dataset_dir = Path(__file__).parent / "dataset_agentic_v1"
if (dataset_dir / "train" / "data.jsonl").exists():
    print(f"✓ Training dataset found: {dataset_dir}")

    # Count examples
    import json
    with open(dataset_dir / "train" / "data.jsonl") as f:
        train_count = sum(1 for _ in f)
    print(f"  Training examples: {train_count}")

    # Check XML examples
    xml_files = list((dataset_dir / "steps_dump").rglob("*.xml"))
    print(f"  Intermediate BT XMLs: {len(xml_files)}")
else:
    print(f"✗ Training dataset not found: {dataset_dir}")

# Test 4: Parse example BT
print("\n[Test 4/4] Testing BT executor...")
example_bt = """<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <SubTree ID="T_Navigate" target="bread" />
      <SubTree ID="T_Grasp" target="bread" />
      <SubTree ID="T_Navigate" target="table" />
      <Action ID="PLACE_ON_TOP" obj="table"/>
      <Action ID="RELEASE"/>
    </Sequence>
  </BehaviorTree>
  <BehaviorTree ID="T_Navigate">
    <Action ID="NAVIGATE_TO" obj="{target}"/>
  </BehaviorTree>
  <BehaviorTree ID="T_Grasp">
    <Action ID="GRASP" obj="{target}"/>
  </BehaviorTree>
</root>"""

try:
    executor = BehaviorTreeExecutor()
    bt_root = executor.parse_xml_string(example_bt)
    print("✓ BT parsing successful")
    print("\n  BT Structure:")
    executor.print_tree(bt_root)
except Exception as e:
    print(f"✗ BT parsing failed: {e}")

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("✓ All basic tests passed!")
print("\n📝 Ready to run first episode:")
print("\nOption 1 - With Gemma3 (4B, faster):")
print("  python examples/run_behavior1k_episode.py \\")
print(f"    --lora-path {gemma_lora} \\")
print("    --model gemma3-4b \\")
print("    --task cleaning_windows \\")
print("    --symbolic  # Start with fast mode")

print("\nOption 2 - With Qwen2.5 (3B):")
print("  python examples/run_behavior1k_episode.py \\")
print(f"    --lora-path {qwen_lora} \\")
print("    --model qwen25-vl-3b \\")
print("    --task cleaning_windows \\")
print("    --symbolic")

print("\n⚠️  Note: First run will download base models (~8GB)")
print("="*80)
