# Linear Dataset Pipeline - Documentazione

## Obiettivo

Creare un dataset per training Vision-to-BehaviorTree che colleghi:
- **Input:** Instruction (testo) + Contact Sheet (immagine 3x3 con 9 frames)
- **Output:** BehaviorTree XML lineare semplice

### Problema Risolto

I dataset precedenti in `dataset_agentic` avevano un **bias pesante**: usavano SEMPRE Retry/Fallback/Timeout/SubTree anche per task semplici. Questo non insegna al modello QUANDO usare questi costrutti.

### Soluzione

1. **Dataset base:** ~1800 BT lineari sequenziali semplici (NO Retry/Fallback/Timeout/SubTree)
2. **Augmentation futura:** ~500 varianti selezionate per insegnare QUANDO usare i costrutti complessi

---

## Architettura Pipeline

```
[OXE Episode]
     │
     ├── instruction: "pick 7up can from bottom shelf of fridge"
     ├── contact_sheet: 3x3 grid (9 frames)
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ FASE 1: Scene Analysis (LLM Call #1)                        │
│                                                             │
│ Input: instruction + contact_sheet (9 frames)               │
│                                                             │
│ Output YAML (scene_analysis):                               │
│   target: "7up_can"                                         │
│   destination: ""                                           │
│   expanded_instruction: "Pick up the 7up can from..."       │
│   scene_context: "Fridge is closed. 7up can on shelf."      │
│   expected_sequence: "First open fridge, then grasp can"    │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ FASE 2: BT Generation - Architect (LLM Call #2)             │
│                                                             │
│ Input: instruction + contact_sheet + scene_analysis         │
│                                                             │
│ Output: BT lineare (SOLO Sequence + Action nodes)           │
│   <Sequence>                                                │
│     <!-- Navigate to fridge -->                             │
│     <Action ID="NAVIGATE_TO" obj="fridge"/>                 │
│     <!-- Open fridge -->                                    │
│     <Action ID="OPEN" obj="fridge"/>                        │
│     <!-- Navigate to 7up_can -->                            │
│     <Action ID="NAVIGATE_TO" obj="7up_can"/>                │
│     <!-- Grasp 7up_can -->                                  │
│     <Action ID="GRASP" obj="7up_can"/>                      │
│   </Sequence>                                               │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ FASE 3: Conformance Validation                              │
│                                                             │
│ Check:                                                      │
│   ✓ XML syntax valid                                        │
│   ✓ Primitive ∈ PAL v1                                      │
│   ✓ Logical dependencies (NAVIGATE before GRASP, etc.)     │
│   ✓ NO costrutti complessi (rifiuta se trova Retry, etc.)  │
│                                                             │
│ Verdict: ACCEPT o REJECT                                    │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
[Dataset Entry: JSONL con instruction, image, BT XML]
```

---

## Stato Implementazione

### File Completati

| File | Stato | Descrizione |
|------|-------|-------------|
| `teacher_loop.py` | ✅ | Pipeline semplificata, solo conformance |
| `generate_dataset.py` | ✅ | Script unificato con --parallel, --limit, --tqdm |
| `prompts/scene_analysis.md` | ✅ | Schema YAML con CoT (expected_sequence) |
| `prompts/architect.md` | ✅ | Verb-to-Primitive mapping, Self-Check |
| `agents/instruction_filter.py` | ✅ | Filtra istruzioni problematiche |
| `agents/scene_analysis.py` | ✅ | Supporta nuovo schema YAML |
| `agents/architect.py` | ✅ | Genera BT lineari |
| `agents/conformance.py` | ✅ | Valida PAL v1 |
| `augmentation/bt_augmenter.py` | ✅ | Wrapper granulare per Retry/Timeout/Fallback |
| `augmentation/bt_postprocessor.py` | ✅ | Estrae allowed_actions, crea entry |

### Agent Rimossi

- ❌ `RobustnessAgent` - Non necessario per BT lineari
- ❌ `RecoveryPlannerAgent` - Non necessario per BT lineari
- ❌ `SubtreeEnablementAgent` - Non necessario per BT lineari

---

## Comandi per Generare il Dataset

### Dry Run (verifica episodi)
```bash
python -m embodied_bt_brain.dataset_proposer_agentic.generate_dataset \
    --out-root out_temp \
    --output-dir dataset_linear \
    --output-mode jsonl \
    --dry-run \
    --limit 100
```

### Generazione con Parallelismo
```bash
python -m embodied_bt_brain.dataset_proposer_agentic.generate_dataset \
    --out-root out_temp \
    --output-dir dataset_linear \
    --output-mode jsonl \
    --parallel 3 \
    --tqdm \
    --dump-intermediate-to-disk
```

### Opzioni Principali

| Flag | Descrizione |
|------|-------------|
| `--out-root` | Directory con episodi OXE (default: `out_temp`) |
| `--output-dir` | Directory output dataset (default: `dataset_agentic`) |
| `--output-mode` | `jsonl` (training) o `bt` (file XML separati) |
| `--parallel N` | Processa N episodi in parallelo (1-5) |
| `--limit N` | Max episodi da processare |
| `--max-per-dataset N` | Max episodi per singolo dataset OXE |
| `--tqdm` | Progress bar episodi |
| `--tqdm-agents` | Progress bar per-agent (solo --parallel 1) |
| `--dump-intermediate-to-disk` | Salva step intermedi |
| `--dry-run` | Lista episodi senza processare |
| `--no-resume` | Non saltare episodi già processati |

---

## Schema Scene Analysis

```yaml
scene_analysis:
  target: "<main object(s), string or array, snake_case>"
  destination: "<where to place, snake_case or empty>"
  expanded_instruction: "<instruction with scene details>"
  scene_context: "<INITIAL state observations>"
  expected_sequence: "<plan in natural language>"
```

### Regole
- `target`: stringa singola o array per multi-oggetto (es. `["fish", "sausage", "tomato"]`)
- `destination`: sempre snake_case
- `scene_context`: descrive SOLO lo stato iniziale (Frame 0)
- `expected_sequence`: piano futuro (CoT per lo student)
- **Lunghezza proporzionale** alla complessità del task
- NO riferimenti ai numeri di frame

### Esempio (singolo oggetto)
```yaml
scene_analysis:
  target: "7up_can"
  destination: ""
  expanded_instruction: "Pick up the 7up can from the bottom shelf inside the fridge"
  scene_context: "Fridge is closed. 7up can on bottom shelf inside."
  expected_sequence: "First open the fridge door, then reach inside and grasp the can"
```

### Esempio (multi-oggetto)
```yaml
scene_analysis:
  target: ["fish", "sausage", "tomato"]
  destination: "frying_pan"
  expanded_instruction: "Pick up the fish, sausage, and tomato and place each into the frying pan"
  scene_context: "Fish, sausage, and tomato on counter. Frying pan on stove, empty."
  expected_sequence: "For each item: navigate, grasp, navigate to pan, place inside, release. Repeat for all three."
```

---

## PAL v1 Primitives

Le uniche primitive ammesse nei BT generati:

**Manipulation:**
- `GRASP(obj)` - Afferra oggetto
- `RELEASE` - Rilascia (no parametro)
- `PLACE_ON_TOP(obj)` - Posiziona SU superficie (obj = destinazione)
- `PLACE_INSIDE(obj)` - Posiziona DENTRO container (obj = destinazione)
- `PUSH(obj)` - Spingi oggetto

**Navigation:**
- `NAVIGATE_TO(obj)` - Muovi verso oggetto/posizione

**Container Operations:**
- `OPEN(obj)` - Apri container/porta
- `CLOSE(obj)` - Chiudi container/porta

**Appliance Operations:**
- `TOGGLE_ON(obj)` - Accendi
- `TOGGLE_OFF(obj)` - Spegni

**Other:**
- `POUR(obj)` - Versa in obj (destinazione)
- `FOLD(obj)`, `UNFOLD(obj)` - Piega/Spiega
- `WIPE(obj)` - Pulisci
- `CUT(obj)` - Taglia
- `HANG(obj)` - Appendi su obj (destinazione)
- `SOAK_UNDER(obj)`, `SOAK_INSIDE(obj)` - Immergi
- `PLACE_NEAR_HEATING_ELEMENT(obj)` - Posiziona vicino calore
- `SCREW(obj)` - Avvita
- `FLIP(obj)` - Raddrizza oggetto rovesciato

### Semantic Parameter (obj)

**Category A - obj = oggetto su cui si agisce:**
- NAVIGATE_TO, GRASP, OPEN, CLOSE, TOGGLE_ON, TOGGLE_OFF, PUSH, FOLD, UNFOLD, WIPE, CUT, SOAK_*, SCREW, FLIP

**Category B - obj = DESTINAZIONE (non l'oggetto tenuto):**
- PLACE_ON_TOP, PLACE_INSIDE, POUR, HANG, PLACE_NEAR_HEATING_ELEMENT

---

## Verb Synonym Groups

L'Architect usa gruppi semantici invece di pattern matching rigido:

| Famiglia | Verbi | Primitiva |
|----------|-------|-----------|
| **GRASP** | pick, grab, hold, raise, lift, take, get, fetch, collect | NAVIGATE_TO → GRASP |
| **PUSH** | push, slide, sweep (con direzione), knock, shove, move (senza dest) | NAVIGATE_TO → PUSH |
| **PLACE** | put, place, set, lay, insert, store | GRASP → NAVIGATE → PLACE_* → RELEASE |
| **OPEN** | open, pull open, lift open | NAVIGATE_TO → OPEN |
| **TOGGLE** | turn on/off, switch on/off, activate, press | NAVIGATE_TO → TOGGLE_* |
| **WIPE** | wipe, clean, swipe, sweep (superficie) | NAVIGATE_TO → WIPE |
| **FLIP** | flip upright, upright | NAVIGATE_TO → FLIP |

### Verbi Context-Dependent

| Verbo | Contesto | Primitiva |
|-------|----------|-----------|
| "sweep" | con direzione | PUSH |
| "sweep" | superficie | WIPE |
| "move" | con destinazione | GRASP + PLACE |
| "move" | senza destinazione | PUSH |
| "lift" | oggetto | GRASP |
| "lift" | "lift open" (coperchio) | OPEN |

### Casi Speciali
- Se `scene_context` menziona container "closed" → aggiungi OPEN prima di accedere
- Se oggetto già in mano → salta NAVIGATE_TO e GRASP
- PUSH: NO GRASP, NO RELEASE (spingi senza sollevare)

---

## Istruzioni Filtrate

Pattern esclusi automaticamente da `instruction_filter.py`:

```python
EXCLUDED_PATTERNS = [
    r"play with",              # Troppo vago
    r"NOT MOVING",             # Non è un comando
    r"Video format",           # Errore
    r"Interact with",          # Open-ended
    r"make a cup of",          # Troppo astratto
    r"make a piece of",        # Troppo astratto
    r"end effector",           # Meta-descrizione
    r"transition from",        # Meta-descrizione
    r"diverse but meaningful", # Open-ended
    r"^\s*$",                  # Vuoto
    r"^N/A$", r"^nan$", r"^none$",  # Placeholder
]
```

Lunghezza: min 5 chars, max 500 chars.

---

## Augmentation (Fase Futura)

L'augmentation wrappa SINGOLE azioni, non l'intera sequenza.
L'istruzione specifica ESPLICITAMENTE quale azione wrappare.

### Esempi

**Retry su GRASP:**
```
Istruzione: "pick up apple, retry grasp 3 times"
BT:
  <Sequence>
    <Action ID="NAVIGATE_TO" obj="apple"/>
    <RetryUntilSuccessful num_attempts="3">
      <Action ID="GRASP" obj="apple"/>
    </RetryUntilSuccessful>
  </Sequence>
```

**Timeout su NAVIGATE:**
```
Istruzione: "navigate to apple within 10 seconds, then grasp it"
BT:
  <Sequence>
    <Timeout msec="10000">
      <Action ID="NAVIGATE_TO" obj="apple"/>
    </Timeout>
    <Action ID="GRASP" obj="apple"/>
  </Sequence>
```

**Fallback su GRASP:**
```
Istruzione: "grasp apple, if fails try pushing it first"
BT:
  <Sequence>
    <Action ID="NAVIGATE_TO" obj="apple"/>
    <Fallback>
      <Action ID="GRASP" obj="apple"/>
      <Sequence>
        <Action ID="PUSH" obj="apple"/>
        <Action ID="GRASP" obj="apple"/>
      </Sequence>
    </Fallback>
  </Sequence>
```

### Distribuzione Target

| Tipo | Quantità |
|------|----------|
| Base (BT lineari) | ~1800 |
| +Retry | ~150-200 |
| +Timeout | ~150-200 |
| +Fallback | ~50-100 |
| **Totale** | ~2200-2500 |

---

## File di Riferimento

| File | Descrizione |
|------|-------------|
| `teacher_loop.py` | Orchestrazione pipeline |
| `generate_dataset.py` | Script principale generazione |
| `prompts/scene_analysis.md` | Prompt Scene Analysis |
| `prompts/architect.md` | Prompt Architect |
| `prompts/conformance.md` | Prompt Conformance |
| `agents/` | Implementazioni agenti |
| `augmentation/bt_augmenter.py` | Wrapper granulare |
| `augmentation/bt_postprocessor.py` | Post-processing dataset |

---

## Changelog

- **v3.1** (Current): Prompt migliorati e primitiva FLIP
  - Nuova primitiva: FLIP per task "flip upright"
  - `target`: ora supporta stringa O array per task multi-oggetto
  - Prompt: Verb Synonym Groups (semantici) invece di tabella rigida
  - Lunghezza scene_context/expected_sequence proporzionale alla complessità

- **v3.0**: Pipeline LINEAR semplificata
  - Rimossi: RobustnessAgent, RecoveryPlannerAgent, SubtreeEnablementAgent
  - Output: SOLO BT lineari (Sequence + Action)
  - Schema scene_analysis semplificato con CoT (expected_sequence)
  - Prompt architect con Self-Check e Verb-to-Primitive mapping
  - Script unificato `generate_dataset.py`

- **v2.0**: Pipeline con validazione deterministica (FinalValidator)

- **v1.0**: Pipeline completa con 6 agenti configurabili
