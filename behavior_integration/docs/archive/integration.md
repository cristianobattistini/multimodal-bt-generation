# BEHAVIOR-1K ↔ OXE-BT Pipeline ↔ (Embodied) BT Brain — Project Notes

This document summarizes the current situation and the intended direction after the recent discussion.

The key change: instead of managing **`embodied-bt-brain`** as a separate repository, we may integrate it as a **module/folder inside the existing OXE-BT pipeline project** (a monorepo approach). The goal remains the same: run tasks in **BEHAVIOR‑1K / OmniGibson**, execute **Behavior Trees**, and collect traces to train a **runtime validator**.

---

## 1) What exists today

### 1.1 OXE-BT pipeline (your current work)
You already have a working pipeline (see `doc.md` in your project) that covers:
- exporting episodes (OXE → frames / contact sheets / videos)
- producing teacher BTs (offline)
- building a dataset for training a **BT proposer**
- training the proposer (VLM).

What is missing:
- a simulation runner that executes BTs in OmniGibson / BEHAVIOR‑1K
- execution logging (tick traces, node failures)
- dataset construction and training for a **runtime validator**.

### 1.2 BEHAVIOR‑1K repository (what it contains)
The folder `BEHAVIOR-1K/` is a **monolithic simulator + assets repo**. It contains:

- `OmniGibson/`: the simulator codebase and learning scripts
- `datasets/`:
  - `behavior-1k-assets/`: object assets (USD, metadata, etc.)
  - `omnigibson-robot-assets/`: robot assets
  - `2025-challenge-task-instances/`: task instance metadata and sampled scenes
  - **does NOT include large “complete episodes” by default**
- `docs/`: documentation, examples, tutorials
- `joylo/`: task definitions / sampled tasks and related tooling
- `bddl3/`: task specification language components

### 1.3 Why you did not find “complete episodes” locally
Complete demonstrations / rollouts are **too large to ship inside the repo** (often TB-scale). They are hosted externally (e.g., HuggingFace) and must be downloaded when needed.

You successfully verified this workflow by downloading and replaying an episode (e.g., “turning on radio”) and generating videos.

---

## 2) How to “use” BEHAVIOR‑1K effectively

### 2.1 Environment (conda) expectations
Your supervisor mentioned everything is inside a conda environment named `behavior`.

Typical workflow:
```bash
conda activate behavior
python -c "import omnigibson as og; print('ok', og.__version__)"
```

### 2.2 Data path
OmniGibson uses `gm.DATA_PATH` and can be overridden via:

```bash
export OMNIGIBSON_DATA_PATH=/home/cristiano/BEHAVIOR-1K/datasets
```

This must point to a folder that contains `behavior-1k-assets/` and robot assets.

### 2.3 What you can run immediately
- Scene browsing:
  - `python -m omnigibson.examples.scenes.scene_selector`
- BEHAVIOR task demo (live sim):
  - `python -m omnigibson.examples.environments.behavior_env_demo`
- Navigation demo:
  - `python -m omnigibson.examples.environments.navigation_env_demo`

Important note: some examples are **teleoperation** (robot will not move unless you provide keyboard input). Others depend on **cuRobo** (which may fail to build in your current environment).

### 2.4 “Complete episodes”: replay + videos
To view complete demos:
- download a single `.hdf5` from the external dataset
- run `OmniGibson/scripts/learning/replay_obs.py` to generate videos

This is the best way to quickly see “full task executions” without building your own agent yet.

---

## 3) New direction: integrate BT runtime + validator into your existing project

Instead of maintaining a second repo, we can treat “embodied-bt-brain” as a **new folder/module inside your OXE-BT pipeline project**.

### 3.1 Suggested monorepo layout
Example:

```
oxe-bt-pipeline/
  processing/               # existing
  nb/                       # existing
  data/                     # existing (not in git)
  prompts/                  # existing
  docs/ or doc/             # existing notes

  embodied_bt_brain/        # NEW: simulation + runtime execution
    src/
      proposer/
      validator/
      bt_runtime/
      og_adapter/
    configs/
    scripts/
    doc/
```

Key principle:
- your project repo contains **only your code + configs + docs**
- BEHAVIOR‑1K remains a separate dependency located at `/home/cristiano/BEHAVIOR-1K`

This keeps the monorepo clean while avoiding a second GitHub repository.

### 3.2 How the two codebases interact
- Your repo (`oxe-bt-pipeline`) owns:
  - BT proposer and training
  - BT validator and training
  - BT runtime + logging
  - dataset generation for proposer/validator

- BEHAVIOR‑1K owns:
  - the simulator (OmniGibson)
  - assets and scenes
  - replay tooling

Your code should *import and call OmniGibson*, but should not require editing BEHAVIOR‑1K unless absolutely necessary.

---

## 4) Behavior Tree runtime: execution vs representation

### 4.1 Do we “need BT.CPP” at runtime?
Conceptually, yes: we need a **Behavior Tree**.
Practically, the runtime can be:
- a Python interpreter that parses a BT.CPP-like XML subset (Sequence/Fallback/Retry + Action/Condition)
- or a full BT.CPP runtime (harder to integrate).

Given current constraints and the goal to iterate fast, a **Python BT executor** is a pragmatic first step.

### 4.2 XML-only vs “structured internal representation”
Final artifact should be **BT.CPP XML**.
However, even in an XML-only approach you still want:
- stable node instance identifiers
- a strict whitelist of allowed nodes and parameters
- a robust patch mechanism

Recommendation (still XML-first):
- generate **BT.CPP XML**
- parse it once into an internal tree (AST)
- apply validator patches to that tree
- re-serialize to XML when saving/logging.

This does not mean “converting constantly”; it is normal runtime behavior.

### 4.3 Stable node IDs in XML
You can embed stable IDs directly in XML using `name` (instance id) and `ID` (node type).

Example:
```xml
<Sequence name="n0">
  <Action ID="Search" name="n1" target="radio"/>
  <Action ID="NavigateTo" name="n2" target="radio" dist="0.8"/>
  <Action ID="ToggleOn" name="n3" target="radio"/>
</Sequence>
```

The validator can patch: “change attributes of node `n3`” or “insert a recovery subtree after `n2`”.

---

## 5) PAL: a compatibility layer for large-scale primitive support

**PAL (Primitive Abstraction Layer)** is a project-side definition of a finite set of leaf actions.

It is not a replacement for BEHAVIOR‑1K primitives; it is an *interface* that you map to whatever OmniGibson can execute.

Why it matters:
- prevents the proposer from inventing actions
- lets you validate BTs before running them
- standardizes runtime errors (useful for training the validator)

### 5.1 How many primitives?
To be “as compatible as possible with BEHAVIOR‑1K” without collapsing under complexity:

- Start with a **core set (~15–20)** that covers navigation + common interactions:
  - `Search`, `LookAt`, `NavigateTo`
  - `Open`, `Close`, `ToggleOn`, `ToggleOff`, `Press`
  - `Pick`, `PlaceOn`, `PlaceIn`, `Release`
  - `Wait`, `Retry`, `Check`

- Then expand toward a larger set (~30–35) aligned with BEHAVIOR skills (pour/spray/wipe/sweep/chop etc.).

---

## 6) Known obstacles and risks

- Some OmniGibson “automatic” examples depend on **cuRobo** and currently fail to build in your environment.
- Some demos are teleop (no movement unless you provide keyboard actions).
- We observed occasional crashes related to robot articulation initialization in certain configs.

These issues reinforce the value of:
- using replayed episodes to inspect behavior
- building a minimal runtime first (even with partial/heuristic primitives)
- collecting traces/errors early.

---

## 7) Concrete next goals

1) Decide a **PAL v1** (list of allowed actions + parameters)
2) Decide the **BT XML conventions** (required attributes, node ID policy)
3) Implement a **Python BT executor** (tick loop) + logger
4) Implement a **simulation runner** that:
   - loads a BEHAVIOR task
   - runs proposer → BT
   - executes BT + logs failures
5) Define and generate a **validator dataset** from traces

---

## 8) What you can do right now in BEHAVIOR‑1K

- Explore tasks/scenes:
  - `python -m omnigibson.examples.scenes.scene_selector`
- Watch complete demos via replay:
  - download one `episode_XXXXXXXX.hdf5`
  - run `OmniGibson/scripts/learning/replay_obs.py --rgbd`

This provides reference trajectories and “what success looks like” while we build the agentic pipeline.

