"""
Behavior Tree Generation

VLM client integration for generating and mapping behavior trees.
"""


class BTGenerator:
    """
    Generates behavior trees using VLM and handles object name mapping.

    Features:
    - VLM client management (lazy initialization)
    - BT generation from image + instruction
    - Object name mapping (pre-mapping or on-demand)
    """

    def __init__(self, args, log_fn=print):
        """
        Initialize BT generator.

        Args:
            args: Parsed arguments with server_url, temperature, allowed_actions, on_demand_mapping
            log_fn: Logging function
        """
        self.args = args
        self.log = log_fn
        self._vlm_client = None

    @property
    def vlm_client(self):
        """Get or create VLM client (lazy initialization)."""
        if self._vlm_client is None and self.args.server_url:
            from .client import VLMClient
            self._vlm_client = VLMClient(gradio_url=self.args.server_url)
        return self._vlm_client

    def generate_bt(self, image, instruction, inference_mode="adapter", model_name=None):
        """
        Generate behavior tree from image and instruction.

        Args:
            image: PIL Image of the scene
            instruction: Natural language instruction
            inference_mode: One of 'adapter', 'baseline', 'openai' (default: 'adapter')
            model_name: Optional model to switch to before generation (e.g. 'gemma', 'qwen', 'smol500')

        Returns:
            Tuple of (bt_xml string, full_output string)

        Raises:
            RuntimeError: If no VLM client configured
        """
        if self.vlm_client is None:
            raise RuntimeError("No VLM configured. Use --server-url")

        if model_name:
            self.vlm_client.switch_model(model_name)

        bt_xml, full_output = self.vlm_client.generate_bt(
            image=image,
            instruction=instruction,
            allowed_actions=self.args.allowed_actions,
            temperature=self.args.temperature,
            prompt_template=None,
            inference_mode=inference_mode
        )

        return bt_xml, full_output

    def generate_bt_with_prompt(self, image, instruction, prompt_template=None, env=None,
                                temperature=None, inference_mode="adapter", model_name=None):
        """
        Generate behavior tree with optional custom prompt template.

        Args:
            image: PIL Image of the scene
            instruction: Natural language instruction
            prompt_template: Optional prompt template. Can be:
                - None: Use default prompt
                - String with {instruction} and {allowed_actions}: Template mode
                - String starting with __RAW__: Raw mode (no substitution)
                - String with {scene_objects}: Objects injected from env (requires env param)
            env: Optional OmniGibson environment (required if template has {scene_objects})
            temperature: Optional temperature override. If None, uses args.temperature
            inference_mode: One of 'adapter', 'baseline', 'openai' (default: 'adapter')
            model_name: Optional model to switch to before generation (e.g. 'gemma', 'qwen', 'smol500')

        Returns:
            Tuple of (bt_xml string, full_output string)

        Raises:
            RuntimeError: If no VLM client configured
        """
        if self.vlm_client is None:
            raise RuntimeError("No VLM configured. Use --server-url")

        if model_name:
            self.vlm_client.switch_model(model_name)

        # Use provided temperature or fallback to args
        temp = temperature if temperature is not None else self.args.temperature

        # If template contains {scene_objects}, render on client side
        final_prompt = prompt_template
        if prompt_template and "{scene_objects}" in prompt_template:
            final_prompt = self._render_with_scene_objects(
                prompt_template, instruction, env
            )

        bt_xml, full_output = self.vlm_client.generate_bt(
            image=image,
            instruction=instruction,
            allowed_actions=self.args.allowed_actions,
            temperature=temp,
            prompt_template=final_prompt,
            inference_mode=inference_mode
        )

        return bt_xml, full_output

    def _render_with_scene_objects(self, template, instruction, env):
        """
        Render template with scene objects on client side.

        This is needed because the VLM server doesn't have access to the
        OmniGibson environment, so {scene_objects} must be resolved here.

        Args:
            template: Prompt template with {scene_objects} placeholder
            instruction: Task instruction
            env: OmniGibson environment

        Returns:
            Rendered prompt as RAW (ready to send to server without further processing)
        """
        from .client import render_prompt_template, get_scene_objects_str

        # Get scene objects
        scene_objects_str = "(scene objects not available)"
        if env:
            scene_objects_str = get_scene_objects_str(env)
            self.log(f"  [PROMPT] Injecting {len(scene_objects_str.splitlines())} scene objects into prompt")

        # Render template
        rendered = render_prompt_template(
            template,
            instruction,
            self.args.allowed_actions,
            scene_objects_str=scene_objects_str
        )

        # Return as RAW so server doesn't try to render again
        if not rendered.strip().startswith("__RAW__"):
            rendered = "__RAW__\n" + rendered

        return rendered

    def map_objects(self, bt_xml, env, task_id=None):
        """
        Map VLM object names to simulation objects.

        If on_demand_mapping is enabled, skip pre-mapping and let
        primitive_bridge resolve objects during execution. This allows
        objects inside containers (e.g., bottle in fridge) to be found
        after the container is opened.

        Args:
            bt_xml: Behavior tree XML string
            env: OmniGibson environment
            task_id: Optional task identifier (e.g., '00_turning_on_radio')
                     for task-specific BDDL object mapping

        Returns:
            Mapped BT XML string (or original if on-demand mapping enabled)
        """
        if self.args.on_demand_mapping:
            self.log("  [MAPPING] On-demand mapping enabled - skipping pre-mapping")
            self.log("  [MAPPING] Objects will be resolved during BT execution")
            return bt_xml

        from .object_mapping import resolve_object_names
        return resolve_object_names(bt_xml, env, task_id=task_id)
