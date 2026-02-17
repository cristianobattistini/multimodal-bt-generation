# Agentic Teacher - System Design Documentation

## Overview

The **Agentic Teacher** is a streamlined pipeline that generates simple, linear Behavior Tree (BT) XML from robot task instructions and visual observations. The system uses three agents to produce sequential BTs without complex constructs.

**Key Design Principle**: Generate simple linear BTs (Sequence + Action nodes only). No Retry, Fallback, Timeout, or SubTree constructs. This avoids the bias problem where models learn to ALWAYS use complex constructs even for simple tasks.

## System Architecture

```
Instruction + Contact Sheet (9 frames)
           ↓
   [Scene Analysis Agent]        (extracts scene_analysis YAML)
           ↓
     [Architect Agent]           (generates linear BT XML)
           ↓
   [Conformance Agent]           (validates PAL v1 compliance)
           ↓
    [Final Validator]            (hard XML + PAL check)
           ↓
  Linear BT XML + Audit Log + Verdict (ACCEPT/REJECT)
```

---

## Pipeline Execution Flow

The `AgenticTeacherLoop` orchestrates:

1. **Scene Analysis**: Extract target, destination, scene context, expected sequence
2. **Architect**: Generate linear BT using verb-to-primitive mapping
3. **Conformance**: Validate PAL v1 primitives
4. **Final Validation**: Hard XML syntax + PAL compliance check

---

## Agent Specifications

### 1. Scene Analysis Agent

**Purpose**: Analyze the scene and produce structured planning context for the Architect.

**Inputs**:
- `instruction` (str): Natural language task description
- `contact_sheet_path` (str): Path to 3x3 contact sheet (9 frames)

**Processing**:
- Uses LLM with vision (multimodal)
- Prompt: `prompts/scene_analysis.md`
- Temperature: 0.2
- Max tokens: 900

**Output** (str): **Structured Scene Analysis (YAML)**:
```yaml
scene_analysis:
  target: "7up_can"                    # string or array of strings
  destination: ""
  expanded_instruction: "Pick up the 7up can from the bottom shelf inside the fridge"
  scene_context: "Fridge is closed. 7up can on bottom shelf inside."
  expected_sequence: "First open the fridge door, then reach inside and grasp the can"
```

**Field Semantics**:
- `target`: Main object(s) to manipulate (string or array of strings, snake_case)
- `destination`: Where to place/put object (snake_case or empty)
- `expanded_instruction`: Original instruction with concrete scene details
- `scene_context`: INITIAL state observations (container states, object positions)
- `expected_sequence`: Natural language plan (Chain-of-Thought for student model)

**Length Guideline**: scene_context and expected_sequence should be proportional to task complexity.

**Audit Log Entry**:
```json
{
  "agent": "SceneAnalysis",
  "status": "ok",
  "used_llm": true,
  "chars": 245
}
```

---

### 2. Architect Agent

**Purpose**: Generate a simple, linear BT from instruction and scene analysis.

**Inputs**:
- `instruction` (str): Natural language task description
- `contact_sheet_path` (str): Path to 3x3 contact sheet
- `scene_analysis` (str): YAML output from Scene Analysis Agent

**Processing**:
- Uses LLM with vision (multimodal)
- Prompt: `prompts/architect.md`
- Temperature: 0.7
- Max tokens: 2000

**Critical Rules**:
1. Output ONLY `<Sequence>` with `<Action>` nodes
2. **NO Fallback, NO RetryUntilSuccessful, NO Timeout, NO SubTree**
3. Each Action MUST have an XML comment above it
4. Use verb-to-primitive mapping from prompt

**Output** (str): Linear BT XML
```xml
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <!-- Navigate to fridge -->
      <Action ID="NAVIGATE_TO" obj="fridge"/>
      <!-- Open fridge -->
      <Action ID="OPEN" obj="fridge"/>
      <!-- Navigate to 7up_can -->
      <Action ID="NAVIGATE_TO" obj="7up_can"/>
      <!-- Grasp 7up_can -->
      <Action ID="GRASP" obj="7up_can"/>
    </Sequence>
  </BehaviorTree>
</root>
```

**Audit Log Entry**:
```json
{
  "agent": "Architect",
  "status": "ok",
  "used_llm": true
}
```

---

### 3. Conformance Agent

**Purpose**: Validate PAL v1 primitive compliance.

**Inputs**:
- `bt_xml` (str): XML from Architect Agent

**Processing**:
- Uses LLM (text-only) with repair prompt if needed
- Prompt: `prompts/conformance.md`
- Checks against PAL v1 specification

**Output** (str): PAL-compliant BT XML (may be repaired)

**Audit Log Entry**:
```json
{
  "agent": "Conformance",
  "status": "ok"|"repaired",
  "issues_found": 0,
  "issues_fixed": 0,
  "remaining_issues": [],
  "used_llm": true
}
```

---

### 4. Final Validator

**Purpose**: Hard syntactic and semantic validation (final gatekeeper).

**Processing**:
- Pure validation (no LLM)
- XML syntax check via `ET.fromstring()`
- PAL v1 compliance check via `validate_bt_xml()`

**Behavior**:
- If validation fails → episode is **REJECTED**
- If validation passes → episode is **ACCEPTED** (score 1.0)

**Audit Log Entry**:
```json
{
  "agent": "FinalValidator",
  "status": "ok"|"error",
  "issues": []
}
```

---

## Final Output

The `AgenticTeacherLoop.generate_bt()` method returns:

```python
{
  "bt_xml": "<root>...</root>",          # Final linear BT XML
  "audit_log": [...],                     # List of all agent logs
  "score": 1.0,                           # Binary: 1.0 if passed, 0 if rejected
  "verdict": "ACCEPT"|"REJECT",           # ACCEPT if passed FinalValidator
  "steps": [...]                          # Intermediate outputs (if record_steps=True)
}
```

### Steps Array (if `record_steps=True`):
```python
[
  {
    "agent": "scene_analysis",
    "content": "scene_analysis:\n  target: ...",
    "ext": "txt"
  },
  {
    "agent": "architect",
    "bt_xml": "<root>...</root>",
    "type": "baseline"
  },
  {
    "agent": "conformance",
    "bt_xml": "<root>...</root>"
  }
]
```

---

## PAL v1 Primitives

All generated BTs must use ONLY these primitives:

### Category A - obj = object being acted upon

| Primitive | Description |
|-----------|-------------|
| `NAVIGATE_TO(obj)` | Move to obj |
| `GRASP(obj)` | Grasp obj |
| `OPEN(obj)` | Open obj (door, drawer, lid) |
| `CLOSE(obj)` | Close obj |
| `TOGGLE_ON(obj)` | Turn on obj |
| `TOGGLE_OFF(obj)` | Turn off obj |
| `PUSH(obj)` | Push obj |
| `FOLD(obj)` | Fold obj |
| `UNFOLD(obj)` | Unfold obj |
| `WIPE(obj)` | Wipe/clean obj |
| `CUT(obj)` | Cut obj |
| `SOAK_UNDER(obj)` | Soak obj under running water |
| `SOAK_INSIDE(obj)` | Soak obj inside container |
| `SCREW(obj)` | Screw obj |
| `FLIP(obj)` | Flip obj upright |

### Category B - obj = DESTINATION (not the held object)

| Primitive | Description |
|-----------|-------------|
| `PLACE_ON_TOP(obj)` | Place held object ON obj (surface) |
| `PLACE_INSIDE(obj)` | Place held object INSIDE obj (container) |
| `PLACE_NEAR_HEATING_ELEMENT(obj)` | Place held object near obj |
| `POUR(obj)` | Pour into obj (destination container) |
| `HANG(obj)` | Hang held object on obj (hook/rack) |

### No Parameter

| Primitive | Description |
|-----------|-------------|
| `RELEASE` | Release currently held object |

---

## Verb Synonym Groups

The Architect uses semantic verb groupings instead of rigid pattern matching:

| Family | Verbs | Maps to |
|--------|-------|---------|
| **GRASP** | pick, pick up, grab, grasp, hold, raise, lift, take, get, fetch, collect | NAVIGATE_TO → GRASP |
| **PUSH** | push, slide, sweep (with direction), knock, shove, move (no destination) | NAVIGATE_TO → PUSH |
| **PLACE** | put, place, set, lay, insert, store | GRASP → NAVIGATE_TO → PLACE_* → RELEASE |
| **OPEN** | open, pull open, lift open | NAVIGATE_TO → OPEN |
| **TOGGLE** | turn on/off, switch on/off, activate, press | NAVIGATE_TO → TOGGLE_* |
| **WIPE** | wipe, clean, swipe, sweep (surface) | NAVIGATE_TO → WIPE |
| **FLIP** | flip upright, upright | NAVIGATE_TO → FLIP |

### Context-Dependent Verbs

| Verb | Context | Primitive |
|------|---------|-----------|
| "sweep" | with direction ("to Y") | PUSH |
| "sweep" | surface, no direction | WIPE |
| "move" | with destination | GRASP + PLACE sequence |
| "move" | no destination | PUSH |
| "lift" | object | GRASP |
| "lift" | "lift open" (lid) | OPEN |

### Special Cases (from scene_context)

- If container is "closed" and task requires accessing inside → Add OPEN before GRASP
- If object is already held → Skip NAVIGATE_TO and GRASP
- PUSH tasks → NO GRASP, NO RELEASE (push without lifting)

---

## Logical Dependencies (Mandatory)

- NAVIGATE_TO before any manipulation (GRASP, OPEN, PUSH, TOGGLE, etc.)
- GRASP before PLACE_*, POUR, HANG, RELEASE
- OPEN before accessing contents inside closed container
- RELEASE only at end, only if GRASP was used

---

## Configuration

### Agent Setup

```python
from embodied_bt_brain.agentic_teacher import AgenticTeacherLoop
from embodied_bt_brain.agentic_teacher.agents import (
    SceneAnalysisAgent,
    ArchitectAgent,
    ConformanceAgent,
)
from embodied_bt_brain.agentic_teacher.llm_client import LLMClient

llm_client = LLMClient()

agents = {
    "scene_analysis": SceneAnalysisAgent(enabled=True, llm_client=llm_client),
    "architect": ArchitectAgent(llm_client),
    "conformance": ConformanceAgent(enabled=True, llm_client=llm_client),
}

loop = AgenticTeacherLoop(agents)

result = loop.generate_bt(
    instruction="pick up the apple",
    contact_sheet_path="/path/to/contact_sheet.jpg",
    record_steps=True,
)
```

---

## Example Execution Trace

**Input**:
- Instruction: `"put the apple on the table"`
- Contact sheet: 9 frames showing apple on counter, table nearby

**Execution**:

1. **Scene Analysis**:
   ```yaml
   scene_analysis:
     target: "apple"
     destination: "table"
     expanded_instruction: "Pick up the red apple from the counter and place it on the wooden table"
     scene_context: "Apple on counter near sink. Table is clear and accessible."
     expected_sequence: "Grasp the apple from the counter, move to the table, and place it down"
   ```

2. **Architect**: Generates linear BT
   ```xml
   <root main_tree_to_execute="MainTree">
     <BehaviorTree ID="MainTree">
       <Sequence>
         <!-- Navigate to apple -->
         <Action ID="NAVIGATE_TO" obj="apple"/>
         <!-- Grasp apple -->
         <Action ID="GRASP" obj="apple"/>
         <!-- Navigate to table -->
         <Action ID="NAVIGATE_TO" obj="table"/>
         <!-- Place on table -->
         <Action ID="PLACE_ON_TOP" obj="table"/>
         <!-- Release -->
         <Action ID="RELEASE"/>
       </Sequence>
     </BehaviorTree>
   </root>
   ```

3. **Conformance**: No issues found

4. **Final Validator**: ✓ Valid XML and PAL v1 → **ACCEPT (score 1.0)**

---

## Anti-Leakage Rule

**Critical constraint** for training data:

- **Teacher** sees all 9 frames to understand what happens (ground truth)
- **Student** (trained model) sees ONLY Frame 0 and must generate the plan
- `scene_context` describes ONLY the INITIAL state (no future actions)
- `expected_sequence` provides Chain-of-Thought reasoning for student to learn

This ensures the model learns to plan from initial observations, not by "cheating" from future frames.

---

## Error Handling

### Validation Errors
- Any agent can raise `ValueError` if output is invalid
- Pipeline aborts for that episode
- Error is logged in audit log

### LLM Failures
- Each agent uses `llm_client.complete_with_fallback()`
- Automatic retry with fallback models if primary fails
- Configurable retry logic in `LLMClient`

### Pipeline Error
```python
class TeacherPipelineError(Exception):
    """Raised when an agent fails, carrying partial artifacts."""
    agent: str           # Which agent failed
    original_exc: Exception
    steps: List[dict]    # Partial steps for debugging
    audit_log: List[dict]
    bt_xml: str          # Partial BT (if any)
```

---

## Quick Reference: Agent I/O Summary

| Agent | Input | Output | Format | LLM? |
|-------|-------|--------|--------|------|
| Scene Analysis | instruction, contact_sheet | scene_analysis YAML | YAML | ✓ (vision) |
| Architect | instruction, contact_sheet, scene_analysis | linear BT | XML | ✓ (vision) |
| Conformance | BT XML | PAL-compliant BT | XML | ✓ (text) |
| Final Validator | BT XML | ACCEPT (1.0) or REJECT (0) | - | ✗ |

---

## Related Files

| File | Description |
|------|-------------|
| `teacher_loop.py` | Main orchestration logic |
| `agents/scene_analysis.py` | Scene Analysis Agent |
| `agents/architect.py` | Architect Agent |
| `agents/conformance.py` | Conformance Agent |
| `agents/instruction_filter.py` | Filters problematic instructions |
| `prompts/scene_analysis.md` | Prompt for Scene Analysis |
| `prompts/architect.md` | Prompt for Architect |
| `prompts/conformance.md` | Prompt for Conformance |
| `llm_client.py` | OpenAI client + retry/backoff |
| `augmentation/bt_augmenter.py` | Granular BT augmentation (future) |
| `augmentation/bt_postprocessor.py` | Dataset entry creation |

---

## Version History

- **v3.1** (Current): Enhanced prompts and FLIP primitive
  - **New primitive**: FLIP for "flip upright" tasks
  - **target**: Now supports string OR array for multi-object tasks
  - **Prompts**: Verb Synonym Groups (semantic) instead of rigid Verb-to-Primitive table
  - **Length guideline**: scene_context/expected_sequence proportional to task complexity

- **v3.0**: LINEAR pipeline for simple BTs
  - **Removed**: RobustnessAgent, RecoveryPlannerAgent, SubtreeEnablementAgent
  - **Output**: ONLY linear BTs (Sequence + Action nodes)
  - **New schema**: Simplified scene_analysis with CoT (expected_sequence)
  - **Prompts**: Verb-to-Primitive mapping, Self-Check, Category A/B semantics
  - **Reason**: Avoid bias where models always use complex constructs

- **v2.0**: Simplified pipeline with deterministic validation
  - Removed Scorer Agent (LLM-based quality scoring)
  - Binary verdict: ACCEPT if passes FinalValidator

- **v1.0**: Initial pipeline with 6 agents
  - SceneAnalysis, Architect, Robustness, RecoveryPlanner, SubtreeEnablement, Conformance
  - Automatic retry/fallback/subtree insertion
