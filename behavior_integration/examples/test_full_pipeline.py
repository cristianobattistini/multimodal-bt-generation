#!/usr/bin/env python3
"""
Test the full pipeline: VLM generation → BT execution in simulation
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, '/home/cristiano/BEHAVIOR-1K/OmniGibson')

from embodied_bt_brain.runtime.vlm_inference import VLMInference
from embodied_bt_brain.runtime import BehaviorTreeExecutor
from PIL import Image

print("="*80)
print("Full Pipeline Test: VLM → BT Parsing")
print("="*80)

# Step 1: Generate BT with VLM
print("\n[1/2] Generating BT with Gemma3 LoRA...")
dummy_img = Image.new('RGB', (224, 224), color='gray')

vlm = VLMInference(
    model_type='gemma3-4b',
    lora_path='/home/cristiano/lora_models/gemma3_4b_vision_bt_lora_06012026',
    temperature=0.3
)

instruction = "pick up the apple and place it in the basket"
bt_xml = vlm.generate_bt(image=dummy_img, instruction=instruction)

print(f"✓ Generated BT ({len(bt_xml)} chars)")
print("\nGenerated BT (first 500 chars):")
print("-"*80)
print(bt_xml[:500])
print("-"*80)

# Step 2: Parse BT
print("\n[2/2] Parsing BT...")
executor = BehaviorTreeExecutor()
bt_root = executor.parse_xml_string(bt_xml)

print(f"✓ Parsed successfully!")
print(f"  Root: {bt_root.__class__.__name__}")
print(f"  Children: {len(bt_root.children)}")

print("\n" + "="*80)
print("✅ Full pipeline test successful!")
print("="*80)
print("\nNext: Integrate with OmniGibson simulation")
print("  - Load BEHAVIOR-1K scene")
print("  - Execute BT primitives")
print("  - Log failures for validator training")
