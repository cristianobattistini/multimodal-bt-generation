# BEHAVIOR-1K Integration

Integration layer for executing VLM-generated Behavior Trees in BEHAVIOR-1K simulation.

This folder is now a **Python package** (`behavior_integration/`) split into small modules
(camera / env / episode runner / BT execution / UI / VLM client glue). The CLI entrypoints
live in `behavior_integration/scripts/` and mostly orchestrate these modules.

## 🌟 Main Scripts

### `scripts/run_continuous_pipeline.py`
Persistent OmniGibson session that runs multiple episodes without restarting Isaac/OmniGibson.
Supports batch mode, interactive prompt mode, and interactive control mode.

```bash
python3 behavior_integration/scripts/run_continuous_pipeline.py \
    --scene house_single_floor \
    --robot Tiago \
    --task bringing_water \
    --instruction "bring water to the coffee table" \
    --colab-url http://127.0.0.1:7860 \
    --symbolic
```

### `scripts/vlm_server.py`
Gradio server for generating **State Analysis + BehaviorTree.CPP XML** from an image + instruction.

```bash
python3 behavior_integration/scripts/vlm_server.py --model qwen --port 7860
```

### `scripts/run_bt_agent.py`
Complete VLM → BT → Simulation pipeline with GUI visualization.

```bash
python3 behavior_integration/scripts/run_bt_agent.py \
    --instruction "bring me the water" \
    --task bringing_water \
    --scene house_single_floor \
    --show-window \
    --symbolic
```

### `scripts/run_bt_agent_pipeline.py`
Shared helpers used by the scripts and modules (Gradio VLM client, object-name mapping, camera observation extraction).

## 📚 Documentation

- **docs/USAGE.md** - Detailed usage guide
- **docs/QUICK_REFERENCE.md** - Common commands
- **Root docs**: `docs/BEHAVIOR1K_INTEGRATION.md` and `docs/VLM_SERVER_E_PIPELINE_CONTINUA.md`

## ✅ Status

Production ready! Complete pipeline operational.
