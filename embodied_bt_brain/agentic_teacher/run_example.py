import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embodied_bt_brain.agentic_teacher import AgenticTeacherLoop
from embodied_bt_brain.agentic_teacher.agents import (
    ArchitectAgent,
    ConformanceAgent,
    RobustnessAgent,
    SceneAnalysisAgent,
    SubtreeEnablementAgent,
)
from embodied_bt_brain.agentic_teacher.llm_client import LLMClient
from embodied_bt_brain.primitive_library.validator import load_default_pal_spec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--contact-sheet", required=True, help="Path to contact sheet image (jpeg).")
    parser.add_argument("--model", default=None, help="OpenAI model name")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    pal_spec = load_default_pal_spec()
    llm_client = LLMClient(model=args.model)

    agents = {
        "scene_analysis": SceneAnalysisAgent(llm_client=llm_client),
        "architect": ArchitectAgent(llm_client),
        "robustness": RobustnessAgent(llm_client=llm_client),
        "subtree_enablement": SubtreeEnablementAgent(llm_client=llm_client),
        "conformance": ConformanceAgent(
            pal_spec,
            llm_client=llm_client,
            always_call_llm=os.getenv("CONFORMANCE_ALWAYS_LLM", "1").strip().lower()
            not in {"0", "false", "no"},
        ),
    }

    teacher = AgenticTeacherLoop(agents)
    result = teacher.generate_bt(
        instruction=args.instruction,
        contact_sheet_path=args.contact_sheet,
    )

    print("verdict:", result["verdict"])
    print("score:", result["score"])
    print("audit_log_len:", len(result["audit_log"]))
    print("bt_xml:", result["bt_xml"])


if __name__ == "__main__":
    main()
