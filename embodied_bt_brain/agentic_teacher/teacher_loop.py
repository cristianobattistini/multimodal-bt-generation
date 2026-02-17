from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from xml.etree import ElementTree as ET

from embodied_bt_brain.primitive_library.validator import validate_bt_xml


# Pipeline: only conformance check (generates simple sequential BTs)
_PIPELINE = ["conformance"]


class TeacherPipelineError(Exception):
    """
    Raised when a teacher agent fails mid-pipeline, carrying partial artifacts so
    callers can persist intermediate steps (e.g., for cost recovery and debugging).
    """

    def __init__(
        self,
        agent: str,
        exc: Exception,
        *,
        steps: List[Dict[str, Any]],
        audit_log: List[dict],
        bt_xml: str,
    ) -> None:
        super().__init__(f"{agent} failed: {type(exc).__name__}: {exc}")
        self.agent = agent
        self.original_exc = exc
        self.steps = steps
        self.audit_log = audit_log
        self.bt_xml = bt_xml


class AgenticTeacherLoop:
    """
    Orchestrates a multi-agent "teacher" pipeline to produce a single BT XML.

    Notes:
    - Each agent is expected to return syntactically valid BT.CPP XML (or raise).
    - PAL conformance is enforced at the end (via ConformanceAgent).
    """

    def __init__(self, agents: Dict[str, Any]) -> None:
        self.agents = agents
        self.pipeline = _PIPELINE

    def generate_bt(
        self,
        instruction: str,
        contact_sheet_path: str,
        *,
        record_steps: bool = False,
        on_agent_step: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        # Always init steps list
        steps: List[Dict[str, Any]] = []
        audit_log: List[dict] = []

        scene_analysis = ""
        scene = self.agents.get("scene_analysis")
        if scene is not None:
            try:
                scene_analysis, scene_log = scene.analyze(  # type: ignore[call-arg]
                    instruction,
                    contact_sheet_path,
                )
                audit_log.append(scene_log)
                if on_agent_step:
                    on_agent_step("scene_analysis")
                if record_steps:
                    steps.append(
                        {
                            "agent": "scene_analysis",
                            "content": scene_analysis,
                            "ext": "txt",
                        }
                    )
            except Exception as exc:
                audit_log.append(
                    {
                        "agent": "SceneAnalysis",
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "used_llm": True,
                    }
                )
                if record_steps:
                    steps.append(
                        {
                            "agent": "scene_analysis_error",
                            "content": f"{type(exc).__name__}: {exc}",
                            "ext": "txt",
                        }
                    )
                raise TeacherPipelineError(
                    "scene_analysis",
                    exc,
                    steps=steps,
                    audit_log=audit_log,
                    bt_xml="",
                ) from exc

        architect = self.agents.get("architect")
        if architect is None:
            raise ValueError("Missing required agent: architect")

        draft_fn = getattr(architect, "draft", None)
        if not callable(draft_fn):
            raise TypeError(
                "Architect agent must implement draft(instruction, contact_sheet_path)."
            )

        bt_xml = ""
        try:
            bt_xml, architect_log = draft_fn(
                instruction,
                contact_sheet_path,
                scene_analysis=scene_analysis,
            )
            audit_log.extend(architect_log)
            if on_agent_step:
                on_agent_step("architect")
            if record_steps:
                steps.append(
                    {
                        "agent": "architect",
                        "bt_xml": bt_xml,
                        "type": "baseline",  # Mark as baseline for DPO
                    }
                )
        except Exception as exc:
            audit_log.append(
                {
                    "agent": "Architect",
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "used_llm": True,
                }
            )
            if record_steps:
                steps.append(
                    {
                        "agent": "architect_error",
                        "content": f"{type(exc).__name__}: {exc}",
                        "ext": "txt",
                    }
                )
            raise TeacherPipelineError(
                "architect",
                exc,
                steps=steps,
                audit_log=audit_log,
                bt_xml=bt_xml,
            ) from exc

        for agent_name in self.pipeline:
            agent = self.agents.get(agent_name)
            if agent is None:
                continue
            process_with_context = getattr(agent, "process_with_context", None)
            try:
                if callable(process_with_context):
                    bt_xml, agent_log = process_with_context(
                        bt_xml,
                        instruction=instruction,
                        scene_analysis=scene_analysis,
                    )
                else:
                    bt_xml, agent_log = agent.process(bt_xml)
                audit_log.extend(agent_log)
                if record_steps:
                    steps.append({"agent": agent_name, "bt_xml": bt_xml})
                if on_agent_step:
                    on_agent_step(agent_name)
            except Exception as exc:
                audit_log.append(
                    {
                        "agent": agent_name,
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "used_llm": True,
                    }
                )
                if record_steps:
                    steps.append(
                        {
                            "agent": f"{agent_name}_error",
                            "content": f"{type(exc).__name__}: {exc}",
                            "ext": "txt",
                        }
                    )
                raise TeacherPipelineError(
                    agent_name,
                    exc,
                    steps=steps,
                    audit_log=audit_log,
                    bt_xml=bt_xml,
                ) from exc

        # Final hard checks (syntactic + PAL v1 conformance) after all mutations.
        try:
            ET.fromstring(bt_xml)
        except ET.ParseError as exc:
            raise ValueError(f"final XML parse error: {exc}") from exc

        conformance_agent = self.agents.get("conformance")
        pal_spec = getattr(conformance_agent, "pal_spec", None)
        if pal_spec:
            final_issues = validate_bt_xml(bt_xml, pal_spec)
            audit_log.append(
                {
                    "agent": "FinalValidator",
                    "status": "ok" if not final_issues else "error",
                    "issues": final_issues,
                }
            )
            if final_issues:
                # Instead of raising, we can reject it
                return {
                    "bt_xml": bt_xml,
                    "audit_log": audit_log,
                    "score": 0,
                    "verdict": "REJECT",
                    "reason": f"PAL validation failed: {final_issues}",
                    "steps": steps
                }

        # All BTs that pass FinalValidator are accepted
        verdict = "ACCEPT"
        score = 1.0  # Binary: passed all validation checks

        result = {
            "bt_xml": bt_xml,
            "audit_log": audit_log,
            "score": score,
            "verdict": verdict,
            "steps": steps # Always include steps if record_steps was requested (or even if not? User said "Lossless")
        }
        return result


class SkipEpisode(Exception):
    def __init__(self, reason: str, *, details: Optional[dict] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}
