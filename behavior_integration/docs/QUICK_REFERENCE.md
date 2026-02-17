# ⚡ BEHAVIOR-1K Integration - Quick Reference (post-refactor)

## 🚀 Fast Path (recommended): VLM server + continuous pipeline

Terminal 1 (VLM):
```bash
conda activate behavior
cd /home/cristiano/oxe-bt-pipeline
python3 behavior_integration/scripts/vlm_server.py --model qwen --port 7860
```

Terminal 2 (simulation):
```bash
python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --scene house_single_floor \
  --robot Tiago \
  --task bringing_water \
  --instruction "bring water to the coffee table" \
  --colab-url http://127.0.0.1:7860 \
  --symbolic
```

Artifacts:
- `debug_images/` (screenshots + BT xml)
- `debug_logs/` (session log + `results_*.json`)

## 🧭 Batch mode

```bash
cat > tasks.txt <<'EOF'
bring water to the coffee table | bringing_water | 3
clean the carpets | cleaning_carpets | 2
EOF

python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --scene house_single_floor \
  --robot Tiago \
  --batch tasks.txt \
  --colab-url http://127.0.0.1:7860 \
  --symbolic
```

## 🎛️ Interactive control (menu)

```bash
python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --scene house_single_floor \
  --robot Tiago \
  --task bringing_water \
  --colab-url http://127.0.0.1:7860 \
  --symbolic \
  --interactive-control
```

## ✅ Pre-Run Checklist

- [ ] `conda activate behavior`
- [ ] VLM server running (port 7860/7861)
- [ ] Correct `--colab-url` (use `http://127.0.0.1:7860` for local)
- [ ] Using Fetch robot? Consider `--symbolic`
- [ ] Want extra views? Add `--multi-view`

## 🎓 BEHAVIOR-1K tasks list

```bash
ls /home/cristiano/BEHAVIOR-1K/datasets/2025-challenge-task-instances/house_single_floor/
```

## 📚 More info

- Full guide: `README_USAGE.md`
- Root docs: `../../docs/BEHAVIOR1K_INTEGRATION.md`, `../../docs/VLM_SERVER_E_PIPELINE_CONTINUA.md`
