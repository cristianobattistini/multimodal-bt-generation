# Run Continuous Pipeline - Documentazione Completa

Pipeline per l'esecuzione continua di Behavior Trees in simulazione OmniGibson.

---

## Indice

1. [Panoramica](#1-panoramica)
2. [Architettura e Componenti](#2-architettura-e-componenti)
3. [Modalità di Esecuzione](#3-modalità-di-esecuzione)
4. [BT Templates Predefiniti](#4-bt-templates-predefiniti)
5. [Sistema Multi-View](#5-sistema-multi-view)
6. [Configurazione Rendering](#6-configurazione-rendering)
7. [Task BEHAVIOR Supportate](#7-task-behavior-supportate)
8. [Orientamento Automatico Camera](#8-orientamento-automatico-camera)
9. [Struttura Directory Output](#9-struttura-directory-output)
10. [Riferimento Completo Opzioni CLI](#10-riferimento-completo-opzioni-cli)
11. [Esempi Pratici](#11-esempi-pratici)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Panoramica

### Scopo

`run_continuous_pipeline.py` è il punto di ingresso principale per eseguire Behavior Trees (BT) in simulazione OmniGibson. Supporta:

- **Esecuzione di BT predefiniti** (senza VLM) per test e validazione
- **Generazione di BT tramite VLM** da istruzioni in linguaggio naturale
- **Modalità interattiva** per debug e sviluppo
- **Cattura multi-view** per documentazione e analisi

### Flusso di Esecuzione

```
┌─────────────────┐
│  Inizializzazione │
│  OmniGibson (~5min)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Creazione Env   │
│  (scene + task)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Reset Episodio  │
│  + Warmup Steps  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Orientamento    │
│  Camera (auto)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Screenshot      │
│  INIZIALE        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Esecuzione BT   │
│  (tick by tick)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Screenshot per  │
│  ogni primitiva  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Risultato +     │
│  Summary         │
└─────────────────┘
```

---

## 2. Architettura e Componenti

### Diagramma Componenti

```
ContinuousPipeline
├── EnvironmentManager      # Gestione OmniGibson
├── CameraController        # Orientamento head camera
├── ImageCapture            # Cattura screenshot
├── BTGenerator             # Generazione BT (VLM)
├── BTExecutor              # Esecuzione BT
├── EpisodeRunner           # Orchestrazione episodi
└── InteractiveController   # Controllo menu-driven
```

### Componenti Dettagliati

#### EnvironmentManager (`behavior_integration/pipeline/environment_manager.py`)

Gestisce il ciclo di vita di OmniGibson:

- **`initialize_omnigibson()`**: Inizializzazione one-time (~5 min)
  - Pre-warming CuRobo per RTX 5080
  - Configurazione GPU dynamics
  - Lancio kernel OmniGibson

- **`create_environment(scene, task, robot)`**: Creazione/riutilizzo ambiente
  - Configurazione robot (Tiago/R1)
  - Setup sensori esterni (multi-view)
  - Configurazione task BEHAVIOR

- **`reset_episode(warmup_steps)`**: Reset per nuovo episodio
  - Reset ambiente
  - Warmup simulation steps
  - Logging posizione robot

#### CameraController (`behavior_integration/camera/camera_control.py`)

Controlla l'orientamento della head camera del robot:

- **`orient_camera(head_pan, head_tilt)`**: Imposta angoli pan/tilt
- **`look_at_object(obj)`**: Orienta camera verso un oggetto specifico
- **`debug_camera_orientations()`**: Salva 4 screenshot con diverse orientazioni

#### BTExecutor (`behavior_integration/pipeline/bt_executor.py`)

Esegue Behavior Trees in simulazione:

- **`execute(bt_xml, obs)`**: Loop principale di esecuzione
  - Parsing XML del BT
  - Creazione PALPrimitiveBridge
  - Tick loop fino a SUCCESS/FAILURE
  - Screenshot dopo ogni primitiva (se abilitato)

#### PALPrimitiveBridge (`embodied_bt_brain/runtime/primitive_bridge.py`)

Bridge tra BT e primitive di OmniGibson:

- **NAVIGATE_TO**: Navigazione verso oggetto (symbolic: teleport)
- **GRASP**: Afferrare oggetto
- **RELEASE**: Rilasciare oggetto
- **PLACE_ON_TOP**: Posizionare sopra superficie
- **PLACE_INSIDE**: Posizionare dentro contenitore
- **OPEN/CLOSE**: Aprire/chiudere contenitori
- **TOGGLE_ON/OFF**: Accendere/spegnere dispositivi

---

## 3. Modalità di Esecuzione

### 3.1 Modalità BT Predefiniti (`--bt`)

Esegue un BT template senza bisogno di VLM. Ideale per test e validazione.

```bash
./run_bt_test.sh --bt tidying_bedroom_book --task tidying_bedroom --step-screenshots --multi-view
```

**Caratteristiche:**
- Non richiede `--colab-url`
- Screenshot iniziale automatico
- Orientamento camera automatico basato sul task

### 3.2 Modalità Istruzione Singola (`--instruction`)

Genera ed esegue BT da una singola istruzione. Richiede VLM.

```bash
./run_continuous_pipeline.sh --instruction "bring water to the coffee table" \
    --task bringing_water --colab-url http://localhost:7860
```

### 3.3 Modalità Batch (`--batch`)

Esegue multiple istruzioni da file. Richiede VLM.

```bash
./run_continuous_pipeline.sh --batch tasks.txt --colab-url http://localhost:7860
```

**Formato file tasks.txt:**
```
instruction | task_name | [retries]
bring water to counter | bringing_water | 3
tidy the bedroom | tidying_bedroom
```

### 3.4 Modalità Interactive (`--interactive`)

Prompt interattivo per inserire istruzioni. Richiede VLM.

```bash
./run_continuous_pipeline.sh --interactive --colab-url http://localhost:7860
```

### 3.5 Modalità Interactive Control (`--interactive-control`)

Menu-driven control durante la simulazione. Permette di:
- Regolare pan/tilt camera
- Catturare screenshot
- Generare BT da VLM o selezionare predefiniti
- Eseguire BT con video recording

```bash
./run_bt_test.sh --bt tidying_bedroom_book --task tidying_bedroom --interactive-control
```

**Menu disponibile:**
```
[1] Adjust head PAN      [2] Adjust head TILT
[3] Take screenshot      [4] Multi-view screenshot
[5] Change instruction   [6] Reset episode
[7] Generate/Select BT   [8] Execute BT
[9] Save state           [0] Quit
```

---

## 4. BT Templates Predefiniti

### test_navigate
**Scopo:** Verifica avvio OmniGibson e navigazione base

```xml
<Sequence>
  <Action ID="NAVIGATE_TO" obj="bed"/>
</Sequence>
```

### test_grasp
**Scopo:** Verifica navigazione + manipolazione

```xml
<Sequence>
  <Action ID="NAVIGATE_TO" obj="hardback"/>
  <Action ID="GRASP" obj="hardback"/>
</Sequence>
```

### tidying_bedroom_book
**Scopo:** Task completo - spostare libro dal letto al nightstand

```xml
<Sequence>
  <Action ID="NAVIGATE_TO" obj="hardback"/>
  <Action ID="GRASP" obj="hardback"/>
  <Action ID="NAVIGATE_TO" obj="nightstand"/>
  <Action ID="PLACE_ON_TOP" obj="nightstand"/>
</Sequence>
```

**Obiettivo BDDL:** `book ON TOP nightstand` (inizialmente `book ON bed`)

### bringing_water_one
**Scopo:** Task con OPEN/CLOSE - bottiglia dal frigo al coffee_table

```xml
<Sequence>
  <Action ID="NAVIGATE_TO" obj="fridge"/>
  <Action ID="OPEN" obj="fridge"/>
  <Action ID="NAVIGATE_TO" obj="bottle"/>
  <Action ID="GRASP" obj="bottle"/>
  <Action ID="NAVIGATE_TO" obj="coffee_table"/>
  <Action ID="PLACE_ON_TOP" obj="coffee_table"/>
  <Action ID="NAVIGATE_TO" obj="fridge"/>
  <Action ID="CLOSE" obj="fridge"/>
</Sequence>
```

**Obiettivo BDDL:** `bottle ON TOP coffee_table` AND `fridge CLOSED`

### picking_up_toys_one
**Scopo:** Task con PLACE_INSIDE - board_game nel toy_box

```xml
<Sequence>
  <Action ID="NAVIGATE_TO" obj="board_game"/>
  <Action ID="GRASP" obj="board_game"/>
  <Action ID="NAVIGATE_TO" obj="toy_box"/>
  <Action ID="PLACE_INSIDE" obj="toy_box"/>
</Sequence>
```

### storing_food_one
**Scopo:** Task completo con OPEN + PLACE_INSIDE - chips nel cabinet

```xml
<Sequence>
  <Action ID="NAVIGATE_TO" obj="cabinet"/>
  <Action ID="OPEN" obj="cabinet"/>
  <Action ID="NAVIGATE_TO" obj="bag_of_chips"/>
  <Action ID="GRASP" obj="bag_of_chips"/>
  <Action ID="NAVIGATE_TO" obj="cabinet"/>
  <Action ID="PLACE_INSIDE" obj="cabinet"/>
  <Action ID="CLOSE" obj="cabinet"/>
</Sequence>
```

---

## 5. Sistema Multi-View

### Abilitazione

```bash
--multi-view    # Abilita camere esterne
```

### Viste Disponibili

| Vista | Posizione | Orientamento | Descrizione |
|-------|-----------|--------------|-------------|
| **head** | Testa robot | Controllata da pan/tilt | Vista POV del robot |
| **birds_eye** | 2m sopra robot | Guarda in basso | Vista dall'alto della stanza |
| **follow_cam** | 1.2m dietro, 1m sopra | Guarda avanti (~30°) | Terza persona da dietro |
| **front_view** | 1.5m davanti, 1.2m sopra | Guarda indietro (~30°) | Vista frontale del robot |

### Configurazione Camere (environment_manager.py)

```python
# birds_eye: Vista dall'alto (indoor-friendly)
"position": [0.0, 0.0, 2.0],   # 2m sopra (dentro soffitti ~2.5m)
"orientation": [0.707, 0.0, 0.0, 0.707],  # Guarda in basso

# follow_cam: Terza persona
"position": [-1.2, 0.0, 1.0],  # 1.2m dietro, 1m sopra
"orientation": [0.0, 0.26, 0.0, 0.966],   # ~30° verso il basso

# front_view: Vista frontale
"position": [1.5, 0.0, 1.2],   # 1.5m davanti, 1.2m sopra
"orientation": [0.0, -0.26, 0.0, 0.966],  # ~30° verso l'alto
```

### Screenshot Automatici

Con `--step-screenshots` abilitato:

1. **Screenshot INIZIALE** (prima del BT):
   - `ep_step00_INITIAL_head.png`
   - `ep_step00_INITIAL_birds_eye.png`
   - `ep_step00_INITIAL_follow_cam.png`
   - `ep_step00_INITIAL_front_view.png`
   - `ep_step00_INITIAL_composite.png` (griglia 2x2)

2. **Screenshot per ogni PRIMITIVA**:
   - `ep_step01_NAVIGATE_TO_hardback_ok_head.png`
   - `ep_step01_NAVIGATE_TO_hardback_ok_composite.png`
   - ... (per ogni azione)

### Composite Image

Layout griglia 2x2 (512x512 per cella):

```
┌─────────────┬─────────────┐
│  birds_eye  │  front_view │
├─────────────┼─────────────┤
│  follow_cam │    head     │
└─────────────┴─────────────┘
```

---

## 6. Configurazione Rendering

### Preset Qualità

| Preset | SPP | Denoiser | TAA | Render Mode | Note |
|--------|-----|----------|-----|-------------|------|
| `turbo` | 1 | 0.0 (full) | on | RayTracedLighting | Velocissimo, bassa qualità |
| `fast` | 8 | 0.2 | on | RayTracedLighting | **Default**, buon compromesso |
| `balanced` | 32 | 0.09 | on | PathTracing | Qualità media |
| `high` | 128 | 0.05 | on | PathTracing | Alta qualità, lento |
| `sharp` | 64 | 0.5 | **off** | PathTracing | Nitido, meno blur |
| `ultra_sharp` | 128 | 0.8 | **off** | PathTracing | Massima nitidezza |

### Utilizzo

```bash
--render-quality fast        # Default
--render-quality sharp       # Per immagini più nitide
--render-quality ultra_sharp # Massima qualità
```

### Denoiser

Il denoiser OptiX riduce il rumore ma può causare sfocatura:

```bash
--enable-denoiser    # Default: abilita denoiser
--no-denoiser        # Disabilita (più rumore ma nitido)
```

### Quando Usare Cosa

- **Test rapidi**: `--render-quality turbo`
- **Sviluppo normale**: `--render-quality fast` (default)
- **Screenshot per documentazione**: `--render-quality sharp` o `ultra_sharp`
- **Immagini sfocate**: Usare `sharp` o `ultra_sharp` che disabilitano TAA

---

## 7. Task BEHAVIOR Supportate

### tidying_bedroom

**Descrizione:** Riordinare la camera da letto
**Scene:** `house_single_floor`
**Oggetti coinvolti:**
- `hardback` (libro) - da spostare
- `bed` - posizione iniziale
- `nightstand` - destinazione

**Obiettivo BDDL:**
```
(ontop hardback nightstand)
```

### bringing_water

**Descrizione:** Portare acqua dal frigo al tavolo
**Scene:** `house_single_floor`
**Oggetti coinvolti:**
- `bottle` (bottiglia d'acqua)
- `fridge` - contenitore iniziale
- `coffee_table` - destinazione

**Obiettivo BDDL:**
```
(ontop bottle coffee_table)
(closed fridge)
```

### picking_up_toys

**Descrizione:** Raccogliere giocattoli
**Scene:** `house_single_floor`
**Oggetti coinvolti:**
- `board_game` (gioco da tavolo)
- `toy_box` - contenitore destinazione

**Obiettivo BDDL:**
```
(inside board_game toy_box)
```

### storing_food

**Descrizione:** Conservare cibo nella dispensa
**Scene:** `house_single_floor`
**Oggetti coinvolti:**
- `bag_of_chips` (patatine)
- `cabinet` - contenitore destinazione

**Obiettivo BDDL:**
```
(inside bag_of_chips cabinet)
(closed cabinet)
```

---

## 8. Orientamento Automatico Camera

### Funzionamento

Prima di catturare lo screenshot iniziale, il sistema:

1. **Parsing dell'istruzione/task** per trovare keyword
2. **Mapping keyword → categorie oggetti**
3. **Ricerca oggetto nella scena**
4. **Orientamento head camera** verso l'oggetto trovato

### Mapping Keyword → Oggetti

```python
keyword_mappings = {
    # Keyword → possibili categorie/nomi oggetti
    'water': ['water', 'bottle', 'glass', 'cup'],
    'drink': ['bottle', 'glass', 'cup', 'water'],
    'book': ['book', 'hardback', 'paperback', 'novel'],
    'tidy': ['book', 'hardback', 'clothes', 'toy'],
    'table': ['table', 'coffee_table', 'nightstand', 'desk'],
    'bed': ['bed'],
    'shelf': ['shelf', 'bookshelf'],
    'food': ['apple', 'banana', 'bread', 'plate'],
    'fruit': ['apple', 'banana', 'orange'],
    'clean': ['sponge', 'cloth', 'towel'],
    'bedroom': ['book', 'hardback', 'pillow', 'clothes'],
    'kitchen': ['cup', 'plate', 'bottle', 'food'],
    'living': ['remote', 'cushion', 'book'],
}
```

### Esempio

Per `--task tidying_bedroom`:
1. Parsing: "tidying bedroom" → keyword "bedroom" e "tidy"
2. Mapping: "bedroom" → ['book', 'hardback', 'pillow', 'clothes']
3. Ricerca: trova `hardback_188` nella scena
4. Orientamento: camera punta verso il libro

---

## 9. Struttura Directory Output

### Layout

```
multimodal-bt-generation/
├── debug_images/
│   └── {bt_name}_{task}/           # Es: tidying_bedroom_book_tidying_bedroom
│       └── {timestamp}/            # Es: 20260128_114356
│           ├── ep_step00_INITIAL_head.png
│           ├── ep_step00_INITIAL_birds_eye.png
│           ├── ep_step00_INITIAL_follow_cam.png
│           ├── ep_step00_INITIAL_front_view.png
│           ├── ep_step00_INITIAL_composite.png
│           ├── ep_step01_NAVIGATE_TO_hardback_ok_head.png
│           ├── ep_step01_NAVIGATE_TO_hardback_ok_composite.png
│           ├── ep_step02_GRASP_hardback_ok_*.png
│           ├── ep_step03_NAVIGATE_TO_nightstand_ok_*.png
│           └── ep_step04_PLACE_ON_TOP_nightstand_ok_*.png
│
├── debug_logs/
│   ├── bt_test_20260128_114356.log     # Log completo
│   └── results_20260128_114356.json    # Risultati JSON
│
└── run_bt_test.sh                       # Script di avvio
```

### Convenzione Nomi File

```
ep_step{NN}_{ACTION}_{target}_{result}_{view}.png

Esempi:
- ep_step00_INITIAL_head.png           # Screenshot iniziale, head camera
- ep_step01_NAVIGATE_TO_hardback_ok_head.png  # Step 1, successo
- ep_step02_GRASP_bottle_fail_composite.png   # Step 2, fallimento
```

---

## 10. Riferimento Completo Opzioni CLI

### Sorgente Episodi (mutually exclusive)

| Opzione | Descrizione | Richiede VLM |
|---------|-------------|--------------|
| `--bt <template>` | BT predefinito | No |
| `--instruction "..."` | Singola istruzione | Sì |
| `--batch <file>` | File batch | Sì |
| `--interactive` | Prompt interattivo | Sì |

### Configurazione Ambiente

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `--scene` | `house_single_floor` | Modello scena |
| `--task` | `bringing_water` | Nome task BEHAVIOR |
| `--robot` | `Tiago` | Tipo robot (Tiago/R1) |
| `--activity-definition-id` | `0` | ID definizione attività |
| `--activity-instance-id` | `0` | ID istanza attività |

### Configurazione Esecuzione

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `--symbolic` | `False` | Primitive simboliche (teleport) |
| `--max-ticks` | `1000` | Max tick BT |
| `--warmup-steps` | `50` | Step warmup simulazione |
| `--retries` | `1` | Tentativi per istruzione |

### Configurazione VLM

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `--colab-url` | `None` | URL server Gradio VLM |
| `--temperature` | `0.3` | Temperatura generazione |
| `--allowed-actions` | `NAVIGATE_TO,...` | Azioni permesse |
| `--on-demand-mapping` | `True` | Risolvi nomi oggetti on-demand |

### Display

| Opzione | Descrizione |
|---------|-------------|
| `--headless` | Nessuna finestra UI |
| `--show-window` | Mostra finestra viewer |

### Camera

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `--head-tilt` | `0.0` | Angolo tilt (negativo=guarda giù) |
| `--head-pan` | `1.57` | Angolo pan (π/2 = 90° destra) |
| `--debug-camera` | `False` | Salva 4 orientazioni debug |

### Rendering

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `--render-quality` | `fast` | Preset qualità |
| `--enable-denoiser` | `True` | Abilita OptiX denoiser |
| `--no-denoiser` | - | Disabilita denoiser |
| `--samples-per-pixel` | `None` | Override SPP |

### Multi-View e Debug

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `--multi-view` | `False` | Abilita camere esterne |
| `--step-screenshots` | `False` | Screenshot dopo ogni primitiva |
| `--dump-objects` | `None` | Dump oggetti matching pattern |

### Controllo Interattivo

| Opzione | Descrizione |
|---------|-------------|
| `--interactive-control` | Menu durante simulazione |

---

## 11. Esempi Pratici

### Test Base - Verifica Avvio

```bash
./run_bt_test.sh --bt test_navigate --task tidying_bedroom
```

### Task Completo con Screenshot

```bash
./run_bt_test.sh --bt tidying_bedroom_book \
    --task tidying_bedroom \
    --step-screenshots \
    --multi-view
```

### Alta Qualità per Documentazione

```bash
./run_bt_test.sh --bt tidying_bedroom_book \
    --task tidying_bedroom \
    --step-screenshots \
    --multi-view \
    --render-quality sharp
```

### Debug Interattivo

```bash
./run_bt_test.sh --bt tidying_bedroom_book \
    --task tidying_bedroom \
    --interactive-control \
    --multi-view
```

### Task con VLM

```bash
./run_continuous_pipeline.sh \
    --instruction "bring the bottle from the fridge to the coffee table" \
    --task bringing_water \
    --colab-url http://localhost:7860 \
    --step-screenshots \
    --multi-view
```

### Batch Processing

```bash
# Crea file tasks.txt
cat > tasks.txt << EOF
tidy the book on the nightstand | tidying_bedroom | 2
bring water to the table | bringing_water | 3
EOF

# Esegui batch
./run_continuous_pipeline.sh --batch tasks.txt --colab-url http://localhost:7860
```

---

## 12. Troubleshooting

### Screenshot Neri o Rumorosi

**Problema:** Le immagini sono nere, rumorose o sfocate

**Soluzione:**
```bash
# Per immagini più nitide
--render-quality sharp

# Per massima qualità
--render-quality ultra_sharp --no-denoiser
```

### Camere Esterne Fuori dalla Stanza

**Problema:** birds_eye/follow_cam mostrano l'esterno invece dell'interno

**Causa:** Posizioni camere troppo lontane (configurazione precedente)

**Soluzione:** Già corretto - le camere ora sono più vicine:
- birds_eye: 2m sopra (era 4m)
- follow_cam: 1.2m dietro, 1m sopra (era 2m, 2m)
- front_view: 1.5m davanti (era 2.5m)

### Head Camera Non Cattura

**Problema:** Screenshot head è nero nell'INITIAL

**Soluzione:** Verificare che venga usato `env.get_obs()` invece di `robot.sensors`

### Oggetti Non Trovati

**Problema:** "[OBJECT] No objects found matching..."

**Cause possibili:**
1. Nome oggetto errato nel BT
2. Oggetto dentro contenitore chiuso
3. Task/scene non compatibili

**Soluzione:**
```bash
# Usa on-demand mapping (default)
--on-demand-mapping

# Lista oggetti nella scena
--dump-objects "*"
```

### CUDA/GPU Errors

**Problema:** CUDA error 700 o simili

**Soluzioni:**
1. Usare `--symbolic` per evitare motion planning
2. Verificare variabili ambiente:
```bash
export OMNIGIBSON_CUROBO_USE_CUDA_GRAPH=0
export PYTORCH_ALLOC_CONF=expandable_segments:True
```

---

## Changelog

- **2026-01-29**: Prima versione documentazione completa
- **2026-01-28**: Aggiunta modalità `--bt` con BT predefiniti
- **2026-01-28**: Aggiunto sistema multi-view con camere indoor-friendly
- **2026-01-28**: Aggiunto orientamento automatico camera basato su keyword
