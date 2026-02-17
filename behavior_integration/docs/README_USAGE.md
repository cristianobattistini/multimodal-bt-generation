# 🤖 OXE-BT-Pipeline - Guida Completa

Sistema completo per generare Behavior Trees con VLM e eseguirli in BEHAVIOR-1K simulation.

> Aggiornamento (refactoring): la cartella `behavior_integration/` è stata spezzata in un vero **package Python**
> (camera / pipeline / ui / vlm / utils). Gli entrypoint CLI stanno in `behavior_integration/scripts/`.
> Alcuni vecchi script monolitici (`run_bt_collect_failures.py`, `run_bt_simple.py`, `generate_bt_only.py`) non sono più
> presenti come CLI: per test mirati usa `behavior_integration/examples/` oppure la `SimulationHarness` in
> `embodied_bt_brain/runtime/`.

## 📁 Struttura del Progetto

```
oxe-bt-pipeline/
├── behavior_integration/                     # 📦 Package: integrazione BEHAVIOR-1K
│   ├── scripts/
│   │   ├── run_continuous_pipeline.py        # 🌟 Pipeline persistente (multi-episodio)
│   │   ├── vlm_server.py                     # 🌟 Server Gradio: immagine+istruzione → BT
│   │   ├── run_bt_agent.py                   # Alternativa: VLM in-process + esecuzione singola
│   │   └── run_bt_agent_pipeline.py          # Helper: client Gradio + mapping + camera obs
│   ├── pipeline/                             # EnvironmentManager / EpisodeRunner / BTExecutor
│   ├── camera/                               # CameraController / ImageCapture / RTX presets
│   ├── vlm/                                  # BTGenerator (client) + mapping mode
│   ├── ui/                                   # batch / interactive / interactive control
│   ├── utils/                                # logging
│   └── examples/                             # script di test (sim-only, vlm-only, ecc.)
└── embodied_bt_brain/runtime/                # Runtime BT + bridge primitive + harness/validator
```

## 🚀 Quick Start

### 1. Setup Ambiente

```bash
# Attiva l'ambiente behavior (include tutto: OmniGibson + VLM)
conda activate behavior
cd /home/cristiano/oxe-bt-pipeline
```

### 2. Avvia il VLM server (in un terminale separato)

```bash
python3 behavior_integration/scripts/vlm_server.py --model qwen --port 7860
```

### 3. Esegui il sistema completo (pipeline persistente)

```bash
python3 behavior_integration/scripts/run_continuous_pipeline.py \
    --scene house_single_floor \
    --robot Tiago \
    --task bringing_water \
    --instruction "bring water to the coffee table" \
    --colab-url http://127.0.0.1:7860 \
    --symbolic
```

**Output principale:**
- `debug_images/`: screenshot, BT, BT mappato, success/failure
- `debug_logs/`: log sessione + `results_*.json`

### (Opzionale) Modalità interactive control (menu)

```bash
python3 behavior_integration/scripts/run_continuous_pipeline.py \
    --scene house_single_floor \
    --robot Tiago \
    --task bringing_water \
    --colab-url http://127.0.0.1:7860 \
    --symbolic \
    --interactive-control
```

## 📝 Parametri Principali

### `run_continuous_pipeline.py` (consigliato)

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `--instruction` / `--batch` | - | Sorgente episodi (singolo o file tasks) |
| `--colab-url` | **required** | URL Gradio del VLM server (anche locale) |
| `--scene` | `house_single_floor` | Scena OmniGibson |
| `--task` | `bringing_water` | Task BEHAVIOR-1K (activity_name) |
| `--robot` | `Tiago` | Robot (Tiago/R1/Fetch) |
| `--symbolic` | `False` | Primitive simboliche (più stabili/veloci) |
| `--headless` | `False` | Esecuzione senza viewer |
| `--interactive-control` | `False` | Menu per camera/screenshot/BT/exec |
| `--head-pan` | `1.57` | Orientamento camera (pan) |
| `--head-tilt` | `0.0` | Orientamento camera (tilt) |
| `--render-quality` | `fast` | Preset RTX (turbo/fast/balanced/high) |
| `--multi-view` | `False` | Salva viste extra (birds_eye/side_view/viewer) |

### `run_bt_agent.py` (alternativa: VLM in-process)

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `--instruction` | **required** | Descrizione task in linguaggio naturale |
| `--task` | `bringing_water` | Task BEHAVIOR-1K |
| `--scene` | `house_single_floor` | Scena 3D |
| `--robot` | `Fetch` | Tipo robot (Fetch, Tiago, R1) |
| `--lora` | `/home/cristiano/lora_models/gemma3_4b_vision_bt_lora_08012026` | Path LoRA adapter |
| `--model` | `gemma3-4b` | VLM model (gemma3-4b, qwen25-vl-3b) |
| `--symbolic` | `False` | Usa primitive simboliche (raccomandato con Fetch) |
| `--show-window` | `False` | Mostra GUI OmniGibson |
| `--max-ticks` | `1000` | Max iterazioni BT |
| `--temperature` | `0.3` | Temperature VLM |

### Task BEHAVIOR-1K Disponibili

Esempi da `/home/cristiano/BEHAVIOR-1K/datasets/2025-challenge-task-instances/house_single_floor/`:

```bash
# Visualizza tutti i task disponibili
ls /home/cristiano/BEHAVIOR-1K/datasets/2025-challenge-task-instances/house_single_floor/
```

Alcuni task comuni:
- `bringing_water` - Portare acqua
- `canning_food` - Inscatolare cibo
- `cleaning_carpets` - Pulire tappeti
- `cleaning_freezer` - Pulire freezer
- `cleaning_oven` - Pulire forno
- `cleaning_shoes` - Pulire scarpe
- `cleaning_stove` - Pulire fornelli

## 🎯 Raccolta Dataset per Validator

Il refactoring ha rimosso l’entrypoint `run_bt_collect_failures.py`. Per raccolta dati “validator-style” ci sono due opzioni:

### Opzione A (consigliata): `SimulationHarness` + `ValidatorLogger` (in-process)

Usa `embodied_bt_brain/runtime/simulation_harness.py` (API Python) che integra `ValidatorLogger`.

Esempio minimale:

```python
from embodied_bt_brain.runtime import SimulationHarness

h = SimulationHarness(
    vlm_model_type="qwen25-vl-3b",
    vlm_lora_path="/path/to/lora",
    use_symbolic_primitives=True,
    validator_output_dir="validator_dataset",
)

ok = h.run_episode(
    task_name="bringing_water",
    scene_model="house_single_floor",
    activity_definition=0,
    activity_instance=0,
    robot_type="Tiago",
)
print("success:", ok)
```

### Opzione B: usare gli artefatti della pipeline continua

`run_continuous_pipeline.py` salva già per ogni episodio:
- immagini iniziali/finali
- `*_bt.xml` e `*_bt_mapped.xml`
- log + `results_*.json`

Se ti serve un dataset strutturato “validator”, puoi costruirlo offline a partire da `debug_images/` + `debug_logs/`.

## 🔧 Altri Script Utili

Gli script “di test” stanno in `behavior_integration/examples/` (vlm-only, sim-only, full pipeline, ecc.).
Vedi la lista con:

```bash
ls behavior_integration/examples
```

## 📊 Workflow Completo: Proposer → Validator

### Step 1: Raccolta Fallimenti

Esegui il sistema su vari task e raccogli fallimenti:

```bash
# Batch mode dalla pipeline continua (tasks file)
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

### Step 2: Analizza Dataset

```bash
# Risultati sessione (JSON)
ls -1t debug_logs/results_*.json | head -n 1

# Log sessione
ls -1t debug_logs/continuous_session_*.log | head -n 1

# Artefatti episodio (immagini + xml)
ls -1t debug_images | head -n 20
```

### Step 3: Training Validator LoRA

Per un dataset “validator” strutturato e riproducibile, usa l’Opzione A (SimulationHarness + ValidatorLogger) e punta
`validator_output_dir` a una cartella dedicata (es. `validator_dataset/`). La struttura e i metadati sono gestiti da
`embodied_bt_brain/runtime/validator_logger.py`.

## 🔍 Debug e Troubleshooting

### Visualizza log completo

```bash
# Redireziona output a file
python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --scene house_single_floor \
  --robot Tiago \
  --instruction "bring water to the coffee table" \
  --colab-url http://127.0.0.1:7860 \
  --symbolic \
  2>&1 | tee execution.log
```

### OmniGibson non si apre

```bash
# Verifica environment variables
echo $ISAAC_PATH
echo $OMNIGIBSON_DATA_PATH

# Dovrebbero essere:
# ISAAC_PATH=/home/cristiano/isaacsim
# OMNIGIBSON_DATA_PATH=/home/cristiano/BEHAVIOR-1K/datasets
```

### Primitive bridge errors con Fetch

⚠️ `StarterSemanticActionPrimitives` (realistic) funziona solo con **Tiago** e **R1**.

**Soluzione:** Usa `--symbolic` con Fetch:

```bash
python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --robot Fetch \
  --symbolic \
  --colab-url http://127.0.0.1:7860 \
  --instruction "bring water" \
  ...
```

Oppure cambia robot:

```bash
python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --robot Tiago \
  # (opzionale) senza --symbolic per realistic primitives
  --colab-url http://127.0.0.1:7860 \
  --instruction "bring water" \
  ...
```

### BT fallisce subito (tick 1)

Probabilmente il BT cerca oggetti che non esistono nella scena.

**Soluzione:** Allinea instruction al task reale:

```bash
# ❌ MALE - task bringing_water ma instruction parla di apple
python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --instruction "pick up the apple" \
  --task bringing_water \
  --colab-url http://127.0.0.1:7860

# ✅ BENE - instruction allineata al task
python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --instruction "bring me the water" \
  --task bringing_water \
  --colab-url http://127.0.0.1:7860
```

## 🌐 GitHub Repository

Tutti i file sono pushati su:
**https://github.com/tuozaibeibei/oxe-bt-pipeline**

```bash
# Verifica stato git
cd /home/cristiano/oxe-bt-pipeline
git status
git log --oneline -10

# Push nuove modifiche
git add .
git commit -m "Update dataset collection script"
git push origin main
```

## 📦 Files NON su GitHub

**LoRA Models** (troppo grandi):
```bash
/home/cristiano/lora_models/gemma3_4b_vision_bt_lora_08012026/
```

**⚠️ IMPORTANTE:** Fai backup locale dei LoRA models!

```bash
# Backup su disco esterno o cloud
tar -czf gemma3_lora_backup.tar.gz /home/cristiano/lora_models/
```

## 🎓 Esempi Pratici

### Esempio 1: Esecuzione Base

```bash
conda activate behavior
cd /home/cristiano/oxe-bt-pipeline

python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --scene house_single_floor \
  --robot Tiago \
  --task bringing_water \
  --instruction "bring me the water from the kitchen" \
  --colab-url http://127.0.0.1:7860 \
  --symbolic \
  --max-ticks 50
```

### Esempio 2: Raccolta Fallimenti Batch

```bash
# File batch con retry
cat > tasks.txt <<'EOF'
pick random objects | bringing_water | 10
EOF

python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --scene house_single_floor \
  --robot Tiago \
  --batch tasks.txt \
  --colab-url http://127.0.0.1:7860 \
  --symbolic \
  --max-ticks 20
```

### Esempio 3: Debug camera + multi-view

```bash
python3 behavior_integration/scripts/run_continuous_pipeline.py \
  --scene house_single_floor \
  --robot Tiago \
  --task bringing_water \
  --colab-url http://127.0.0.1:7860 \
  --symbolic \
  --debug-camera \
  --multi-view
```

## 📚 Risorse

- **BEHAVIOR-1K Paper:** https://behavior.stanford.edu
- **OmniGibson Docs:** https://behavior.stanford.edu/omnigibson/
- **BehaviorTree.CPP:** https://www.behaviortree.dev

## ✅ Checklist Pre-Run

Prima di ogni esecuzione:

- [ ] `conda activate behavior` attivo
- [ ] In directory `/home/cristiano/oxe-bt-pipeline`
- [ ] LoRA models esistono in `/home/cristiano/lora_models/`
- [ ] Isaac Sim disponibile in `/home/cristiano/isaacsim/`
- [ ] BEHAVIOR-1K datasets in `/home/cristiano/BEHAVIOR-1K/datasets/`
- [ ] Task name corrisponde a cartella in `2025-challenge-task-instances/`
- [ ] Se usi Fetch → aggiungi `--symbolic`
- [ ] Se vuoi vedere GUI → aggiungi `--show-window`

## 🎯 Prossimi Step

1. **Raccogli dataset fallimenti** (100+ esempi)
2. **Analizza pattern di errori comuni**
3. **Prepara dataset per training validator LoRA**
4. **Training validator** (Gemma3-4B o Qwen2.5-VL-3B)
5. **Integra validator in runtime** (vedi `VALIDATOR_STRATEGY.md`)

---

**Status:** ✅ Sistema completo funzionante! VLM → BT → Simulation pipeline operativo.

**Ultimo test riuscito:** 2026-01-08 - Robot Fetch con symbolic primitives, GUI aperta, BT eseguito tick 1.
