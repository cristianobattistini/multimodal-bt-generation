"""
VLM Inference using native HuggingFace transformers + PEFT (no unsloth).

More compatible with different PyTorch versions.
"""

import torch
import numpy as np
from PIL import Image
from typing import Union, Optional
from pathlib import Path


class VLMInferenceNative:
    """
    VLM inference using transformers + PEFT only (no unsloth dependency).
    """

    SUPPORTED_MODELS = {
        "gemma3-4b": "unsloth/gemma-3-4b-pt-unsloth-bnb-4bit",  # Unsloth pre-quantized (no gating)
        "qwen25-vl-3b": "Qwen/Qwen2.5-VL-3B-Instruct",
    }

    def __init__(
        self,
        model_type: str = "gemma3-4b",
        lora_path: Optional[str] = None,
        temperature: float = 0.2,
        load_in_4bit: bool = True,
        device: str = "cuda"
    ):
        """Initialize VLM with native transformers"""
        if model_type not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_type}. Use: {list(self.SUPPORTED_MODELS.keys())}")

        self.model_type = model_type
        self.lora_path = lora_path
        self.temperature = temperature
        self.device = device

        # Import libraries
        try:
            from transformers import AutoProcessor, AutoModelForVision2Seq, BitsAndBytesConfig
            from peft import PeftModel
            self.AutoProcessor = AutoProcessor
            self.AutoModelForVision2Seq = AutoModelForVision2Seq
            self.BitsAndBytesConfig = BitsAndBytesConfig
            self.PeftModel = PeftModel
        except ImportError as e:
            raise ImportError(f"Install: pip install transformers peft bitsandbytes. Error: {e}")

        print(f"[VLMInferenceNative] Loading {model_type}...")
        self._load_model(load_in_4bit)

    def _load_model(self, load_in_4bit: bool):
        """Load model with native transformers"""
        base_model_name = self.SUPPORTED_MODELS[self.model_type]

        # Quantization config
        if load_in_4bit:
            quantization_config = self.BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
        else:
            quantization_config = None

        # Load processor
        self.processor = self.AutoProcessor.from_pretrained(
            base_model_name,
            trust_remote_code=True
        )

        # Load base model
        self.model = self.AutoModelForVision2Seq.from_pretrained(
            base_model_name,
            quantization_config=quantization_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16 if not load_in_4bit else None
        )

        # Load LoRA if provided
        if self.lora_path:
            print(f"[VLMInferenceNative] Loading LoRA from {self.lora_path}")
            self.model = self.PeftModel.from_pretrained(
                self.model,
                self.lora_path,
                is_trainable=False
            )

        self.model.eval()
        print(f"[VLMInferenceNative] Model loaded!")

        # Print GPU stats
        if torch.cuda.is_available():
            gpu_stats = torch.cuda.get_device_properties(0)
            used_mem = round(torch.cuda.max_memory_reserved() / 1024**3, 2)
            total_mem = round(gpu_stats.total_memory / 1024**3, 2)
            print(f"[VLMInferenceNative] GPU: {gpu_stats.name}")
            print(f"[VLMInferenceNative] Memory: {used_mem} GB / {total_mem} GB")

    def generate_bt(
        self,
        image: Union[np.ndarray, Image.Image, str],
        instruction: str,
        max_new_tokens: int = 1536,
        return_full_output: bool = False
    ) -> str:
        """Generate BehaviorTree XML"""
        # Convert image to PIL
        if isinstance(image, str):
            pil_image = Image.open(image).convert("RGB")
        elif isinstance(image, np.ndarray):
            if image.dtype in [np.float32, np.float64]:
                image = (image * 255).astype(np.uint8)
            pil_image = Image.fromarray(image)
        else:
            pil_image = image

        # Build prompt
        prompt = self._build_prompt(instruction)

        # Prepare inputs
        if self.model_type.startswith("qwen"):
            # Qwen format
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": prompt}
                ]
            }]
            text = self.processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
            inputs = self.processor(images=pil_image, text=text, return_tensors="pt").to(self.device)

        else:
            # Gemma format
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_image},
                    {"type": "text", "text": prompt}
                ]
            }]
            text = self.processor.apply_chat_template(messages, add_generation_prompt=True)
            inputs = self.processor(text=text, images=pil_image, return_tensors="pt").to(self.device)

        # Generation params
        if self.model_type.startswith("qwen"):
            gen_kwargs = {
                "max_new_tokens": max_new_tokens,
                "temperature": self.temperature,
                "do_sample": True if self.temperature > 0 else False,
            }
        else:
            # Gemma
            gen_kwargs = {
                "max_new_tokens": max_new_tokens,
                "temperature": self.temperature,
                "top_p": 0.95,
                "top_k": 64,
                "do_sample": True,
            }

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(**inputs, **gen_kwargs)

        # Decode
        result = self.processor.batch_decode(outputs, skip_special_tokens=True)[0]

        # Extract XML
        if return_full_output:
            return result
        else:
            return self._extract_xml(result)

    def _build_prompt(self, instruction: str) -> str:
        """Build BT generation prompt"""
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
        """Extract XML from model output"""
        if "<root" in full_output and "</root>" in full_output:
            xml_start = full_output.index("<root")
            xml_end = full_output.index("</root>") + len("</root>")
            return full_output[xml_start:xml_end].strip()
        return full_output

    def set_temperature(self, temperature: float):
        """Update temperature"""
        self.temperature = temperature
