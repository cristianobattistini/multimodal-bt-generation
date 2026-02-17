"""
VLM Client

Gradio client for remote VLM inference.
"""

import numpy as np
from PIL import Image


def extract_last_bt_xml(full_output: str) -> str:
    """Extract the last complete <root>...</root> XML block from VLM output."""
    if not full_output:
        return full_output

    # Remove markdown fences if present
    text = full_output.replace("```xml", "").replace("```", "")

    # Prefer the last <root main_tree_to_execute=...> block
    start = text.rfind('<root main_tree_to_execute=')
    if start == -1:
        start = text.rfind("<root")
        if start == -1:
            return text.strip()

    # Take the FIRST </root> after that start (not rfind)
    end = text.find("</root>", start)
    if end == -1:
        return text[start:].strip()

    end += len("</root>")
    return text[start:end].strip()


def render_prompt_template(template_text, instruction, allowed_actions_str, scene_objects_str=None):
    """
    Render a prompt template by substituting placeholders.

    Args:
        template_text: Template with placeholders:
            - {instruction}: Task instruction (required)
            - {allowed_actions}: Available actions (required)
            - {scene_objects}: Objects in scene (optional)
        instruction: The task instruction
        allowed_actions_str: String of allowed actions
        scene_objects_str: Optional string listing scene objects (for BDDL name generation)

    Returns:
        Rendered prompt string, or None if template_text is empty
    """
    if not template_text:
        return None
    if "{instruction}" not in template_text:
        raise ValueError("Prompt template missing {instruction} placeholder")
    if "{allowed_actions}" not in template_text and "{allowed actions}" not in template_text:
        raise ValueError("Prompt template missing {allowed_actions} placeholder")

    rendered = template_text.replace("{instruction}", instruction)
    rendered = rendered.replace("{allowed_actions}", allowed_actions_str)
    rendered = rendered.replace("{allowed actions}", allowed_actions_str)

    # Optional: scene objects for BDDL name generation
    if "{scene_objects}" in rendered:
        if scene_objects_str:
            rendered = rendered.replace("{scene_objects}", scene_objects_str)
        else:
            rendered = rendered.replace("{scene_objects}", "(not available)")

    return rendered


def get_scene_objects_str(env):
    """
    Get formatted string of scene objects for prompt injection.

    Args:
        env: OmniGibson environment

    Returns:
        Formatted string listing objects with their categories
    """
    lines = []
    try:
        for obj in getattr(env.scene, "objects", []):
            name = getattr(obj, "name", "unknown")
            category = getattr(obj, "category", "")
            if category:
                lines.append(f"- {name} ({category})")
            else:
                lines.append(f"- {name}")
    except Exception as e:
        return f"(error getting objects: {e})"

    return "\n".join(lines) if lines else "(no objects found)"


class VLMClient:
    """
    Client for calling VLM server via Gradio API.

    Connects to a Gradio server hosting a VLM model and generates
    behavior trees from images and instructions.
    """

    def __init__(self, gradio_url):
        """
        Initialize VLM client.

        Args:
            gradio_url: URL of the Gradio server (e.g., http://10.79.2.183:7860)
        """
        from gradio_client import Client

        self.gradio_url = gradio_url.rstrip("/")
        print(f"[VLM] Connecting to server: {self.gradio_url}")

        try:
            self.client = Client(self.gradio_url)
            print(f"[VLM] Connected successfully")

            # Always use explicit api_name — required when server
            # exposes multiple endpoints (gr.Blocks with /switch_model, etc.)
            print("[VLM] Connected (using explicit api_name for all endpoints)")

        except Exception as e:
            raise Exception(f"Failed to connect: {e}")

    def generate_bt(self, image, instruction, allowed_actions, temperature=0.3,
                    prompt_template=None, inference_mode="adapter"):
        """
        Call VLM to generate behavior tree.

        Args:
            image: PIL Image or numpy array
            instruction: Natural language instruction
            allowed_actions: String of allowed actions
            temperature: Sampling temperature (default 0.3)
            prompt_template: Optional custom prompt template
            inference_mode: One of 'adapter', 'baseline', 'openai' (default: 'adapter')

        Returns:
            tuple: (bt_xml, full_output) - XML tree and complete VLM output
        """
        import tempfile
        import os
        from gradio_client import handle_file

        # Convert to PIL
        if isinstance(image, np.ndarray):
            if image.dtype in [np.float32, np.float64]:
                image = (image * 255).astype(np.uint8)
            pil_img = Image.fromarray(image)
        else:
            pil_img = image

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            pil_img.save(f.name)
            temp_path = f.name

        print(f"[VLM] Requesting BT from server...")

        try:
            result = self.client.predict(
                handle_file(temp_path),
                instruction,
                allowed_actions,
                temperature,
                prompt_template or "",
                inference_mode,  # 6th parameter: inference mode
                api_name="/predict"
            )

            # Store full output
            full_output = result

            # Extract XML portion (ROBUST): pick the last complete <root...></root>
            bt_xml = extract_last_bt_xml(full_output)

            # Fallback if no root block was found
            if "<root" not in bt_xml or "</root>" not in bt_xml:
                print("[VLM] No valid <root>...</root> found, using full output")
                bt_xml = full_output
            else:
                print(f"[VLM] BT XML received ({len(bt_xml)} chars)")

            # Return both XML and full output
            return bt_xml, full_output

        except Exception as e:
            raise Exception(f"VLM prediction error: {e}")

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # ------------------------------------------------------------------
    # Model management endpoints (require gr.Blocks server with these APIs)
    # ------------------------------------------------------------------

    def switch_model(self, model_name: str) -> dict:
        """Switch VLM server to a different model. Calls /switch_model endpoint.

        Args:
            model_name: One of the dynamic model names (e.g. 'gemma', 'qwen', 'smol500')

        Returns:
            Status dict from the server
        """
        print(f"[VLM] Switching server model to: {model_name}")
        result = self.client.predict(model_name, api_name="/switch_model")
        print(f"[VLM] Switch result: {result}")
        return result

    def reset_model(self) -> dict:
        """Unload current model from server to free VRAM. Calls /reset endpoint.

        Returns:
            Status dict from the server
        """
        print("[VLM] Requesting model reset/unload...")
        result = self.client.predict(api_name="/reset")
        print(f"[VLM] Reset result: {result}")
        return result

    def get_server_status(self) -> dict:
        """Get server status (loaded model, mode, VRAM). Calls /status endpoint.

        Returns:
            Status dict from the server
        """
        result = self.client.predict(api_name="/status")
        return result
