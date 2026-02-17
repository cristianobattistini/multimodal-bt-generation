"""
VLM Inference: Load and run LoRA-finetuned VLMs for BT generation.

Supports:
- Qwen3-VL-8B (with LoRA adapter)
- Gemma3-4B (with LoRA adapter)

Usage:
    vlm = VLMInference(
        model_type="qwen3-vl-8b",
        lora_path="/path/to/qwen3_vl_8b_bt_lora"
    )

    bt_xml = vlm.generate_bt(
        image=rgb_array,
        instruction="pick up the bread and place it on the table"
    )
"""

import torch
import numpy as np
from PIL import Image
from typing import Union, Optional
from pathlib import Path
import os
import tempfile


class VLMInference:
    """
    VLM inference wrapper for BT generation.

    Handles both Qwen and Gemma models with their different APIs.
    """

    SUPPORTED_MODELS = {
        "qwen3-vl-8b": "unsloth/Qwen3-VL-8B-Instruct-unsloth-bnb-4bit",
        "gemma3-4b": "unsloth/gemma-3-4b-pt",
        "qwen25-vl-3b": "unsloth/Qwen2.5-VL-3B-Instruct",
    }

    def __init__(
        self,
        model_type: str = "qwen3-vl-8b",
        lora_path: Optional[str] = None,
        temperature: float = 0.2,
        load_in_4bit: bool = True,
        device: str = "cuda"
    ):
        """
        Initialize VLM inference.

        Args:
            model_type: Model type ("qwen3-vl-8b", "gemma3-4b", "qwen25-vl-3b")
            lora_path: Path to LoRA adapter (optional)
            temperature: Sampling temperature
            load_in_4bit: Use 4-bit quantization
            device: Device to load model on
        """
        if model_type not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model type: {model_type}. "
                f"Supported: {list(self.SUPPORTED_MODELS.keys())}"
            )

        self.model_type = model_type
        self.lora_path = lora_path
        self.temperature = temperature
        self.device = device

        # Import unsloth
        try:
            from unsloth import FastVisionModel, get_chat_template
            from peft import PeftModel
            self.FastVisionModel = FastVisionModel
            self.get_chat_template = get_chat_template
            self.PeftModel = PeftModel
        except ImportError:
            raise ImportError(
                "Failed to import unsloth. Install with: pip install unsloth"
            )

        # Load model
        print(f"[VLMInference] Loading {model_type}...")
        self._load_model(load_in_4bit)

    def _load_model(self, load_in_4bit: bool):
        base_model_name = self.SUPPORTED_MODELS[self.model_type]

        # Importante: evita device_map="auto" (sparge su CPU/disk)
        common_kwargs = dict(
            model_name=base_model_name,
            load_in_4bit=load_in_4bit,
            device_map="sequential",
            gpu_memory_utilization=0.90,   # prova 0.90-0.95 se hai VRAM libera
            # opzionale se Unsloth lo supporta per questo modello:
            # max_seq_length=2048,
        )

        if self.model_type.startswith("qwen"):
            self.model, self.tokenizer = self.FastVisionModel.from_pretrained(**common_kwargs)
            self.processor = None
        else:
            self.model, self.processor = self.FastVisionModel.from_pretrained(**common_kwargs)
            self.processor = self.get_chat_template(self.processor, "gemma-3")
            self.tokenizer = self.processor.tokenizer if self.processor else None

        if self.lora_path:
            self.model = self.PeftModel.from_pretrained(self.model, self.lora_path)

        self.FastVisionModel.for_inference(self.model)



    def generate_bt(
        self,
        image: Union[np.ndarray, Image.Image, str],
        instruction: str,
        max_new_tokens: int = 1536,
        return_full_output: bool = False,
        prompt_override: str = None
    ) -> str:
        """
        Generate BehaviorTree XML from image and instruction.

        Args:
            image: RGB image (numpy array, PIL Image, or file path)
            instruction: Task instruction
            max_new_tokens: Maximum tokens to generate
            return_full_output: If True, return full model output; if False, extract only XML

        Returns:
            BehaviorTree XML string
        """
        # Convert image to PIL
        if isinstance(image, str):
            pil_image = Image.open(image).convert("RGB")
        elif isinstance(image, np.ndarray):
            if image.dtype == np.float32 or image.dtype == np.float64:
                image = (image * 255).astype(np.uint8)
            pil_image = Image.fromarray(image)
        else:
            pil_image = image

        # Build prompt
        if prompt_override:
            prompt = prompt_override
        else:
            prompt = self._build_prompt(instruction)

        # Prepare input
        messages = [{
            "role": "user",
            "content": [
                {"type": "image" if self.model_type.startswith("qwen") else "image",
                 **({"image": pil_image} if self.model_type == "gemma3-4b" else {})},
                {"type": "text", "text": prompt}
            ]
        }]

        # Generate
        if self.model_type.startswith("qwen"):
            # Qwen3-VL format
            input_text = self.tokenizer.apply_chat_template(
                messages, add_generation_prompt=True)
            inputs = self.tokenizer(
                pil_image,  # Image first!
                input_text,  # Text second!
                add_special_tokens=False,
                return_tensors="pt"
            ).to(self.device)

            # Generation params for Qwen
            gen_kwargs = {
                "max_new_tokens": max_new_tokens,
                "temperature": self.temperature,
                "min_p": 0.1,
                "use_cache": True,
                "do_sample": True if self.temperature > 0 else False,
                "pad_token_id": self.tokenizer.pad_token_id
            }
        else:
            # Gemma format
            input_text = self.processor.apply_chat_template(
                messages, add_generation_prompt=True)
            inputs = self.processor(
                text=input_text,
                images=pil_image,
                add_special_tokens=False,
                return_tensors="pt"
            ).to(self.device)

            # Generation params for Gemma
            gen_kwargs = {
                "max_new_tokens": max_new_tokens,
                "temperature": self.temperature,
                "top_p": 0.95,
                "top_k": 64,
                "do_sample": True,
                "pad_token_id": self.processor.tokenizer.pad_token_id
            }

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(**inputs, **gen_kwargs)

        # Decode
        if self.model_type.startswith("qwen"):
            result = self.tokenizer.decode(
                outputs[0], skip_special_tokens=True)
        else:
            result = self.processor.tokenizer.decode(
                outputs[0], skip_special_tokens=True)

        # Extract XML if requested
        if return_full_output:
            return result
        else:
            return self._extract_xml(result)

    def _build_prompt(self, instruction: str) -> str:
        """Build prompt for BT generation"""
        # This matches the training prompt format
        return f"""ROLE: Embodied Planner
GOAL: Analyze the scene and generate a valid BehaviorTree.CPP XML plan.

INPUTS:
- Instruction: {instruction}
- Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), RELEASE(), PLACE_ON_TOP(obj), PLACE_INSIDE(obj), OPEN(obj), CLOSE(obj), TOGGLE_ON(obj), TOGGLE_OFF(obj), WIPE(obj), CUT(obj), SOAK_UNDER(obj), SOAK_INSIDE(obj), PLACE_NEAR_HEATING_ELEMENT(obj)]

OUTPUT FORMAT:
State Analysis:
Target: <snake_case_name>
Destination: <snake_case_name> or "none"
Plan:
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    ...
  </BehaviorTree>
</root>

CONSTRAINTS:
1. Analysis First: You MUST output the State Analysis block before the XML.
2. Consistency: The XML must strictly follow the analysis (target/destination names).
3. Compliance: Use ONLY the Allowed Actions provided."""

    def _extract_xml(self, full_output: str) -> str:
        """Extract XML portion from model output"""
        # Find XML block - use rfind to get LAST occurrence (actual model output, not prompt template)
        if "<root" in full_output and "</root>" in full_output:
            xml_start = full_output.rfind("<root")
            xml_end = full_output.rfind("</root>") + len("</root>")
            xml = full_output[xml_start:xml_end]

            # Clean up any extra whitespace
            xml = xml.strip()

            return xml
        else:
            # Return full output if no XML found
            return full_output

    def set_temperature(self, temperature: float):
        """Update sampling temperature"""
        self.temperature = temperature
