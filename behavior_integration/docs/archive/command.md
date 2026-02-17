# Command Reference (copy/paste)

Tutti i comandi sotto assumono che tu sia nella root del repo (`oxe-bt-pipeline`).

---

## 0) Setup rapido (Python env + .env)

### Ambiente Python (pip)
```bash
python -m pip install -r requirement.txt
```

### `.env` (chiave OpenAI + modelli + retry)
```bash
cp .env.template .env
```

Poi modifica `.env`:
- `OPENAI_API_KEY`: la tua chiave (non committare `.env`, è già in `.gitignore`).
- `OPENAI_MODEL` / `MODEL_*`: scegli il modello (per il PoC economico: `gpt-4o-mini`).
- `OPENAI_RETRY_MAX_SLEEP`: cap dello sleep per retry (evita attese lunghissime).
- `GRAYSCALE_SCENE_ANALYSIS/GRAYSCALE_ARCHITECT`: opzionale, forza image grayscale per alcuni agenti.

Esempio pronto:
```bash
OPENAI_API_KEY="__YOUR_REAL_KEY_HERE__"
OPENAI_MODEL="gpt-4o-mini"

# cap sleep retry (evita attese lunghissime; consigliato)
OPENAI_RETRY_MAX_SLEEP="15"
OPENAI_RETRY_BASE_SLEEP="1.5"
```

---

## 1) Download dataset TFDS (OXE) su disco (gsutil)

Questo script **non ha CLI**: scarica un elenco hardcoded di dataset TFDS in `~/tensorflow_datasets`.

1) (opzionale) Modifica la lista `DATASETS_TO_DOWNLOAD` in:
`processing/tools/download_selected_datasets.py`

2) Esegui:
```bash
python processing/tools/download_selected_datasets.py
```

Requisiti:
- `gsutil` installato e autenticato (GCP).

---

## 2) Export episodi OXE → `out_temp/` (frame + metadata + phase “final_selected”)

Questo step è config-driven (non c’è CLI): edita `processing/utils/config.py`, poi lancia:
```bash
python processing/main.py
```

Config utili in `processing/utils/config.py` (da copiare/incollare/settare):
- `out_root = "out_temp"`
- `tfds_data_dir = os.path.expanduser("~/tensorflow_datasets")`
- `split = "train"`
- `limit_episodes_per_dataset = 200` (esempio)
- `resume_from_existing = True`
- `resume_mode = "fill_gaps"` oppure `"append"`
- `skip_existing = True`
- `overwrite_incomplete = True`

---

## 3) Genera contact sheets (9 frame) dentro `out_temp/*/episode_*/final_selected/`

### Tutti i dataset trovati in `out_temp/`
```bash
python processing/tools/generate_contact_sheets_out.py \
  --out-root out_temp \
  --workers 8
```

### Contact sheet ridotto (lato lungo ~768px)
```bash
python processing/tools/generate_contact_sheets_out.py \
  --out-root out_temp \
  --out-name contact_sheet_reduced.jpg \
  --tile-max-w 256 \
  --workers 8
```

### Rigenera “contact_sheet_reduced” pulito (senza header e con indici piccoli)
```bash
find out_temp -type f -name 'contact_sheet*' -delete
python processing/tools/generate_contact_sheets_out.py \
  --out-root out_temp \
  --out-name contact_sheet_reduced.jpg \
  --tile-max-w 256 \
  --workers 8 \
  --force
```

### Solo alcuni dataset (comma-separated)
```bash
python processing/tools/generate_contact_sheets_out.py \
  --out-root out_temp \
  --datasets asu_table_top_converted_externally_to_rlds_0.1.0,cmu_stretch_0.1.0 \
  --workers 8
```

### Rigenera anche se già esiste (overwrite)
```bash
python processing/tools/generate_contact_sheets_out.py \
  --out-root out_temp \
  --workers 8 \
  --force
```

---

## 4) Crea struttura episode-level “classica” (dataset/...) e locals

Script: `processing/generate_folders.py`

### 4.1 Init: crea cartelle episodio e copia frame/prompt base
```bash
python processing/generate_folders.py \
  --mode init \
  --out-root out_temp \
  --dest-root dataset \
  --prompt-src prompts/prompt_full.md \
  --prompt-name prompt.md
```

### 4.2 Locals: genera prompt locali (richiede node library)
```bash
python processing/generate_folders.py \
  --mode locals \
  --out-root out_temp \
  --dest-root dataset \
  --node-lib data/library/node_library.json
```

### 4.3 Videos: genera MP4 da 9 frame accanto a contact_sheet
```bash
python processing/generate_folders.py \
  --mode videos \
  --out-root out_temp \
  --dest-root dataset \
  --video-duration 4.0
```

### 4.4 Dry-run (non scrive nulla)
```bash
python processing/generate_folders.py \
  --mode init \
  --out-root out_temp \
  --dest-root dataset \
  --dry-run
```

---

## 5) Sampling randomico episodi (per provare “tutti i dataset”)

### 5.1 Sample N episodi per dataset → JSONL
```bash
python tools/sample_eval_episodes.py \
  --out-root out_temp \
  --max-per-dataset 2 \
  --seed 0 \
  --output eval_samples.jsonl
```

### 5.2 Sample solo alcuni dataset
```bash
python tools/sample_eval_episodes.py \
  --out-root out_temp \
  --datasets asu_table_top_converted_externally_to_rlds_0.1.0,cmu_stretch_0.1.0 \
  --max-per-dataset 5 \
  --seed 42 \
  --output eval_samples.jsonl
```

---

## 6) Run Teacher sui sample (trial/debug)

### 6.1 Run base (scrive JSONL ricco + audit log)
```bash
python tools/run_teacher_on_samples.py \
  --samples eval_samples.jsonl \
  --output-dir dataset_distillation_trial \
  --split train \
  --tqdm
```

### 6.2 Con copia immagini + trace steps nel JSONL + dump su disco
```bash
python tools/run_teacher_on_samples.py \
  --samples eval_samples.jsonl \
  --output-dir dataset_distillation_trial \
  --split train \
  --copy-images \
  --dump-steps \
  --dump-steps-to-disk \
  --tqdm
```

### 6.3 Limit e log file (utile con tqdm)
```bash
python tools/run_teacher_on_samples.py \
  --samples eval_samples.jsonl \
  --output-dir dataset_distillation_trial \
  --split train \
  --limit 20 \
  --tqdm \
  --log-file teacher_trial.log
```

---

## 7) Generazione dataset massivo (Teacher) da `out_temp/`

Script: `embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py`

### 7.1 JSONL “rich trace” (consigliato per split adapter)
```bash
python embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py \
  --out-root out_temp \
  --output-dir dataset_agentic_v1 \
  --output-mode jsonl \
  --copy-images \
  --tqdm \
  --tqdm-agents
```

### 7.2 Solo alcuni dataset + limit
```bash
python embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py \
  --out-root out_temp \
  --output-dir dataset_agentic_v1 \
  --output-mode jsonl \
  --datasets asu_table_top_converted_externally_to_rlds_0.1.0 cmu_stretch_0.1.0 \
  --max-per-dataset 200 \
  --limit 500 \
  --copy-images \
  --tqdm
```

### 7.2b Parallel + dry-run (lista episodi) 
```bash
# Dry-run: mostra quanti/quali episodi verranno processati (senza spendere token)
python embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py \
  --out-root out_temp \
  --output-dir dataset_agentic_v1 \
  --output-mode jsonl \
  --max-per-dataset 200 \
  --val-ratio 0.1 \
  --val-seed pal_v1 \
  --dry-run

# Esecuzione in parallelo (max 5)
python embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py \
  --out-root out_temp \
  --output-dir dataset_agentic_v1 \
  --output-mode jsonl \
  --max-per-dataset 200 \
  --parallel 5 \
  --val-ratio 0.1 \
  --val-seed pal_v1 \
  --fail-log dataset_agentic_v1/failed.jsonl \
  --copy-images \
  --tqdm
```

### 7.3 Split train/val deterministico
```bash
python embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py \
  --out-root out_temp \
  --output-dir dataset_agentic_v1 \
  --output-mode jsonl \
  --val-ratio 0.05 \
  --val-seed pal_v1 \
  --copy-images \
  --tqdm
```

### 7.4 Dump steps intermedi su disco (oltre al JSONL)
```bash
python embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py \
  --out-root out_temp \
  --output-dir dataset_agentic_v1 \
  --output-mode jsonl \
  --copy-images \
  --dump-intermediate-to-disk \
  --tqdm
```

### 7.5 Modalita BT (file per episodio)
```bash
python embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py \
  --out-root out_temp \
  --output-dir dataset_agentic_bt \
  --output-mode bt \
  --dump-intermediate \
  --dump-intermediate-to-disk \
  --tqdm
```

### 7.6 Resume / non riprocessare episodi gia salvati
Di default fa resume (skip episodi già salvati). Per forzare ricalcolo:
```bash
python embodied_bt_brain/dataset_proposer_agentic/generate_dataset.py \
  --out-root out_temp \
  --output-dir dataset_agentic_v1 \
  --output-mode jsonl \
  --no-resume \
  --tqdm
```

### 7.7 Ctrl+C “safe”
- Primo Ctrl+C: finisce l’episodio in corso, salva, poi esce.
- Secondo Ctrl+C: esce subito.

---

## 8) Build dataset Student (End-to-End) includendo prompt `prompts/inference/`

Input: il JSONL “rich trace” con almeno `trace.semantic_state` e `trace.final_xml`.

### 8.1 Build con default path (se usi i default dello script)
```bash
python tools/split_dataset.py
```

### 8.2 Build specificando input/output
```bash
python tools/split_dataset.py \
  --input dataset_agentic_v1/train/data.jsonl \
  --output dataset_agentic_student_v1/train
```

Output:
- `dataset_agentic_student_v1/train/train_e2e.jsonl` (target: `State Analysis` + `final_xml`)
- Prompt usato: `prompts/inference/system_interface.md` (solo `actions`)

---

## 9) QA / Report su dataset “rich trace”

### 9.1 Report XML issues comuni (final_xml)
```bash
python tools/report_rich_records.py \
  --input dataset_agentic_v1/train/data.jsonl
```

---

## 10) Utility: raccolta instruction sets (hardcoded)

Script senza CLI: `processing/tools/collect_instruction_sets.py`

1) Modifica dentro il file:
- `ROOT = Path("out")` (se i tuoi export stanno in `out_temp`, cambia in `Path("out_temp")`)
- `DATASETS = [...]`
- `TAG = "batchX"`

2) Esegui:
```bash
python processing/tools/collect_instruction_sets.py
```

Output:
- `analysis/instruction_sets.<TAG>.json`
- `analysis/instructions_all_unique.<TAG>.txt`

---

## 11) Utility: validation dataset “classico” (dataset/...)

Script: `processing/validate_dataset.py` (lista dataset hardcoded in testa al file).

```bash
python processing/validate_dataset.py
```

Oppure passa una root diversa:
```bash
python processing/validate_dataset.py dataset1
```

---

## 12) Utility: staging manuale prompts/frames (chat_stage)

Script: `processing/chat_stage.py` (ha CLI con subcommands).

### 12.1 Staging locals (p/ e f/) da un episodio in poi
```bash
python processing/chat_stage.py build --from 1 --dataset dlr_sara_grid_clamp_converted_externally_to_rlds_0.1.0 --locals 1,2,3
```

### 12.2 Staging ROOT (prompt + contact sheet)
```bash
python processing/chat_stage.py build-root --from 1 --dataset dlr_sara_grid_clamp_converted_externally_to_rlds_0.1.0
```

### 12.3 Status (quanti file verrebbero preparati)
```bash
python processing/chat_stage.py status --from 10 --dataset dlr_sara_grid_clamp_converted_externally_to_rlds_0.1.0 --locals 1,2,3
python processing/chat_stage.py status-root --from 10 --dataset dlr_sara_grid_clamp_converted_externally_to_rlds_0.1.0
```

### 12.4 Scaffold output (r/) segnaposto
```bash
python processing/chat_stage.py scaffold-out --from 1 --dataset dlr_sara_grid_clamp_converted_externally_to_rlds_0.1.0 --locals 1,2,3 --include both --force
```

### 12.5 Applica output (r/) al dataset
```bash
python processing/chat_stage.py apply-out --dataset dlr_sara_grid_clamp_converted_externally_to_rlds_0.1.0
```

### 12.6 Pulisci staging dirs
```bash
python processing/chat_stage.py clean
```
