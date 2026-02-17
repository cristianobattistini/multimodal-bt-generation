# OXE-BT Pipeline — Documentazione (IT)

Questo repository contiene una pipeline per trasformare episodi del dataset **Open‑X‑Embodiment (OXE)** in un dataset “grounded” composto da:

- **Istruzione** (testo)  
- **Evidenza visiva** (1 immagine oppure una contact‑sheet di 9 frame / video)  
- **Behavior Tree** in **BehaviorTree.CPP v3 XML** (eseguibile da un runtime BT)

Lo scopo finale è addestrare un **Vision‑Language Model (VLM) piccolo** che funga da “cervello” del robot:

1. Il robot osserva la scena (RGB) e riceve un’istruzione.
2. Il VLM (modalità **proposer**) genera un Behavior Tree (BT) coerente con l’istruzione e con ciò che vede.
3. Un **BT executor** “tikka” il tree e, sui leaf node, chiama **primitive / API** disponibili (es. grasp, place, open…), cercando di completare la task.

Direzione di ricerca indicata: **Mixture of Experts** con due adapter LoRA “switchabili” sullo stesso base model:

- **Proposer**: genera un BT iniziale (offline e/o all’avvio della task).
- **Runtime validator**: durante l’esecuzione osserva fallimenti / mismatch e **corregge** parti del BT (solo runtime).

Questa documentazione è volutamente “operativa” e dettagliata, con focus su: `nb/`, `processing/`, `data/`, `data/dataset/`, `data/library/` (e chiarimenti su **BEHAVIOR‑1K**).

---

## 1) Visione d’insieme della pipeline

### 1.1 Flusso dati (alto livello)

1. **Export episodi OXE (TFDS / RLDS)** → `out_temp/…` (o `out/…`)  
2. **Selezione frame** (tipicamente K=9) → `final_selected/sampled_frames/`  
3. **Contact sheet** (3×3, frame [0..8]) e/o **contact video** (MP4)  
4. **Prompt teacher** + contact sheet → generazione **bt.xml** + **meta.json** (teacher LLM)  
5. **Dataset episode‑level** → `data/dataset/<dataset>/episode_###/…`  
6. **Dataset per fine‑tuning VLM** (JSONL + immagini) → `dataset_oxe/` e `dataset_oxe.zip`  
7. **Fine‑tuning VLM (LoRA)** via notebook in `nb/`  
8. **Deployment in simulazione (BEHAVIOR‑1K / OmniGibson)**: il VLM propone BT → il runtime chiama primitives → task completion.

### 1.2 Perché i BT attuali risultano “lineari”

Nel dataset attuale (`data/dataset`) i tree hanno tipicamente:

- root `<BehaviorTree ID="MainTree">` con un solo composite (spesso `<Sequence>`),
- branching limitato (molti `Fallback` e `RetryUntilSuccessful` per percezione / ricerca),
- **Parallel** quasi assente.

Statistiche (calcolate sui 1664 `bt.xml` presenti):

- nodi: media ~13.9, mediana 14, P90=20
- profondità: media ~4.23, mediana 4, P90=5
- presenza `Fallback`: ~62%
- presenza `Parallel`: ~1.2%
- “lineari” senza branching né decorator: ~29.5%

Con un teacher che produce pattern simili, lo student tenderà naturalmente a riprodurre tree simili (BT “quasi lineari”).

### 1.3 Esempio end‑to‑end (script principali)

Sequenza tipica (da repo root):

1. **Export OXE → out/**  
   - configura `processing/utils/config.py` (datasets, `tfds_data_dir`, `out_root="out"` consigliato)
   - esegui:
     ```bash
     python processing/main.py
     ```

2. **Scaffold dataset episodio‑level → `data/dataset/`**  
   ```bash
   python processing/generate_folders.py \
     --mode init \
     --out-root out \
     --dest-root data/dataset \
     --prompt-src prompts/prompt_full_v3.md \
     --overwrite
   ```

3. **Generazione teacher di `bt.xml` + `meta.json`** (2 opzioni):
   - manuale (UI) usando `processing/chat_stage.py`, oppure
   - batch via script in `data/bt_local_gen/` (es. `generate_all_bts.py`) se configurato.

4. **(Opzionale) Genera locals prompt / frame**  
   ```bash
   python processing/generate_folders.py \
     --mode locals \
     --dest-root data/dataset \
     --node-lib data/library/node_library_v_03.json \
     --overwrite
   ```

5. **(Opzionale) Genera `contact_video.mp4`**  
   ```bash
   python processing/generate_folders.py \
     --mode videos \
     --out-root out \
     --dest-root data/dataset \
     --video-duration 4.0 \
     --overwrite
   ```

6. **Costruisci dataset JSONL per fine‑tuning**  
   Nel repo è presente uno script pronto (fuori scope della cartella `nb/`): `vlm_ft/tools/build_jsonl.py`.  
   Output atteso: `dataset_oxe/train/data.jsonl`, `dataset_oxe/train/images/...`, ecc.  
   Poi comprimi in `dataset_oxe.zip` e usa i notebook in `nb/`.

---

## 2) Cartella `processing/` (estrazione episodi + preparazione dataset)

`processing/` contiene la parte “OXE → episode folder”, più utility per costruire il dataset in forma “pronta per prompting / annotazione”.

### 2.1 `processing/utils/config.py` — configurazione centrale

Imposta:

- **dataset / datasets**: nomi TFDS (spesso `*_converted_externally_to_rlds/0.1.0`)
- **split**: es. `train[:100%]`
- **out_root**: dove scrivere gli episodi esportati (default attuale: `out_temp`)
- **tfds_data_dir**: directory locale TFDS (legge `TFDS_DATA_DIR` da env)
- **image_key / instruction_key**: path RLDS per immagine e istruzione (con override per dataset specifici)
- **embeds**: parametri per selezione frame basata su embedding (K, stride / percentuale, backbone, caching…)
- **export_mode / prune_only**: decide cosa tenere nell’output dell’episodio (`final_selected/` è il focus)

### 2.2 `processing/main.py` — export episodi RLDS/TFDS

Scopo: per ogni dataset configurato, iterare episodi e creare una cartella `episode_###` contenente almeno `final_selected/`.

Funzioni chiave usate:

- `processing/utils/loader.py`:
  - `iterate_episodes(ds, split, data_dir=...)`: carica TFDS builder, materializza `steps`
  - `dump_episode_rlds(...)`: salva `raw_frames/frame_####.jpg`, `preview.gif`, `instruction.txt`, `episode_data.json`
  - `resolve_instruction(...)`: robusto rispetto a chiavi diverse nei vari dataset
- `processing/utils/episode_phases.py`:
  - `build_all_episode_phases(...)`: campiona (k‑slicing) e seleziona i frame finali (`final_selected/`)

Output tipico (con pruning attivo):

```
out_temp/<dataset_id>/episode_015/
  final_selected/
    sampled_frames/frame_0000.jpg ... frame_0008.jpg
    preview.gif
    attributes.json
    episode_data.json
```

### 2.3 `processing/frame_selection.py` — selezione frame (embedding‑based)

La selezione “finale” usa:

- stride su timeline (`k_slicing`: int o percentuale)
- backbone pre‑addestrato (default: MobileNetV2 con pooling “avg”)
- embedding normalizzati + k‑center greedy per scegliere **K** frame “diversi” (diversità visiva)

Viene scritto `embeds/selection.json` con:

- `selected_indices`
- parametri (K, k_slicing, backbone, ecc.)
- paths ai frame selezionati

### 2.4 `processing/utils/contact_sheet.py` — contact sheet (3×3) con overlay indici

`create_from_dir(...)` costruisce una griglia con:

- indice tile `[0..]`
- indice sorgente `src=<t>` (frame originale)
- header con dataset_id/episode_id

È il formato ideale da dare al teacher (LLM/VLM grande) per generare BT “grounded” su più istanti.

### 2.5 `processing/generate_folders.py` — costruzione dataset “episode‑level”

È uno script multi‑modalità per passare dall’output `out*/` a un dataset strutturato (cartelle episodio) con prompt/placeholder.

Modalità principali:

- `--mode init`  
  Per ogni episodio in `out_root/<dataset>/<episode>/` crea in `dest_root/<dataset>/<episode>/`:
  - `bt.xml` (skeleton)
  - `meta.json` (skeleton + instruction)
  - `prompt.md` (prompt teacher compilato con TASK/DATASET/EPISODE)
  - `locals/local_{1,2,3}/subtree_.xml/.json` (skeleton)
  - copia contact_sheet se presente in `out_root` (se manca, va generata a parte)

- `--mode locals`  
  Genera `locals/local_{1..3}/local_prompt.md` “ricco” (NODE_LIBRARY + GLOBAL_BT + descrizione + frame) e copia i frame top‑3 (da `meta.json.frame_ranking`).

- `--mode videos`  
  Genera `contact_video.mp4` prendendo fino a 9 frame da `out_root/<ds>/<ep>/final_selected/sampled_frames/`.

- `--mode refresh_images`  
  Aggiorna *solo* contact_sheet e i frame nei locals senza toccare BT/metadati.

Nota importante (stato attuale del codice): alcune parti assumono `out/` come root (non `out_temp/`). Se vuoi usare `out_temp/`, uniforma i path oppure imposta `out_root="out"` in `processing/utils/config.py`.

### 2.6 `processing/chat_stage.py` — staging manuale (p/ f/ r/)

È un tool per workflow “manual copy/paste”:

- `p/`: prompt da incollare in un LLM esterno
- `f/`: frame / contact sheet associati
- `r/`: risultati incollati (XML/JSON) pronti per essere “sinktati” nel dataset

È utile quando il teacher viene usato da UI (ChatGPT/console) e vuoi ridurre errori di path/nomi.

Nota: lo script ha `DATASET_ROOT` hardcoded (es. `dataset1`). Va aggiornato se il dataset reale è `data/dataset`.

### 2.7 `processing/validate_dataset.py` — validatore rapido

Valida sintassi:

- `bt.xml` XML well‑formed
- `meta.json` JSON valido e `episode_id` coerente con la cartella
- `locals/local_i/subtree_.xml/.json`

È pensato per trovare rotture tipiche (file mancanti, JSON rotti, XML con testo extra).

### 2.8 `processing/tools/collect_instruction_sets.py` — analisi istruzioni

Scansiona `out/<dataset>/episode_*/instruction.txt` e produce insiemi deduplicati in `analysis/`.

---

## 3) Cartella `data/`

### 3.1 `data/dataset/` — dataset episode‑level (istruzione + immagini + BT)

Struttura:

```
data/dataset/<dataset_id>/episode_052/
  actions.txt
  prompt.md
  contact_sheet.jpeg
  contact_video.mp4              # opzionale (manca in parte degli episodi)
  sampled_frames/frame_0000.jpg … frame_0008.jpg
  bt.xml
  meta.json
  locals/
    local_1/
      local_prompt.md
      frame_03.jpg
      subtree_.xml
      subtree_.json
    local_2/ ...
    local_3/ ...
```

File e significato:

- `sampled_frames/`  
  I 9 frame selezionati (K=9). Sono la base per:
  - contact_sheet (teacher)
  - eventuale video
  - training student (spesso si usa solo `frame_0000.jpg` per semplicità)

- `contact_sheet.jpeg`  
  Griglia 3×3 dei 9 frame, con indici coerenti col prompt.

- `prompt.md`  
  Prompt teacher completo: istruzione + regole + NODE_LIBRARY + schema della risposta richiesta (XML + JSON).

- `bt.xml`  
  BT in formato BehaviorTree.CPP v3. Nel dataset coesistono due stili validi:
  - tag “diretti”: `<DetectObject .../>`
  - tag generici: `<Action ID="DetectObject" .../>` e `<Condition ID="IsObjectVisible" .../>`

- `meta.json`  
  Metadati e annotazioni generate dal teacher (o curate). Contiene tipicamente:
  - `task_summary`, `task_long_description`
  - `frame_ranking` (ordine e score dei frame più “informativi”)
  - `local_annotations`: 9 entry (una per frame_0..frame_8), con fase e leaf attivo
  - `objects`, `blackboard_keys`, `tree_stats`, ecc.

- `actions.txt`  
  Lista “flat” delle azioni disponibili (con firma). Serve per costruire prompt “student‑friendly”
  del tipo:
  ```
  INSTRUCTION: ...
  actions=[ApproachAndAlign(...), DetectObject(...), ...]
  ```
  e vincolare l’output (“non inventare azioni”).

- `locals/`  
  Materiale per “local BT generation” / decomposizione:
  - `local_prompt.md`: prompt per generare un subtree coerente col global BT
  - `frame_XX.jpg`: il frame associato al local slot
  - `subtree_.xml/.json`: subtree e metadati (possono essere placeholder o generati)

Statistiche dataset (repo attuale):

- dataset OXE inclusi: 17
- episodi: 1664
- `contact_video.mp4` mancante in 692 episodi (non blocca il training image‑based)

### 3.2 `data/library/` — vocabolario BT (node library)

Contiene versioni del file “node library”:

- `data/library/node_library_v_01.json` (btlib_v1.1)
- `data/library/node_library_v_02.json` (btlib_v2.2)
- `data/library/node_library_v_03.json` (btlib_v2.2, più azioni)
- `data/library/node_library.md` (spiegazione formato e best practice)

La node library definisce:

- compositi (`Sequence`, `Fallback`, `Parallel`)
- decorators (`RetryUntilSuccessful`, `Timeout`, …)
- leaf nodes (actions / conditions) e relative porte (`ports`)
- discreti “bin” per alcuni parametri (`port_value_spaces`)

Uso pratico:

1. **Prompting**: il teacher/student deve generare solo nodi presenti in library.  
2. **Validazione**: puoi validare output del modello contro library (tag/porte/tipi/bins).  
3. **Runtime**: ogni leaf node deve esistere come “API/primitive” nell’esecutore (sim o robot reale).

### 3.3 `data/bt_local_gen/` — generazione automatica via API (stato: WIP/eterogeneo)

Questa cartella contiene vari esperimenti per generare BT automaticamente via API (OpenAI).

Componenti presenti:

- `generate_all_bts.py`  
  Script “batch” che scansiona episodi e genera `bt.xml` + `meta.json` chiamando un modello multimodale
  su **prompt.md + contact_sheet**. È pensato per “global BT generation”.

- `validators.py`  
  Parser dei due code block (```xml, ```json) + fallback “senza fence”.  
  La validazione XML è volutamente permissiva (well‑formedness).

Nota sullo stato: alcuni file referenziano moduli non presenti (es. `pipeline.py`, `client_mock.py`) e path legacy
(`dataset1`, `library/…`). Se vuoi usare questo tool come “CLI stabile”, è consigliato:

- uniformare i path al layout attuale (`data/dataset`, `data/library`)
- scegliere **un solo** flusso (global BT o local subtree) e consolidare.

### 3.4 `data/analysis/` — analisi istruzioni

File di supporto (istruzioni uniche per dataset) utili per:

- controllare la copertura semantica delle instruction,
- costruire “instruction sets” controllati,
- evitare duplicati / leak train‑val.

---

## 4) Cartella `nb/` (fine‑tuning VLM: 4 modelli + eval)

`nb/` contiene notebook Colab per fine‑tuning LoRA su dataset `dataset_oxe.zip`.

### 4.1 Dataset usato nei notebook (`dataset_oxe.zip` / `dataset_oxe/`)

Struttura:

```
dataset_oxe/
  train/
    data.jsonl
    images/<dataset>/<episode>/sampled_frames/frame_0000.jpg
  val/
    data.jsonl
    data_renamed_actions.jsonl      # variante con naming “azioni rinominate”
    images/...
```

Conteggi attuali:

- train: 1497 sample
- val: 167 sample

Formato sample (schema Unsloth “vision SFT”):

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text",  "text": "<prompt con instruction + actions...>"},
        {"type": "image", "image": "images/<...>/frame_0000.jpg"}
      ]
    },
    {
      "role": "assistant",
      "content": [
        {"type": "text", "text": "<BT XML>"}
      ]
    }
  ]
}
```

I notebook trasformano questo formato in strutture “in‑memory” dove:

- l’immagine viene caricata come PIL Image,
- per alcuni modelli l’ordine nel content viene reso `image` → `text`.

### 4.2 `nb/smolvlm2_oxe_bt_finetune_wandb.ipynb` — SmolVLM2 (2.2B) + LoRA/QLoRA

- Base model:
  - `HuggingFaceTB/SmolVLM2-2.2B-Instruct` (default)
  - opzionale: `HuggingFaceTB/SmolVLM2-500M-Video-Instruct`
- Training: `transformers.Trainer` + W&B
- LoRA:
  - `r=16`, `alpha=16`
  - `target_modules` include proiezioni del decoder e `modality_projection.proj`
- Output:
  - checkpoint e adapter salvati su Google Drive (path configurabili nel notebook)

### 4.3 `nb/Gemma3_(4B)_Vision.ipynb` — Gemma‑3 4B Vision (Unsloth) + LoRA

- Base model: `unsloth/gemma-3-4b-pt` (4‑bit)
- LoRA tipica:
  - `r=16`
  - `target_modules="all-linear"`
- Trainer: `trl.SFTTrainer` + `SFTConfig`, `UnslothVisionDataCollator`
- Dataset: `dataset_oxe/train/data.jsonl` e `dataset_oxe/val/data.jsonl`

### 4.4 `nb/qwen25_3B_Vision.ipynb` — Qwen2.5‑VL 3B (Unsloth) + LoRA

- Base model: `unsloth/Qwen2.5-VL-3B-Instruct` (4‑bit)
- Trainer: `trl.SFTTrainer`
- Stesse idee di dataset conversion (PIL image first)

### 4.5 `nb/Qwen3_VL_(8B)_Vision_ok.ipynb` — Qwen3‑VL 8B (Unsloth) + LoRA

- Base model: `unsloth/Qwen3-VL-8B-Instruct-unsloth-bnb-4bit`
- Training nel notebook mostrato come run breve (`max_steps=20`) e salvataggio checkpoint su Drive.

### 4.6 `nb/evalutation.ipynb` — valutazione

Notebook per valutare output di più modelli (Gemma/Qwen/SmolVLM2 e anche LLM esterni) con metriche tipo BLEU/ROUGE,
su un subset del dataset.

### 4.7 `nb/push_to_hf.ipynb` — push su HuggingFace

Notebook per login e publishing di dataset/modelli su HF Hub.

---

## 5) Chiarimento: “API/primitive” in BEHAVIOR‑1K (OmniGibson)

In BEHAVIOR‑1K l’ambiente simulato è basato su **OmniGibson**, che a sua volta usa **NVIDIA Omniverse / Isaac Sim**.

### 5.1 Cos’è una “primitive”

Una **action primitive** è una skill ad alto livello (es. *GRASP*, *PLACE_INSIDE*, *OPEN*) che:

- controlla pre‑condizioni (es. “mano libera?”),
- pianifica (motion planning; spesso con CuRobo),
- esegue una sequenza di action low‑level (`env.step(action)` ripetuto),
- verifica post‑condizioni (success/failure),
- in caso di fallimento solleva un’eccezione tipizzata (`ActionPrimitiveError`).

In OmniGibson le primitives sono implementate come **generatori**: `apply_ref(...)` produce una sequenza di action
finché la primitive non termina.

Esempio concettuale (pseudo):

```python
controller = StarterSemanticActionPrimitives(env, robot)
for action in controller.apply_ref(StarterSemanticActionPrimitiveSet.GRASP, target_obj):
    obs, _, terminated, truncated, info = env.step(action)
```

#### Primitive set disponibili (esempi)

Nel codice OmniGibson (BEHAVIOR‑1K) esistono almeno:

- `StarterSemanticActionPrimitiveSet` (realistico, basato su motion planning / CuRobo) con primitive come:
  - `GRASP(obj)`
  - `PLACE_ON_TOP(obj)`
  - `PLACE_INSIDE(obj)`
  - `OPEN(obj)`
  - `CLOSE(obj)`
  - `NAVIGATE_TO(obj)`
  - `RELEASE()`
  - `TOGGLE_ON(obj)`, `TOGGLE_OFF(obj)`
- `SymbolicSemanticActionPrimitiveSet` (simbolico, “teleporta” stati post‑condizione; utile per high‑level learning):
  - include anche `SOAK_UNDER`, `SOAK_INSIDE`, `WIPE`, `CUT`, `PLACE_NEAR_HEATING_ELEMENT`, ecc.

In altre parole: in BEHAVIOR‑1K l’“array di azioni disponibili” che metti nel prompt dovrebbe essere un sottoinsieme
coerente con queste primitive (o con la tua implementazione equivalente).

#### Errori tipici (utile per il runtime validator)

Le primitives possono fallire e sollevare `ActionPrimitiveError` con reason (categorie principali):

- `PRE_CONDITION_ERROR` (precondizioni non soddisfatte)
- `SAMPLING_ERROR` (non riesce a campionare pose / target)
- `PLANNING_ERROR` (planning fallito, es. path)
- `EXECUTION_ERROR` (errore durante esecuzione)
- `POST_CONDITION_ERROR` (post‑condizioni non verificate)

Questa tassonomia è perfetta per costruire un dataset “validator‑runtime”: per ogni failure puoi loggare
il reason e addestrare il validator a proporre una patch BT mirata (retry, fallback, re‑detect, re‑plan, ecc.).

### 5.2 Perché serve al tuo progetto BT

Nel tuo runtime BT, un leaf node (es. `Grasp(target)`) può essere implementato chiamando una primitive:

- **RUNNING**: finché il generator produce action
- **SUCCESS**: quando il generator termina senza errori
- **FAILURE**: quando solleva `ActionPrimitiveError` (o `ActionPrimitiveErrorGroup`)

Questa è la “connessione” tra il BT proposto dal modello e l’esecuzione reale/simulata.

---

## 6) Come predisporre BEHAVIOR‑1K (installazione e primo run)

Riferimento ufficiale: `https://behavior.stanford.edu/` (installazione e docs).

### 6.1 Requisiti (indicativi)

- Ubuntu 20.04+ (o Windows 10+)
- 32GB+ RAM
- NVIDIA GPU (RTX 2070+; 8GB+ VRAM)

### 6.2 Installazione (dev setup)

Da docs BEHAVIOR‑1K:

```bash
git clone -b v3.7.2 https://github.com/StanfordVL/BEHAVIOR-1K.git
cd BEHAVIOR-1K

# Full install (include primitives ed eval)
./setup.sh --new-env --omnigibson --bddl --joylo --dataset --eval --primitives

conda activate behavior
```

### 6.3 Esempio: eseguire una task con primitives (hardcoded)

Esempio (stile OmniGibson) di “picking_up_trash”:

- crea un env `BehaviorTask`
- usa `StarterSemanticActionPrimitives`
- esegue `GRASP` e `PLACE_INSIDE`

Nel repo BEHAVIOR‑1K esiste un esempio molto vicino a questo (`wip_solve_behavior_task.py`).

Suggerimento pratico:

- prima verifica che OmniGibson parta con un esempio “base” (viewer + teleoperation)
- poi passa a un esempio di primitives
- solo dopo passa a una `BehaviorTask` lunga (task BEHAVIOR‑1K)

---

## 7) Integrare il tuo VLM (LoRA) dentro BEHAVIOR‑1K come “BT proposer”

### 7.1 Obiettivo tecnico

Costruire un ciclo:

1. `env.reset()` → ottieni osservazione RGB e instruction/task
2. Prompt → VLM → **BT XML**
3. Parse BT → esegui BT con primitive API
4. Se fallisce: (opzionale) switch adapter → **runtime validator** → patch subtree → continua.

### 7.2 Mappare “azioni nel prompt” a primitive reali

Il supervisore intende tipicamente:

- Nel prompt del proposer elenchi **solo** le azioni primitive realmente eseguibili nell’ambiente
  (es. `GRASP`, `PLACE_ON_TOP`, `OPEN`, …).
- Il BT risultante usa quelle azioni.
- Il runtime, quando “vede” un leaf `GRASP(obj)`, chiama l’API della primitive corrispondente.

Questo implica che la tua `node_library` deve essere *coerente* con l’ambiente target:

- o costruisci una node_library “BEHAVIOR‑1K‑native” (leaf = primitive set),
- oppure mantieni la tua libreria e implementi wrappers che traducono i leaf in sequenze di primitives (più complesso).

In pratica, per ridurre complessità e aumentare eseguibilità in simulazione, è quasi sempre preferibile:

1. definire una library minimale “semantic primitives” (10–20 leaf),
2. addestrare proposer e validator su quella,
3. *solo in un secondo momento* espandere verso leaf più “micro” (approach/align) se serve.

### 7.3 Switching proposer/validator (MoE con LoRA)

Pattern tipico con `peft`:

- carichi base model una volta
- carichi 2 adapter LoRA:
  - `proposer_adapter`
  - `validator_adapter`
- durante esecuzione:
  - `model.set_adapter("proposer")` per generare BT iniziale
  - `model.set_adapter("validator")` per patchare subtree a runtime

Il dataset per il validator si può costruire loggando:

- contesto runtime (osservazione, BT parziale, nodo fallito, error reason),
- patch correttiva attesa (subtree sostitutivo, parametri corretti, fallback/retry).

---

## 8) Note pratiche e “punti di attenzione”

- **Path legacy**: alcuni script citano `dataset1/`, `dataset3/`, `library/` e `out/`. Il layout attuale usa `data/dataset/` e `data/library/` (consigliato uniformare).
- **Contact video**: non è presente per tutti gli episodi; per modelli video‑capable potresti rigenerarlo con `processing/generate_folders.py --mode videos`.
- **Bias di struttura**: per ottenere BT più ricchi (branching, recovery) devi cambiare i prompt teacher e/o introdurre “curriculum” (task che richiedono fallback nested, parallel, condition‑gating).
- **Sicurezza**: evita di salvare chiavi API nei file del repo; preferisci env var (`OPENAI_API_KEY`, ecc.).

---

## 9) Indice rapido dei file più importanti (per cartella)

### `processing/`
- `processing/main.py` — export episodi da TFDS/RLDS
- `processing/utils/config.py` — config (datasets, out_root, selezione frame)
- `processing/frame_selection.py` — embedding selection (k‑center)
- `processing/utils/contact_sheet.py` — genera contact sheet indicizzate
- `processing/generate_folders.py` — costruisce `data/dataset` e prompt/locals/video
- `processing/validate_dataset.py` — validatore dataset

### `data/`
- `data/dataset/` — dataset episodio‑level (prompt + frames + BT + meta)
- `data/library/` — node libraries (vocabolario BT)
- `data/bt_local_gen/` — script per generazione automatica (WIP)
- `data/analysis/` — insiemi di istruzioni e analisi

### `nb/`
- fine‑tuning LoRA: `smolvlm2_...`, `Gemma3_...`, `qwen25_...`, `Qwen3_...`
- eval: `evalutation.ipynb`
- publishing: `push_to_hf.ipynb`

---

## 10) Glossario minimo

- **OXE / Open‑X‑Embodiment**: collezione di dataset robotici rilasciati in formato TFDS/RLDS.
- **RLDS**: schema “episodio/step” usato da molti dataset embodied (steps con observation/action).
- **Contact sheet**: immagine mosaico (qui 3×3) che riassume 9 frame rappresentativi.
- **BehaviorTree.CPP**: libreria C++ per eseguire BT; XML definisce la struttura e i leaf nodes.
- **Node library**: vocabolario consentito (nodi, porte, value bins) usato per vincolare/validare output.
- **Proposer**: adapter/modello che genera un BT iniziale da visione + istruzione.
- **Runtime validator**: adapter/modello che corregge/patcha BT durante l’esecuzione (solo runtime).
