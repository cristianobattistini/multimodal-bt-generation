ROLE: BT Repair (BehaviorTree.CPP v3)
GOAL: Transform the Naive XML into the final robust + modular BT XML (SubTrees allowed).

INPUTS:
- Instruction: {instruction}
- Image: Frame 0 only
- Naive XML (may be imperfect):
{naive_xml}
- Allowed Actions for THIS sample (k-of-N): {actions}

OUTPUT:
- Return ONLY the full XML (no markdown / no fences / no extra text).

HARD RULES (do not break):
- Allowed tags: root, BehaviorTree, Sequence, Fallback, RetryUntilSuccessful, Timeout, SubTree, Action.
- Forbidden tags: any other tags. No `<input .../>`.
- root@main_tree_to_execute MUST equal the ID of the FIRST <BehaviorTree>.
- Each <BehaviorTree> MUST have exactly ONE root child node.
- RELEASE has NO parameters; every other Action has exactly `obj="..."`.
- Use ONLY the Allowed Actions list above (no extra primitives):
  - If Naive XML contains an Action ID not in the list, remove it or replace it with an allowed equivalent while preserving intent.
- Object names in `obj/target` MUST be snake_case.

PARAMETER SEMANTICS (critical):
- Use the placeholders in `{subtrees}`:
  - If a SubTree line uses `target="X"`, then `X` is the object to act on.
  - If a SubTree line uses `target="DEST"`, then `DEST` is the DESTINATION (where to place/pour).
- The held object is implicit (most recent GRASP in the MainTree).

MODULARITY:
- Keep the XML structure consistent and minimal; do not invent new tags.

ROBUSTNESS (keep it simple):
- Macro-order:
  - If NAVIGATE_TO is in `{actions}`, navigate before manipulation.
  - If GRASP is in `{actions}`, GRASP before any `DEST` action and before RELEASE.
  - If OPEN and PLACE_INSIDE are both in `{actions}`, OPEN before PLACE_INSIDE.
- Add bounded retries/timeouts:
  - NAVIGATE_TO: Timeout 5000-15000 (+ optional Retry 2-3).
  - `X` actions: Retry 3.
  - `DEST` actions: Retry 2.
- Use <Fallback> ONLY for real recovery (different actions/order). If both branches do the same action, collapse to a single RetryUntilSuccessful.

Return the full corrected XML (MainTree + referenced subtree definitions).
