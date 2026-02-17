#!/usr/bin/env python3
"""
VLM Server - Local BT Generation
Supports Qwen2.5-VL-3B, Qwen3-VL-8B, Gemma3-4B, and SmolVLM2 models with LoRA adapters
"""

import argparse
import base64
import gc
import io
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Optional

import torch
from PIL import Image
from peft import PeftModel
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# NOTE: Unsloth is imported conditionally below (only for qwen/qwen3/gemma models)

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

parser = argparse.ArgumentParser(description="VLM BT Generator Server")
parser.add_argument(
    "--model",
    type=str,
    choices=["qwen", "qwen3", "gemma", "smol500", "smol2b"],
    required=True,
    help="Model to use: 'qwen' for Qwen2.5-VL-3B, 'qwen3' for Qwen3-VL-8B, 'gemma' for Gemma3-4B, 'smol500' for SmolVLM2-500M, or 'smol2b' for SmolVLM2-2.2B"
)
parser.add_argument(
    "--checkpoint",
    type=str,
    choices=["1", "2", "3", "final"],
    default="final",
    help="Checkpoint to use: '1', '2', '3' for intermediate checkpoints, 'final' for merged LoRA (default: final)"
)
parser.add_argument(
    "--port",
    type=int,
    default=7860,
    help="Port to run the server on (default: 7860)"
)
parser.add_argument(
    "--demo",
    action="store_true",
    help="Run a single demo sample from dataset_agentic_student/val and exit"
)
parser.add_argument(
    "--demo-index",
    type=int,
    default=0,
    help="Demo sample index in jsonl (0-based); use -1 for random"
)
parser.add_argument(
    "--demo-jsonl",
    type=str,
    default="/home/cristiano/multimodal-bt-generation/dataset_agentic/val/train_e2e.jsonl",
    help="Path to demo jsonl file"
)
parser.add_argument(
    "--demo-root",
    type=str,
    default="/home/cristiano/multimodal-bt-generation/dataset_agentic/val",
    help="Root folder for demo images"
)
parser.add_argument(
    "--demo-max-tokens",
    type=int,
    default=2048,
    help="Max tokens for demo generation"
)
parser.add_argument(
    "--demo-mode",
    type=str,
    choices=["adapter", "baseline", "openai"],
    default="adapter",
    help="Inference mode for demo: 'adapter' (default), 'baseline', or 'openai'"
)
parser.add_argument(
    "--debug-bt-file",
    type=str,
    default=None,
    help="Path to a pre-generated BT file (.md or .txt). When set, returns this instead of running inference"
)

args = parser.parse_args()

# ============================================================================
# DEBUG MODE: Load pre-generated BT if specified
# ============================================================================
DEBUG_BT_CONTENT = None
if args.debug_bt_file:
    debug_path = Path(args.debug_bt_file)
    if not debug_path.exists():
        print(f"⚠️  Warning: Debug BT file not found: {args.debug_bt_file}")
    else:
        DEBUG_BT_CONTENT = debug_path.read_text()
        print(f"\n{'='*80}")
        print(f"🔧 DEBUG MODE ENABLED")
        print(f"{'='*80}")
        print(f"File: {args.debug_bt_file}")
        print(f"Content length: {len(DEBUG_BT_CONTENT)} chars")
        print(f"{'-'*80}")
        print("LOADED BT CONTENT:")
        print(f"{'-'*80}")
        print(DEBUG_BT_CONTENT)
        print(f"{'-'*80}")
        print(f"{'='*80}\n")

# ============================================================================
# MODEL CONFIGURATION
# ============================================================================

# Dynamic model configs - models available for runtime switching
MODEL_CONFIGS = {
    "gemma": {
        "base_model": "unsloth/gemma-3-4b-pt",
        "chat_template": "gemma-3",
        "use_unsloth": True,
        "use_text_images": False,
        "default_allowed_actions": "NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,PLACE_NEXT_TO,OPEN,CLOSE",
        "generation_params": {
            "temperature": 0.3,
            "min_p": 0.1,
            "top_p": 0.95,
            "top_k": 64,
        },
    },
    "qwen": {
        "base_model": "unsloth/Qwen2.5-VL-3B-Instruct",
        "chat_template": None,
        "use_unsloth": True,
        "use_text_images": False,
        "default_allowed_actions": "NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,PLACE_NEXT_TO,OPEN,CLOSE",
        "generation_params": {
            "temperature": 0.2,
            "min_p": 0.1,
        },
    },
    "smol500": {
        "base_model": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
        "chat_template": None,
        "use_unsloth": False,
        "use_text_images": True,
        "default_allowed_actions": "NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,PLACE_NEXT_TO,OPEN,CLOSE",
        "generation_params": {
            "do_sample": False,
        },
    },
}

# Static model configs - only available at startup via --model, not for dynamic switching
_STATIC_MODEL_CONFIGS = {
    "qwen3": {
        "base_model": "unsloth/Qwen3-VL-8B-Instruct-unsloth-bnb-4bit",
        "chat_template": None,
        "use_unsloth": True,
        "use_text_images": False,
        "default_allowed_actions": "NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,PLACE_NEXT_TO,OPEN,CLOSE",
        "generation_params": {
            "temperature": 0.2,
            "min_p": 0.1,
        },
    },
    "smol2b": {
        "base_model": "HuggingFaceTB/SmolVLM2-2.2B-Instruct",
        "chat_template": None,
        "use_unsloth": False,
        "use_text_images": True,
        "default_allowed_actions": "NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,PLACE_NEXT_TO,OPEN,CLOSE",
        "generation_params": {
            "temperature": 0.2,
            "min_p": 0.1,
        },
    },
}

# Combined lookup for all models (dynamic + static)
_ALL_MODEL_CONFIGS = {**MODEL_CONFIGS, **_STATIC_MODEL_CONFIGS}

# Checkpoint configuration per model (unchanged)
CHECKPOINT_MAP = {
    "gemma": {
        "base": "/home/cristiano/lora_models/training_outputs/gemma3_vision_bt_training_outputs_02022026",
        "checkpoints": {"1": "checkpoint-138", "2": "checkpoint-276", "3": "checkpoint-414"},
        "final": "/home/cristiano/lora_models/gemma3_4b_vision_bt_lora_02022026",
        "valid_checkpoints": ["1", "2"],  # checkpoint 3 has no weights
    },
    "qwen": {
        "base": "/home/cristiano/lora_models/training_outputs/qwen2dot5-VL-2B-bt_training_outputs_02022026",
        "checkpoints": {"1": "checkpoint-138", "2": "checkpoint-276", "3": "checkpoint-414"},
        "final": "/home/cristiano/lora_models/qwen2dot5-3B-Instruct_bt_lora_02022026",
        "valid_checkpoints": ["1", "2", "3"],
    },
    "qwen3": {
        "base": "/home/cristiano/lora_models/training_outputs/qwen3_vl_bt_training_outputs_02022026",
        "checkpoints": {"1": "checkpoint-276", "2": "checkpoint-552", "3": "checkpoint-828"},
        "final": "/home/cristiano/lora_models/qwen3_vl_8b_bt_lora__02022026",
        "valid_checkpoints": ["3"],  # only checkpoint 3 has weights
    },
    "smol500": {
        "base": "/home/cristiano/lora_models/training_outputs/smolvlm2_500M_bt_training_outputs_02022026",
        "checkpoints": {"1": "checkpoint-138", "2": "checkpoint-276", "3": "checkpoint-414"},
        "final": "/home/cristiano/lora_models/smolvlm2_500M_bt_lora_02022026",
        "valid_checkpoints": ["1", "2", "3"],
    },
    # SmolVLM2 2B model not yet supported (training not complete)
    "smol2b": {
        "base": None,
        "checkpoints": {},
        "final": "/home/cristiano/lora_models/smolvlm2_2B_bt_lora__02022026",
        "valid_checkpoints": [],
    },
}


def resolve_lora_path(model: str, checkpoint: str) -> str:
    """Resolve the LoRA path based on model and checkpoint selection."""
    if model not in CHECKPOINT_MAP:
        raise ValueError(f"Unknown model: {model}")

    config = CHECKPOINT_MAP[model]

    if checkpoint == "final":
        return config["final"]

    if not config["valid_checkpoints"]:
        raise ValueError(
            f"Model '{model}' has no intermediate checkpoints available. Use --checkpoint final"
        )

    if checkpoint not in config["valid_checkpoints"]:
        raise ValueError(
            f"Checkpoint '{checkpoint}' for model '{model}' has no weights (adapter_model.safetensors missing). "
            f"Valid checkpoint options: {config['valid_checkpoints']} or 'final'"
        )

    ckpt_folder = config["checkpoints"][checkpoint]
    return os.path.join(config["base"], ckpt_folder)


# Resolve initial config from --model argument (for backward compat and Gradio defaults)
_INITIAL_LORA_PATH = resolve_lora_path(args.model, args.checkpoint)
_INITIAL_MODEL_CONFIG = _ALL_MODEL_CONFIGS[args.model]
_INITIAL_GENERATION_PARAMS = _INITIAL_MODEL_CONFIG["generation_params"]
_INITIAL_DEFAULT_ALLOWED_ACTIONS = _INITIAL_MODEL_CONFIG["default_allowed_actions"]

print(f"🚀 VLM Server configured for {args.model.upper()} model")
print(f"   Base model: {_INITIAL_MODEL_CONFIG['base_model']}")
print(f"   Checkpoint: {args.checkpoint}")
print(f"   LoRA adapter: {_INITIAL_LORA_PATH}")
print(f"   Dynamic models available: {list(MODEL_CONFIGS.keys())}")

# ============================================================================
# MODEL MANAGER - Handles dynamic model loading/unloading for different modes
# ============================================================================

class ModelManager:
    """
    Manages model state and VRAM for different inference modes and models.

    Supports:
    - Dynamic model switching between gemma, qwen, smol500 (via ensure_model)
    - Mode switching: 'adapter', 'baseline', 'openai'
    - VRAM management: unload, reset, status
    """

    def __init__(self, default_model_name: str, default_checkpoint: str = "final"):
        self.default_model_name = default_model_name
        self.default_checkpoint = default_checkpoint

        # Current state (initially nothing loaded)
        self.current_model_name: Optional[str] = None
        self.current_mode: Optional[str] = None
        self.model: Any = None
        self.tokenizer: Any = None
        self.processor: Any = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Derived config for the currently loaded model
        self._config: Optional[dict] = None  # Points to MODEL_CONFIGS/ALL entry
        self._lora_path: Optional[str] = None

    @property
    def use_text_images(self) -> bool:
        """Whether the current model uses text-based image input."""
        return self._config["use_text_images"] if self._config else False

    @property
    def generation_params(self) -> dict:
        """Generation parameters for the current model."""
        return self._config["generation_params"] if self._config else {}

    @property
    def default_allowed_actions(self) -> str:
        """Default allowed actions for the current model."""
        return self._config["default_allowed_actions"] if self._config else ""

    def ensure_model(self, model_name: str, mode: str) -> None:
        """
        Ensure the correct model AND mode are loaded.

        If model_name differs from current, unload and reconfigure.
        Then delegate to ensure_mode() for adapter/baseline loading.

        Args:
            model_name: Model to load (e.g. 'gemma', 'qwen', 'smol500')
            mode: Inference mode ('adapter', 'baseline', 'openai')
        """
        if mode == "openai":
            return  # No local model needed

        if model_name not in _ALL_MODEL_CONFIGS:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(_ALL_MODEL_CONFIGS.keys())}")

        if model_name != self.current_model_name:
            # Model change: must unload everything and reconfigure
            print(f"\n{'='*80}")
            print(f"🔄 MODEL SWITCH: {self.current_model_name or 'None'} → {model_name}")
            print(f"{'='*80}")

            if self.model is not None:
                self._unload_model()

            # Update internal config
            self._config = _ALL_MODEL_CONFIGS[model_name]
            # SmolVLM2 always uses final checkpoint (intermediate ones are too weak)
            ckpt = "final" if model_name == "smol500" else self.default_checkpoint
            self._lora_path = resolve_lora_path(model_name, ckpt)
            self.current_model_name = model_name
            self.current_mode = None  # Force reload in ensure_mode

            print(f"   Base model: {self._config['base_model']}")
            print(f"   LoRA path: {self._lora_path}")
            print(f"   Backend: {'Unsloth' if self._config['use_unsloth'] else 'Transformers'}")

        self.ensure_mode(mode)

    def ensure_mode(self, mode: str) -> None:
        """Ensure the correct inference mode is loaded (model must already be configured)."""
        if mode == "openai":
            return

        if self.current_mode == mode:
            return

        if self._config is None:
            raise RuntimeError("Model not configured. Call ensure_model() first.")

        print(f"\n{'='*80}")
        print(f"🔄 Switching inference mode: {self.current_mode or 'None'} → {mode}")
        print(f"{'='*80}")

        # Unload current model if switching between adapter/baseline
        if self.model is not None:
            self._unload_model()

        # Load the requested model
        if mode == "adapter":
            self._load_with_adapter()
        elif mode == "baseline":
            self._load_baseline()
        else:
            raise ValueError(f"Unknown mode: {mode}")

        self.current_mode = mode

    def unload(self) -> dict:
        """
        Unload model and free all VRAM. Returns status dict.
        Called by the /reset endpoint.
        """
        was_model = self.current_model_name
        was_mode = self.current_mode
        self._unload_model()
        self.current_model_name = None
        self.current_mode = None
        self._config = None
        self._lora_path = None
        return {
            "action": "unload",
            "unloaded_model": was_model,
            "was_mode": was_mode,
            "status": "ok",
            "vram_mb": self._get_vram_mb(),
        }

    def get_status(self) -> dict:
        """Return current model state for /status endpoint."""
        return {
            "model_name": self.current_model_name,
            "mode": self.current_mode,
            "model_loaded": self.model is not None,
            "vram_mb": self._get_vram_mb(),
            "default_model": self.default_model_name,
            "available_models": list(MODEL_CONFIGS.keys()),
        }

    def _get_vram_mb(self) -> Optional[float]:
        """Get current VRAM usage in MB."""
        if torch.cuda.is_available():
            return round(torch.cuda.memory_allocated() / 1024**2, 1)
        return None

    def _unload_model(self) -> None:
        """Unload model from GPU and free VRAM."""
        print("📤 Unloading model from GPU...")
        if self.model is not None:
            del self.model
            self.model = None
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        if self.processor is not None:
            del self.processor
            self.processor = None

        # Force garbage collection and clear CUDA cache
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        print("✓ VRAM freed")

    def _load_baseline(self) -> None:
        """Load base model WITHOUT LoRA adapter."""
        base_model = self._config["base_model"]
        print(f"📥 Loading baseline model (no adapter): {base_model}")

        if self._config["use_unsloth"]:
            self._load_unsloth_baseline()
        else:
            self._load_transformers_baseline()

        print("✓ Baseline model loaded successfully!")

    def _load_with_adapter(self) -> None:
        """Load base model WITH LoRA adapter."""
        base_model = self._config["base_model"]
        print(f"📥 Loading model with adapter: {base_model}")
        print(f"   LoRA path: {self._lora_path}")

        if self._config["use_unsloth"]:
            self._load_unsloth_with_adapter()
        else:
            self._load_transformers_with_adapter()

        print("✓ Model with adapter loaded successfully!")

    def _load_unsloth_baseline(self) -> None:
        """Load Unsloth model WITHOUT adapter."""
        from unsloth import FastVisionModel, get_chat_template

        base_model = self._config["base_model"]
        chat_template = self._config["chat_template"]

        if self.current_model_name in ("qwen", "qwen3"):
            self.model, self.tokenizer = FastVisionModel.from_pretrained(
                base_model,
                load_in_4bit=True,
                use_gradient_checkpointing="unsloth"
            )
        else:  # gemma
            self.model, self.processor = FastVisionModel.from_pretrained(
                base_model,
                load_in_4bit=True,
                use_gradient_checkpointing="unsloth"
            )
            if chat_template:
                print(f"📝 Applying {chat_template} chat template...")
                self.processor = get_chat_template(self.processor, chat_template)
                self.tokenizer = self.processor.tokenizer

        FastVisionModel.for_inference(self.model)

    def _load_unsloth_with_adapter(self) -> None:
        """Load Unsloth model WITH LoRA adapter."""
        from unsloth import FastVisionModel, get_chat_template

        base_model = self._config["base_model"]
        chat_template = self._config["chat_template"]

        if not os.path.exists(self._lora_path):
            raise FileNotFoundError(f"LoRA adapter not found: {self._lora_path}")

        if self.current_model_name in ("qwen", "qwen3"):
            self.model, self.tokenizer = FastVisionModel.from_pretrained(
                base_model,
                load_in_4bit=True,
                use_gradient_checkpointing="unsloth"
            )
        else:  # gemma
            self.model, self.processor = FastVisionModel.from_pretrained(
                base_model,
                load_in_4bit=True,
                use_gradient_checkpointing="unsloth"
            )
            if chat_template:
                print(f"📝 Applying {chat_template} chat template...")
                self.processor = get_chat_template(self.processor, chat_template)
                self.tokenizer = self.processor.tokenizer

        print("📦 Loading trained LoRA weights...")
        self.model = PeftModel.from_pretrained(self.model, self._lora_path)
        FastVisionModel.for_inference(self.model)

    def _load_transformers_baseline(self) -> None:
        """Load Transformers model (SmolVLM2) WITHOUT adapter."""
        from transformers import AutoProcessor, AutoModelForImageTextToText

        base_model = self._config["base_model"]

        # Load processor from base model
        self.processor = AutoProcessor.from_pretrained(base_model)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"   Device: {self.device}")

        self.model = AutoModelForImageTextToText.from_pretrained(
            base_model,
            torch_dtype=torch.bfloat16,
            attn_implementation="eager",
        ).to(self.device)
        self.model.eval()
        self.tokenizer = self.processor.tokenizer

    def _load_transformers_with_adapter(self) -> None:
        """Load Transformers model (SmolVLM2) WITH LoRA adapter."""
        from transformers import AutoProcessor, AutoModelForImageTextToText

        base_model = self._config["base_model"]

        if not os.path.exists(self._lora_path):
            raise FileNotFoundError(f"LoRA adapter not found: {self._lora_path}")

        # Load processor: prefer LoRA dir (has updated tokenizer), fall back to base model
        # Intermediate checkpoints only contain adapter weights, not processor files
        if os.path.exists(os.path.join(self._lora_path, "preprocessor_config.json")):
            self.processor = AutoProcessor.from_pretrained(self._lora_path)
        else:
            print(f"   ⚠ No processor in checkpoint dir, loading from base model")
            self.processor = AutoProcessor.from_pretrained(base_model)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"   Device: {self.device}")

        self.model = AutoModelForImageTextToText.from_pretrained(
            base_model,
            torch_dtype=torch.bfloat16,
            attn_implementation="eager",
        ).to(self.device)

        print("📦 Loading trained LoRA weights...")
        self.model = PeftModel.from_pretrained(self.model, self._lora_path, torch_dtype=torch.bfloat16)
        # Merge LoRA into base weights to avoid unsloth's monkey-patched peft forward
        # (unsloth patches Linear layers globally, causing dtype issues for SmolVLM2)
        print("📦 Merging LoRA weights into base model...")
        self.model = self.model.merge_and_unload()
        self.model.eval()
        self.tokenizer = self.processor.tokenizer


# Create global ModelManager instance (model loading is deferred to first request)
MODEL_MANAGER = ModelManager(
    default_model_name=args.model,
    default_checkpoint=args.checkpoint,
)

# ============================================================================
# OPENAI INTEGRATION - GPT-5 with service tier flex
# ============================================================================

def _call_openai_with_retry(image_pil: Image.Image, prompt: str, max_tokens: int = 2048) -> str:
    """
    Call GPT-5 via OpenAI API with service tier flex and retry logic.
    Falls back to 'standard' tier if flex fails after all retries.
    GPT-5 does not support temperature, uses reasoning_effort instead.
    """
    from openai import (
        OpenAI,
        APIConnectionError,
        APIError,
        APITimeoutError,
        RateLimitError,
    )

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY environment variable")

    # Load retry configuration from environment
    max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
    retry_base_sleep = float(os.getenv("OPENAI_RETRY_BASE_SLEEP", "1.5"))
    retry_max_sleep = float(os.getenv("OPENAI_RETRY_MAX_SLEEP", "20"))
    timeout_s = float(os.getenv("OPENAI_TIMEOUT", "900"))

    client = OpenAI(api_key=api_key, max_retries=0, timeout=timeout_s)

    # Convert PIL image to base64
    buffered = io.BytesIO()
    image_pil.save(buffered, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    # Build message with image
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
        ]
    }]

    # GPT-5 specific parameters
    # Valid tiers: 'auto', 'default', 'flex', 'priority'
    # NOTE: 'flex' is currently unreliable (timeouts), using 'auto' as default
    initial_tier = os.getenv("OPENAI_SERVICE_TIER", "auto")
    kwargs = {
        "model": "gpt-5",
        "messages": messages,
        "max_completion_tokens": int(os.getenv("OPENAI_MAX_COMPLETION_TOKENS", str(max_tokens))),
        "service_tier": initial_tier,
        "reasoning_effort": os.getenv("OPENAI_REASONING_EFFORT", "low"),
    }

    # Service tiers to try (no fallback needed with 'auto')
    tiers_to_try = [initial_tier]

    for tier in tiers_to_try:
        kwargs["service_tier"] = tier
        tier_label = f"[{tier}]"

        # Retry loop with exponential backoff for this tier
        for attempt in range(max_retries + 1):
            try:
                print(f"🌐 {tier_label} Calling OpenAI GPT-5 (attempt {attempt + 1}/{max_retries + 1})...")
                response = client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or ""
                print(f"✓ {tier_label} OpenAI response received ({len(content)} chars)")
                return content

            except (RateLimitError, APITimeoutError, APIConnectionError, APIError) as exc:
                if attempt >= max_retries:
                    # All retries for this tier exhausted
                    if tier != tiers_to_try[-1]:
                        print(f"⚠️  {tier_label} All {max_retries + 1} attempts failed. Falling back to 'auto' tier...")
                        break  # Try next tier
                    else:
                        raise RuntimeError(f"OpenAI API failed after trying all tiers: {exc}") from exc

                # Calculate sleep with exponential backoff
                sleep_s = min(retry_max_sleep, retry_base_sleep * (2 ** attempt))
                print(f"⚠️  {tier_label} OpenAI error: {type(exc).__name__}. Retrying in {sleep_s:.1f}s...")
                time.sleep(sleep_s)

    raise RuntimeError("Unreachable: retry loop exited without return or raise")


# Note: Model loading is deferred to first request via MODEL_MANAGER.ensure_model()
print("✓ Server configured (model will be loaded on first request)")

# ============================================================================
# GENERATION FUNCTIONS
# ============================================================================

def _generate_from_prompt(image, prompt, temperature, max_tokens):
    """Generate model output from a full prompt string + image using MODEL_MANAGER."""
    # Get model references from ModelManager
    model = MODEL_MANAGER.model
    tokenizer = MODEL_MANAGER.tokenizer
    processor = MODEL_MANAGER.processor
    device = MODEL_MANAGER.device

    if model is None:
        raise RuntimeError("Model not loaded. Call MODEL_MANAGER.ensure_model() first.")

    # Prepare messages (correct format for all models)
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": prompt}
        ]
    }]

    # Tokenize (model-specific)
    print("⏳ Tokenizing...")

    if MODEL_MANAGER.use_text_images:
        # SmolVLM2: processor(text=..., images=...)
        input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(
            text=input_text,
            images=image,
            add_special_tokens=False,
            return_tensors="pt",
        ).to(device).to(model.dtype)
        active_tokenizer = processor.tokenizer
    elif MODEL_MANAGER.current_model_name in ("qwen", "qwen3"):
        # Qwen: tokenizer(image, text)
        input_text = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
        inputs = tokenizer(
            image,
            input_text,
            add_special_tokens=False,
            return_tensors="pt"
        ).to("cuda")
        active_tokenizer = tokenizer
    else:
        # Gemma: processor(text=..., images=...)
        input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(
            text=input_text,
            images=image,
            add_special_tokens=False,
            return_tensors="pt"
        ).to("cuda")
        active_tokenizer = processor.tokenizer

    print(f"✓ Input tokens: {inputs['input_ids'].shape[1]}")

    # Generate with streaming
    print("🤖 Generating (streaming)...")
    print("-" * 80)

    with torch.no_grad():
        from transformers import TextIteratorStreamer
        from threading import Thread

        streamer = TextIteratorStreamer(
            active_tokenizer,
            skip_prompt=True,
            skip_special_tokens=True
        )

        # Build generation kwargs with model-specific parameters (from notebooks)
        generation_kwargs = {
            **inputs,
            "max_new_tokens": max_tokens,
            "use_cache": True,
            "pad_token_id": active_tokenizer.pad_token_id,
            "streamer": streamer,
        }

        # Add all generation params from model config
        generation_kwargs.update(MODEL_MANAGER.generation_params)
        # Only set temperature if model uses sampling (not greedy)
        if generation_kwargs.get("do_sample") is not False:
            generation_kwargs["temperature"] = temperature

        # Start generation in thread
        thread = Thread(target=model.generate, kwargs=generation_kwargs)
        thread.start()

        # Stream output
        generated_text = ""
        for new_text in streamer:
            generated_text += new_text
            print(new_text, end="", flush=True)

        thread.join()

    print("\n" + "-" * 80)
    print(f"✅ Generation complete ({len(generated_text)} chars)")
    print("="*80 + "\n")

    # Extract full output (State Analysis + Plan)
    if "State Analysis:" in generated_text:
        start = generated_text.rfind("State Analysis:")
        return generated_text[start:].strip()
    return generated_text


def _format_allowed_actions(actions_str):
    actions_str = (actions_str or "").strip()
    if not actions_str:
        actions_str = (MODEL_MANAGER.default_allowed_actions
                       or _INITIAL_DEFAULT_ALLOWED_ACTIONS)
    if actions_str.startswith("[") and actions_str.endswith("]"):
        actions_str = actions_str[1:-1]

    formatted = []
    for part in actions_str.split(","):
        action = part.strip()
        if not action:
            continue
        if "(" in action:
            formatted.append(action)
        elif action.upper() == "RELEASE":
            formatted.append("RELEASE()")
        else:
            formatted.append(f"{action}(obj)")
    return ", ".join(formatted)


def _is_raw_prompt(prompt_text):
    """Check if prompt is marked as raw (no placeholder substitution needed)."""
    if not prompt_text:
        return False
    return prompt_text.strip().startswith("__RAW__")


def _strip_raw_marker(prompt_text):
    """Remove __RAW__ marker from prompt text."""
    if prompt_text.strip().startswith("__RAW__"):
        return prompt_text.strip()[7:].strip()  # Remove "__RAW__" (7 chars) + whitespace
    return prompt_text


def _render_prompt_template(template_text, instruction, allowed_actions):
    if not template_text:
        return None
    if "{instruction}" not in template_text:
        raise ValueError("Prompt template missing {instruction} placeholder")
    if "{allowed_actions}" not in template_text and "{allowed actions}" not in template_text:
        raise ValueError("Prompt template missing {allowed_actions} placeholder")
    actions = _format_allowed_actions(allowed_actions)
    rendered = template_text.replace("{instruction}", instruction)
    rendered = rendered.replace("{allowed_actions}", actions)
    rendered = rendered.replace("{allowed actions}", actions)
    return rendered


def _build_prompt(instruction, allowed_actions):
    actions = _format_allowed_actions(allowed_actions)

    # Check if instruction contains context (format: "task\n\nContext: details")
    if "\n\nContext:" in instruction:
        main_instruction, context_part = instruction.split("\n\nContext:", 1)
        context_section = f"\n- Scene Context: {context_part.strip()}"
    else:
        main_instruction = instruction
        context_section = ""

    return f"""ROLE: Embodied Planner
GOAL: Analyze the scene and generate a valid BehaviorTree.CPP XML plan.

INPUTS:
- Instruction: {main_instruction}{context_section}
- Allowed Actions: [{actions}]

OUTPUT FORMAT:
State Analysis:
semantic_state:
  target: "<snake_case_or_empty>"
  destination: "<snake_case_or_empty>"
  constraints: []
  primitives: []
  risks:
    possible_failures: []
    recovery_hints: []
    logical_risks: []
Plan:
<root main_tree_to_execute="MainTree">
  ...
</root>

CONSTRAINTS:
1. Analysis First: You MUST output the State Analysis block before the XML.
2. Consistency: The XML must strictly follow the analysis (semantic_state.target / semantic_state.destination).
3. Schema: Output ONLY the keys shown above; do NOT add extra keys (e.g., no dynamic_risks).
4. Compliance: Use ONLY the Allowed Actions provided.
"""


def generate_bt(image, instruction, allowed_actions=None, temperature=None, max_tokens=2048,
                prompt_override=None, inference_mode="adapter", model_name=None):
    """
    Generate BehaviorTree XML from image and instruction.

    Args:
        image: PIL Image of the scene
        instruction: Task instruction text
        allowed_actions: Comma-separated list of allowed actions
        temperature: Generation temperature (ignored for OpenAI mode)
        max_tokens: Maximum tokens to generate
        prompt_override: Optional custom prompt template
        inference_mode: One of 'adapter', 'baseline', 'openai'
        model_name: Model to use (None = current or default). One of MODEL_CONFIGS keys.
    """
    # Validate inference mode
    valid_modes = ("adapter", "baseline", "openai")
    if inference_mode not in valid_modes:
        raise ValueError(f"Invalid inference_mode: {inference_mode}. Must be one of {valid_modes}")

    # Resolve model name: explicit > currently loaded > default
    effective_model = (model_name
                       or MODEL_MANAGER.current_model_name
                       or MODEL_MANAGER.default_model_name)

    # Reduce max_tokens for baseline mode (base model is slower and less capable)
    if inference_mode == "baseline":
        max_tokens = min(max_tokens, 512)

    # Use model-specific default temperature if not provided
    if temperature is None:
        model_cfg = _ALL_MODEL_CONFIGS.get(effective_model, {})
        temperature = model_cfg.get("generation_params", {}).get(
            "temperature", _INITIAL_GENERATION_PARAMS["temperature"]
        )

    # Log request
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "="*80)
    print(f"📥 REQUEST [{timestamp}]")
    print("="*80)
    print(f"Model: {effective_model.upper()}")
    print(f"Inference Mode: {inference_mode}")
    print(f"Instruction: {instruction}")
    print(f"🌡️  Temperature: {temperature}" + (" (ignored for OpenAI)" if inference_mode == "openai" else ""))
    print(f"Image: {'Provided' if image is not None else 'None'}")
    print("="*80)

    # DEBUG MODE: Return pre-generated BT if available
    if DEBUG_BT_CONTENT:
        print("\n" + "="*80)
        print("🔧 DEBUG MODE: Returning pre-generated BT (skipping inference)")
        print(f"   File: {args.debug_bt_file}")
        print(f"   Length: {len(DEBUG_BT_CONTENT)} chars")
        print("="*80)
        print("FULL DEBUG BT CONTENT:")
        print("-"*80)
        print(DEBUG_BT_CONTENT)
        print("-"*80)
        print("="*80)
        return DEBUG_BT_CONTENT

    # Build prompt (same for all modes)
    if prompt_override and prompt_override.strip():
        if _is_raw_prompt(prompt_override):
            # RAW MODE: Use prompt directly (no placeholder substitution)
            prompt = _strip_raw_marker(prompt_override)
            print("[PROMPT MODE] RAW - using prompt without modification")
        else:
            # TEMPLATE MODE: Render with placeholders
            prompt = _render_prompt_template(prompt_override, instruction, allowed_actions)
            print("[PROMPT MODE] TEMPLATE - rendered with {instruction} and {allowed_actions}")
    else:
        # DEFAULT MODE: Use built-in prompt
        prompt = _build_prompt(instruction, allowed_actions)
        print("[PROMPT MODE] DEFAULT - using built-in prompt structure")

    print("\n" + "="*80)
    print("PROMPT")
    print("="*80)
    print(prompt)
    print("="*80)

    # Dispatch to appropriate inference backend
    if inference_mode == "openai":
        # OpenAI GPT-5 inference (no local model needed)
        return _call_openai_with_retry(image, prompt, max_tokens)
    else:
        # Local model inference (adapter or baseline) - ensure correct model+mode
        MODEL_MANAGER.ensure_model(effective_model, inference_mode)
        return _generate_from_prompt(image, prompt, temperature, max_tokens)


def _load_demo_sample(jsonl_path, root_dir, index):
    with open(jsonl_path, "r") as f:
        lines = f.readlines()

    if not lines:
        raise ValueError(f"Empty demo jsonl: {jsonl_path}")

    if index < 0:
        index = random.randrange(len(lines))
    if index >= len(lines):
        raise IndexError(f"Demo index {index} out of range (0..{len(lines) - 1})")

    sample = json.loads(lines[index])
    messages = sample.get("messages", [])
    user_msg = next((m for m in messages if m.get("role") == "user"), None)
    assistant_msg = next((m for m in messages if m.get("role") == "assistant"), None)

    if not user_msg:
        raise ValueError("Demo sample missing user message")

    prompt_text = None
    image_rel = None
    for item in user_msg.get("content", []):
        if item.get("type") == "text":
            prompt_text = item.get("text")
        elif item.get("type") == "image":
            image_rel = item.get("image")

    if not prompt_text or not image_rel:
        raise ValueError("Demo sample missing prompt text or image path")

    image_path = Path(root_dir) / image_rel
    if not image_path.exists():
        raise FileNotFoundError(f"Demo image not found: {image_path}")

    gt_text = None
    if assistant_msg:
        contents = assistant_msg.get("content", [])
        if contents and contents[0].get("type") == "text":
            gt_text = contents[0].get("text")

    return index, prompt_text, image_path, gt_text


def _extract_instruction_line(prompt_text):
    for line in prompt_text.splitlines():
        if line.strip().lower().startswith("- instruction:"):
            return line.strip()
    return None


def run_demo():
    demo_jsonl = args.demo_jsonl
    demo_root = args.demo_root
    demo_index = args.demo_index
    demo_mode = args.demo_mode

    print("\n" + "="*80)
    print("🧪 Running demo sample")
    print("="*80)
    print(f"JSONL: {demo_jsonl}")
    print(f"Root : {demo_root}")
    print(f"Mode : {demo_mode}")

    idx, prompt_text, image_path, gt_text = _load_demo_sample(
        demo_jsonl, demo_root, demo_index
    )

    instruction_line = _extract_instruction_line(prompt_text)
    if instruction_line:
        print(f"Sample {idx}: {instruction_line}")
    else:
        print(f"Sample {idx}: (instruction line not found)")
    print(f"Image: {image_path}")

    image = Image.open(image_path).convert("RGB")
    model_cfg = _ALL_MODEL_CONFIGS.get(args.model, {})
    temperature = model_cfg.get("generation_params", {}).get(
        "temperature", _INITIAL_GENERATION_PARAMS["temperature"]
    )

    # Dispatch based on inference mode
    if demo_mode == "openai":
        output = _call_openai_with_retry(image, prompt_text, args.demo_max_tokens)
    else:
        # Local model inference (adapter or baseline)
        MODEL_MANAGER.ensure_model(args.model, demo_mode)
        output = _generate_from_prompt(
            image=image,
            prompt=prompt_text,
            temperature=temperature,
            max_tokens=args.demo_max_tokens
        )

    print("\n" + "="*80)
    print("MODEL OUTPUT")
    print("="*80)
    print(output)

    if gt_text:
        print("\n" + "="*80)
        print("GROUND TRUTH")
        print("="*80)
        print(gt_text)
    else:
        print("\n(No ground truth found in sample)")

# ============================================================================
# GRADIO INTERFACE
# ============================================================================

def gradio_wrapper(image, instruction, allowed_actions, temperature, prompt_template, inference_mode):
    """Wrapper for Gradio interface with multi-mode inference support.
    Signature: 6 parameters (backward-compatible with VLMClient).
    Uses whatever model is currently loaded (via switch_model) or the default.
    """
    try:
        output = generate_bt(
            image, instruction, allowed_actions, temperature,
            prompt_override=prompt_template,
            inference_mode=inference_mode,
            model_name=None,  # Uses current or default model
        )
        return output
    except Exception as e:
        error_msg = f"Error [{inference_mode}]: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return error_msg

def _handle_switch_model(model_name):
    """Pre-load a model (adapter mode by default). Called via /switch_model endpoint."""
    try:
        MODEL_MANAGER.ensure_model(model_name, "adapter")
        return MODEL_MANAGER.get_status()
    except Exception as e:
        return {"error": str(e), **MODEL_MANAGER.get_status()}


def build_gradio_interface():
    try:
        import gradio as gr
    except ImportError as exc:
        raise ImportError(
            "gradio is required to run the server UI. Install it or use --demo."
        ) from exc

    with gr.Blocks(title=f"VLM BT Generator - {args.model.upper()}") as demo:
        gr.Markdown(f"# VLM BT Generator - {args.model.upper()}")
        gr.Markdown("Generates Behavior Trees from robot camera images and task instructions.")

        # ---- MAIN PREDICT (6 params, backward-compatible) ----
        with gr.Row():
            with gr.Column(scale=2):
                image_input = gr.Image(type="pil", label="Robot Camera View")
                instruction_input = gr.Textbox(
                    label="Task Instruction",
                    placeholder="bring the water bottle to the coffee table",
                )
                allowed_actions_input = gr.Textbox(
                    label="Allowed Actions",
                    value=_INITIAL_DEFAULT_ALLOWED_ACTIONS,
                )
                temperature_input = gr.Slider(
                    0.1, 1.0,
                    value=_INITIAL_GENERATION_PARAMS["temperature"],
                    label="Temperature",
                    step=0.1,
                )
                prompt_template_input = gr.Textbox(
                    label="Prompt Template (optional)",
                    lines=8,
                    placeholder="Use {instruction} and {allowed_actions}",
                )
                inference_mode_input = gr.Radio(
                    choices=["adapter", "baseline", "openai"],
                    value="adapter",
                    label="Inference Mode",
                    info="adapter=LoRA finetuned, baseline=base model only, openai=GPT-5 API",
                )
            with gr.Column(scale=2):
                output_text = gr.Textbox(label="Generated Output (State Analysis + BT XML)", lines=30)
                generate_btn = gr.Button("Generate", variant="primary")

        generate_btn.click(
            fn=gradio_wrapper,
            inputs=[image_input, instruction_input, allowed_actions_input,
                    temperature_input, prompt_template_input, inference_mode_input],
            outputs=output_text,
            api_name="predict",  # backward-compat with VLMClient
        )

        # ---- MODEL MANAGEMENT (new endpoints) ----
        gr.Markdown("---\n### Model Management")
        gr.Markdown(f"Dynamic models: **{', '.join(MODEL_CONFIGS.keys())}**")
        with gr.Row():
            model_selector = gr.Radio(
                choices=list(MODEL_CONFIGS.keys()),
                value=args.model if args.model in MODEL_CONFIGS else list(MODEL_CONFIGS.keys())[0],
                label="Switch Model",
            )
            switch_btn = gr.Button("Switch Model")
            reset_btn = gr.Button("Reset / Unload", variant="stop")
            status_btn = gr.Button("Status")
        status_output = gr.JSON(label="Status")

        switch_btn.click(
            fn=_handle_switch_model,
            inputs=[model_selector],
            outputs=status_output,
            api_name="switch_model",
        )
        reset_btn.click(
            fn=lambda: MODEL_MANAGER.unload(),
            inputs=[],
            outputs=status_output,
            api_name="reset",
        )
        status_btn.click(
            fn=lambda: MODEL_MANAGER.get_status(),
            inputs=[],
            outputs=status_output,
            api_name="status",
        )

    return demo

# ============================================================================
# LAUNCH SERVER
# ============================================================================

if __name__ == "__main__":
    if args.demo:
        run_demo()
        raise SystemExit(0)

    print("\n" + "="*80)
    print(f"🌐 Starting VLM Server ({args.model.upper()})...")
    print("="*80)

    demo = build_gradio_interface()
    demo.launch(
        server_name="0.0.0.0",  # Accept connections from network
        server_port=args.port,
        share=False,
        show_error=True
    )
