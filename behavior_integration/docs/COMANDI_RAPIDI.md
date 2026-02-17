# ⚡ Comandi Rapidi (post-refactor)

## 🚀 Percorso consigliato: VLM server + pipeline persistente

Terminale 1 (VLM):
```bash
conda activate behavior
cd /home/cristiano/oxe-bt-pipeline
python3 behavior_integration/scripts/vlm_server.py --model qwen --port 7860
```

Terminale 2 (simulazione):
```bash
python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --scene house_single_floor \
  --robot Tiago \
  --task bringing_water \
  --instruction "bring me the water" \
  --colab-url http://127.0.0.1:7860 \
  --symbolic
```

Output:
- `debug_images/` (screenshot + BT xml)
- `debug_logs/` (log sessione + `results_*.json`)

## 🧾 Batch (file tasks)

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

## 📁 File importanti

| File | Descrizione |
|------|-------------|
| `behavior_integration/scripts/run_continuous_pipeline.py` | Orchestratore pipeline persistente |
| `behavior_integration/scripts/vlm_server.py` | Server Gradio BT generator |
| `behavior_integration/pipeline/` | Env manager + episode runner + BT executor wrapper |
| `behavior_integration/camera/` | Camera + rendering + capture |
| `behavior_integration/ui/` | Batch / interactive / control |
| `behavior_integration/vlm/` | Client VLM + mapping mode |

## 🔍 Debug rapido

```bash
# Log completo
python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --scene house_single_floor \
  --robot Tiago \
  --instruction "bring water" \
  --colab-url http://127.0.0.1:7860 \
  --symbolic \
  2>&1 | tee execution.log

# Ultimi risultati
ls -1t debug_logs/results_*.json | head -n 1
ls -1t debug_images | head -n 20
```

## ✅ Checklist

- [ ] `conda activate behavior`
- [ ] VLM server avviato (`vlm_server.py`)
- [ ] `--colab-url` corretto (`http://127.0.0.1:7860` in locale)
- [ ] Con Fetch → valuta `--symbolic`

## 🎓 Task BEHAVIOR-1K

```bash
ls /home/cristiano/BEHAVIOR-1K/datasets/2025-challenge-task-instances/house_single_floor/
```
- `cleaning_oven`
- `cleaning_shoes`

## 💾 Backup LoRA

```bash
# Backup LoRA models (NON su GitHub)
tar -czf ~/gemma3_lora_backup_$(date +%Y%m%d).tar.gz \
    /home/cristiano/lora_models/gemma3_4b_vision_bt_lora_08012026/
```

## 🔄 Git Operations

```bash
cd /home/cristiano/oxe-bt-pipeline

# Status
git status
git log --oneline -10

# Push modifiche
git add .
git commit -m "Your message"
git push origin lion
```
