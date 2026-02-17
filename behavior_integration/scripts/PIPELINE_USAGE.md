# Pipeline Usage Guide

Guida completa all'uso di `run_continuous_pipeline.py` per l'esecuzione di Behavior Trees in OmniGibson.

---

## Indice

1. [Modalità di Esecuzione](#modalità-di-esecuzione)
2. [BT Predefiniti (No VLM)](#bt-predefiniti-no-vlm)
3. [Interactive Control Mode](#interactive-control-mode)
4. [VLM Mode](#vlm-mode)
5. [Opzioni Camera e Screenshot](#opzioni-camera-e-screenshot)
6. [Opzioni Rendering](#opzioni-rendering)
7. [Video Recording](#video-recording)
8. [Target Inference & Initial Scan](#target-inference--initial-scan)
9. [Debug e Troubleshooting](#debug-e-troubleshooting)
10. [Test Cases Consigliati](#test-cases-consigliati)

---

## Modalità di Esecuzione

Il pipeline supporta 5 modalità mutuamente esclusive:

| Flag | Descrizione | Richiede VLM |
|------|-------------|--------------|
| `--bt <template>` | Esegue BT predefinito | No |
| `--instruction "..."` | Genera BT da istruzione | Sì |
| `--batch <file>` | Esegue batch di task | Sì |
| `--interactive` | Prompt interattivo | Sì |
| (nessuno) | Default: prompt interattivo | Sì |

Aggiungendo `--interactive-control` a qualsiasi modalità si attiva il menu interattivo.

---

## BT Predefiniti (No VLM)

### Template Disponibili

| Template | Task | Descrizione |
|----------|------|-------------|
| `test_navigate` | tidying_bedroom | Solo NAVIGATE_TO bed |
| `test_grasp` | tidying_bedroom | NAVIGATE + GRASP hardback |
| `tidying_bedroom_book` | tidying_bedroom | Libro dal letto al nightstand |
| `bringing_water_one` | bringing_water | Bottiglia dal frigo al coffee_table |
| `picking_up_toys_one` | picking_up_toys | Board game nel toy_box |
| `storing_food_one` | storing_food | Chips nel cabinet |

### Comandi Base

```bash
# Attiva conda environment
conda activate behavior_gpu

# Naviga alla cartella del progetto
cd ~/oxe-bt-pipeline
```

### Test Fase 1: Solo Navigazione
Verifica che OmniGibson si avvia e NAVIGATE_TO funziona.

```bash
./run_continuous_pipeline.sh \
    --bt test_navigate \
    --task tidying_bedroom \
    --symbolic \
    --step-screenshots
```

### Test Fase 2: Navigate + Grasp
Verifica che la manipolazione base funziona.

```bash
./run_continuous_pipeline.sh \
    --bt test_grasp \
    --task tidying_bedroom \
    --symbolic \
    --step-screenshots
```

### Test Fase 3: Task Completo (tidying_bedroom)
Libro dal letto al nightstand - task completo senza OPEN/CLOSE.

```bash
./run_continuous_pipeline.sh \
    --bt tidying_bedroom_book \
    --task tidying_bedroom \
    --symbolic \
    --step-screenshots \
    --multi-view
```

### Test Fase 4: Task con OPEN/CLOSE (bringing_water)
Bottiglia dal frigo al coffee_table - include OPEN/CLOSE frigo.

```bash
./run_continuous_pipeline.sh \
    --bt bringing_water_one \
    --task bringing_water \
    --symbolic \
    --step-screenshots \
    --multi-view
```

### Test Fase 5: PLACE_INSIDE (picking_up_toys)
Board game nel toy_box - test PLACE_INSIDE.

```bash
./run_continuous_pipeline.sh \
    --bt picking_up_toys_one \
    --task picking_up_toys \
    --symbolic \
    --step-screenshots
```

### Test Fase 6: OPEN + PLACE_INSIDE (storing_food)
Chips nel cabinet - OPEN cabinet, PLACE_INSIDE, CLOSE.

```bash
./run_continuous_pipeline.sh \
    --bt storing_food_one \
    --task storing_food \
    --symbolic \
    --step-screenshots
```

---

## Interactive Control Mode

Menu interattivo per controllo camera, screenshot e BT.

### Con BT Predefinito (pre-caricato)

```bash
./run_continuous_pipeline.sh \
    --bt tidying_bedroom_book \
    --task tidying_bedroom \
    --symbolic \
    --interactive-control \
    --multi-view
```

### Senza BT (selezione manuale)

```bash
./run_continuous_pipeline.sh \
    --task tidying_bedroom \
    --symbolic \
    --interactive-control \
    --multi-view
```

### Menu Comandi Interactive Control

```
[1] Adjust head-pan      - Rotazione orizzontale camera
[2] Adjust head-tilt     - Rotazione verticale camera
[3] Single screenshot    - Screenshot dalla head camera
[4] Multi-view screenshot - Screenshot da tutte le camere
[5] Show camera params   - Mostra parametri camera/robot
[6] Change instruction   - Cambia istruzione per VLM
[7] Generate/Select BT   - Genera da VLM o seleziona predefinito
[8] Execute BT           - Esegue il BT caricato
[9] Reset episode        - Reset ambiente
[0] Step simulation      - Avanza N step simulazione
[m] Multi-view toggle    - Abilita/disabilita multi-view
[d] Debug camera         - Salva 4 immagini (front/right/back/left)
[r] Record video         - Registra video
[s] Select scan angle    - Seleziona angolo dalla contact sheet (se --initial-scan)
[v] Sync viewer -> head  - Sincronizza GUI con head camera
[q] Quit                 - Esci
```

---

## VLM Mode

Richiede server VLM attivo (Gradio URL).

### Singola Istruzione

```bash
./run_continuous_pipeline.sh \
    --colab-url "http://YOUR_GRADIO_URL" \
    --instruction "bring the water bottle to the coffee table" \
    --task bringing_water \
    --symbolic \
    --step-screenshots
```

### Interactive con VLM

```bash
./run_continuous_pipeline.sh \
    --colab-url "http://YOUR_GRADIO_URL" \
    --task bringing_water \
    --symbolic \
    --interactive-control \
    --multi-view
```

### Batch Mode

```bash
# Crea file tasks.txt:
# instruction | task_name | [retries]
# bring water to counter | bringing_water | 3
# tidy the bedroom | tidying_bedroom | 2

./run_continuous_pipeline.sh \
    --colab-url "http://YOUR_GRADIO_URL" \
    --batch tasks.txt \
    --symbolic
```

---

## Opzioni Camera e Screenshot

### Head Camera Orientation

```bash
# Default: pan=1.57 (90° destra), tilt=0.0 (orizzontale)
--head-pan 0.0      # Guarda avanti
--head-pan 1.57     # Guarda destra (default)
--head-pan 3.14     # Guarda dietro
--head-pan -1.57    # Guarda sinistra

--head-tilt 0.0     # Orizzontale (default)
--head-tilt -0.3    # Leggermente in basso
--head-tilt -0.6    # Molto in basso (oggetti su tavoli)
```

### Multi-View Cameras

```bash
# Abilita camere esterne (birds_eye, follow_cam, front_view)
--multi-view

# Le camere seguono il robot:
# - birds_eye: 4m sopra, guarda in basso
# - follow_cam: 2m dietro, 2m sopra
# - front_view: 2.5m davanti, guarda il robot
```

### Screenshot Options

```bash
# Salva screenshot dopo ogni primitiva
--step-screenshots

# Output: debug_images/{experiment}_{task}/{timestamp}/
#   ep_step01_NAVIGATE_TO_hardback_ok_composite.png  (2x2 tutte le viste)
#   ep_step01_NAVIGATE_TO_hardback_ok_head.png
#   ep_step01_NAVIGATE_TO_hardback_ok_birds_eye.png
#   ep_step01_NAVIGATE_TO_hardback_ok_follow_cam.png
#   ep_step01_NAVIGATE_TO_hardback_ok_front_view.png
```

---

## Opzioni Rendering

### Quality Presets

```bash
--render-quality turbo       # Più veloce, qualità minima (1 spp)
--render-quality fast        # Default, buon compromesso (8 spp)
--render-quality balanced    # Qualità media (32 spp, PathTracing)
--render-quality high        # Qualità massima, più lento (128 spp)
--render-quality sharp       # Meno blur, immagine nitida (64 spp, no TAA)
--render-quality ultra_sharp # Massima nitidezza (128 spp, denoiser minimo)
```

**Nota:** Se le immagini sembrano sfocate/blended, usare `--render-quality sharp` o `ultra_sharp`.

| Preset | SPP | Denoiser | TAA | Note |
|--------|-----|----------|-----|------|
| turbo | 1 | full | on | Velocissimo ma rumoroso |
| fast | 8 | 0.2 | on | Buon compromesso |
| balanced | 32 | 0.09 | on | Qualità media |
| high | 128 | 0.05 | on | Alta qualità |
| sharp | 64 | 0.5 | off | Nitido, meno blur |
| ultra_sharp | 128 | 0.8 | off | Massima nitidezza |

### CLI Overrides per Rendering

È possibile sovrascrivere singoli parametri del preset selezionato:

```bash
# Samples per pixel (più alto = meno rumore, più lento)
--spp 64

# Denoiser blend: 0.0=full denoiser (blur), 1.0=raw (noise)
--denoiser-blend 0.4

# TAA anti-aliasing (può causare blur/ghosting)
--taa              # Abilita TAA
--no-taa           # Disabilita TAA (più nitido)

# Modalità rendering
--render-mode PathTracing       # Qualità (default per balanced/high)
--render-mode RayTracedLighting # Veloce (default per turbo/fast)

# Risoluzione (override del preset)
--width 1024
--height 1024
```

**Esempio: Preset balanced con override:**

```bash
./run_continuous_pipeline.sh \
    --bt tidying_bedroom_book \
    --task tidying_bedroom \
    --render-quality balanced \
    --spp 64 \
    --denoiser-blend 0.4 \
    --no-taa \
    --width 1024 --height 1024
```

Output atteso:
```
[RTX] Effective settings: spp=64, denoiser_blend=0.4, taa=False, mode=PathTracing, resolution=1024x1024
```

### Denoiser

Il denoiser riduce il rumore ma può causare sfocatura:

```bash
--enable-denoiser    # Abilita OptiX denoiser (default)
--no-denoiser        # Disabilita denoiser (più rumore ma nitido)
```

### Display

```bash
--headless           # Nessuna finestra (server/batch)
--show-window        # Mostra finestra viewer
```

---

## Video Recording

Registrazione automatica degli episodi in video H.264.

### Opzioni Video

```bash
# Abilita registrazione video
--record-video

# FPS del video (default: 10)
--fps 15

# Vista da registrare
--video-view head         # Head camera (default)
--video-view composite    # Griglia 2x2 di tutte le viste
--video-view birds_eye    # Vista dall'alto
--video-view follow_cam   # Camera che segue il robot
--video-view front_view   # Vista frontale

# Directory output (default: debug_images/.../videos/)
--video-outdir /path/to/videos
```

### Sanity Check Automatico

Prima di iniziare la registrazione, il sistema esegue un **sanity check** sui frame:

- Verifica che i frame non siano neri (mean > 10)
- Verifica che non siano sovraesposti (mean < 250)
- Verifica che abbiano dettaglio (std > 15)

Se il sanity check fallisce, la registrazione video viene disabilitata per l'episodio:

```
[SANITY] Head frame: 1024x1024, mean=127.3, std=48.2 ✓
[SANITY] Frame capture validated, proceeding with video recording
```

Oppure:
```
[SANITY] Head frame: mean=2.1, std=0.8 ✗ BLACK FRAME
[VIDEO] Skipping video recording - sanity check failed
```

### Esempio Completo

```bash
./run_continuous_pipeline.sh \
    --bt tidying_bedroom_book \
    --task tidying_bedroom \
    --symbolic \
    --record-video \
    --fps 20 \
    --video-view composite \
    --multi-view
```

Output atteso:
```
[VIDEO] Recording started: view=composite, fps=20, tick_interval=3
[VIDEO] Capturing frame 1 (tick 3)
...
[VIDEO] Recording stopped: 45 frames, 2.25s
[VIDEO] Saved: debug_images/.../videos/ep1_20260129_143022_success.mp4
```

### Output Video

I video vengono salvati in:
```
debug_images/{experiment}_{task}/{timestamp}/videos/
└── ep{N}_{timestamp}_{success|failure}.mp4
```

---

## Target Inference & Initial Scan

Il sistema orienta automaticamente la camera verso oggetti rilevanti per il task.

### Cascade di Target Inference

La ricerca degli oggetti target segue questa priorità:

1. **BDDL Goal Predicates** - Parsing dei goal conditions del task (se disponibili)
2. **TASK_TARGET_MAP** - Mapping manuale task → oggetti target (20 task verificati)
3. **Keyword Heuristic** - Parsing dell'istruzione per parole chiave
4. **360-Scan** - Scansione panoramica (fallback, se `--initial-scan` attivo)

Ogni metodo logga la sua sorgente:
```
[TARGET] Source: task_map (TASK_TARGET_MAP['tidying_bedroom'])
[TARGET] Found in scene: hardback_188 (category: book)
[ORIENT] Targeting hardback_188 at (1.2, 3.4, 0.8)
```

### Task Target Map

Task con mapping verificato:

| Task | Target Objects |
|------|----------------|
| `bringing_water` | bottle, fridge, coffee_table |
| `tidying_bedroom` | hardback, nightstand, bed |
| `picking_up_toys` | board_game, toy_box |
| `storing_food` | bag_of_chips, cabinet |
| `slicing_vegetables` | bell_pepper, chopping_board |
| `sorting_vegetables` | bok_choy, onion, bowl |
| ... | (16+ task supportati) |

### 360-Scan (Fallback)

Se nessun target viene trovato, è possibile abilitare una scansione panoramica:

```bash
# Abilita scansione se nessun target trovato
--initial-scan

# Numero di angoli da scansionare (default: 8)
--scan-angles 8
```

La scansione rispetta i limiti dei joint della testa del robot e salva:
- Immagini individuali per ogni angolo
- Contact sheet per revisione visiva

```
[SCAN] Pan joint limits: [-2.09, 2.09] rad
[SCAN] Capturing 8 angles from -2.09 to +2.09 rad...
[SCAN] Saved 8 frames + contact sheet: debug_images/.../scan_contact_sheet.png
[SCAN] Use --interactive-control to select preferred angle
```

In modalità `--interactive-control`, è possibile selezionare manualmente l'angolo desiderato dalla contact sheet.

### Esempio con Scan

```bash
./run_continuous_pipeline.sh \
    --bt test_navigate \
    --task tidying_bedroom \
    --symbolic \
    --initial-scan \
    --scan-angles 8 \
    --interactive-control
```

---

## Debug e Troubleshooting

### Dump Objects

```bash
# Mostra oggetti matching pattern dopo ogni primitiva
--dump-objects bottle
--dump-objects fridge
--dump-objects "*"  # Tutti gli oggetti
```

### Debug Camera

```bash
# In interactive-control, usa comando [d] per salvare
# 4 immagini con diverse orientazioni head camera
```

### Lista Oggetti Scena

```bash
# In interactive-control, gli oggetti sono listati all'avvio
# Primi 20 + count totale
```

### Symbolic vs Realistic

```bash
--symbolic           # Teleport istantaneo (veloce, per test)
# senza --symbolic   # Motion planning realistico (lento)
```

---

## Test Cases Consigliati

### Sequenza di Test Incrementale

Esegui in ordine per verificare che ogni componente funzioni:

```bash
# 1. Verifica avvio OmniGibson
./run_continuous_pipeline.sh --bt test_navigate --task tidying_bedroom --symbolic --step-screenshots

# 2. Verifica GRASP
./run_continuous_pipeline.sh --bt test_grasp --task tidying_bedroom --symbolic --step-screenshots

# 3. Task completo semplice
./run_continuous_pipeline.sh --bt tidying_bedroom_book --task tidying_bedroom --symbolic --step-screenshots --multi-view

# 4. Task con OPEN/CLOSE
./run_continuous_pipeline.sh --bt bringing_water_one --task bringing_water --symbolic --step-screenshots --multi-view

# 5. Task con PLACE_INSIDE
./run_continuous_pipeline.sh --bt picking_up_toys_one --task picking_up_toys --symbolic --step-screenshots

# 6. Task complesso
./run_continuous_pipeline.sh --bt storing_food_one --task storing_food --symbolic --step-screenshots
```

### Test Interactive Control

```bash
# Con BT pre-caricato, pronto per esecuzione
./run_continuous_pipeline.sh \
    --bt tidying_bedroom_book \
    --task tidying_bedroom \
    --symbolic \
    --interactive-control \
    --multi-view \
    --head-tilt -0.3
```

### Test Completo con Tutte le Opzioni

```bash
./run_continuous_pipeline.sh \
    --bt bringing_water_one \
    --task bringing_water \
    --symbolic \
    --step-screenshots \
    --multi-view \
    --render-quality fast \
    --enable-denoiser \
    --head-pan 1.57 \
    --head-tilt -0.3 \
    --warmup-steps 50 \
    --max-ticks 1000
```

### Test Video Recording

```bash
./run_continuous_pipeline.sh \
    --bt tidying_bedroom_book \
    --task tidying_bedroom \
    --symbolic \
    --record-video \
    --fps 20 \
    --video-view composite \
    --multi-view \
    --step-screenshots
```

Output atteso:
```
[SANITY] Head frame: 1024x1024, mean=127.3, std=48.2 ✓
[VIDEO] Recording started: view=composite, fps=20, tick_interval=3
...
[VIDEO] Saved: debug_images/.../videos/ep1_success.mp4
```

### Test Sharp Rendering con Override

```bash
./run_continuous_pipeline.sh \
    --bt tidying_bedroom_book \
    --task tidying_bedroom \
    --symbolic \
    --render-quality balanced \
    --spp 64 \
    --denoiser-blend 0.4 \
    --no-taa \
    --width 1024 --height 1024 \
    --step-screenshots
```

Output atteso:
```
[RTX] Effective settings: spp=64, denoiser_blend=0.4, taa=False, mode=PathTracing, resolution=1024x1024
```

### Test Initial Scan

```bash
./run_continuous_pipeline.sh \
    --bt test_navigate \
    --task tidying_bedroom \
    --symbolic \
    --initial-scan \
    --scan-angles 8 \
    --interactive-control
```

Output atteso:
```
[TARGET] No BDDL goals accessible, trying task map...
[SCAN] Pan joint limits: [-2.09, 2.09] rad
[SCAN] Saved 8 frames + contact sheet: debug_images/.../scan_contact_sheet.png
```

---

## Output Structure

```
debug_images/
└── {bt_template}_{task}/           # Es: tidying_bedroom_book_tidying_bedroom/
    └── {YYYYMMDD_HHMMSS}/          # Timestamp del run
        ├── ep1_20260129_143022_initial.png        # Screenshot iniziale
        ├── ep1_20260129_143022_bt.xml             # BT generato
        ├── ep1_20260129_143022_bt_mapped.xml      # BT con oggetti mappati
        ├── ep1_20260129_143022_success.png        # Screenshot finale (success)
        │
        ├── ep_step01_NAVIGATE_TO_hardback_ok_composite.png
        ├── ep_step01_NAVIGATE_TO_hardback_ok_head.png
        ├── ep_step01_NAVIGATE_TO_hardback_ok_birds_eye.png
        ├── ep_step01_NAVIGATE_TO_hardback_ok_follow_cam.png
        ├── ep_step01_NAVIGATE_TO_hardback_ok_front_view.png
        ├── ep_step02_GRASP_hardback_ok_composite.png
        └── ...
        │
        ├── scan_00_pan-120.png                    # 360-scan frames (se --initial-scan)
        ├── scan_01_pan-090.png
        ├── ...
        ├── scan_contact_sheet.png                 # Contact sheet per selezione
        │
        └── videos/                                # Video episodi (se --record-video)
            ├── ep1_20260129_143022_success.mp4
            └── ep2_20260129_143145_failure.mp4

debug_logs/
└── session_{timestamp}.log         # Log completo della sessione
```

---

## Quick Reference

```bash
# Test rapido
./run_continuous_pipeline.sh --bt test_navigate --task tidying_bedroom --symbolic

# Task completo con screenshot
./run_continuous_pipeline.sh --bt tidying_bedroom_book --task tidying_bedroom --symbolic --step-screenshots --multi-view

# Interactive control
./run_continuous_pipeline.sh --bt tidying_bedroom_book --task tidying_bedroom --symbolic --interactive-control --multi-view

# Con VLM
./run_continuous_pipeline.sh --colab-url "URL" --instruction "bring water" --task bringing_water --symbolic

# Con video recording
./run_continuous_pipeline.sh --bt tidying_bedroom_book --task tidying_bedroom --symbolic --record-video --fps 15 --video-view composite

# Con rendering overrides
./run_continuous_pipeline.sh --bt tidying_bedroom_book --task tidying_bedroom --symbolic --spp 64 --denoiser-blend 0.4 --no-taa

# Con initial scan (quando target non trovato)
./run_continuous_pipeline.sh --bt test_navigate --task tidying_bedroom --symbolic --initial-scan --scan-angles 8

# Full test con tutte le opzioni nuove
./run_continuous_pipeline.sh \
    --bt tidying_bedroom_book \
    --task tidying_bedroom \
    --symbolic \
    --multi-view \
    --step-screenshots \
    --render-quality sharp \
    --record-video --fps 20 --video-view composite \
    --initial-scan
```

---

## CLI Arguments Reference

### Modalità

| Argomento | Descrizione |
|-----------|-------------|
| `--bt <template>` | Esegue BT predefinito |
| `--instruction "..."` | Genera BT da istruzione (richiede VLM) |
| `--batch <file>` | Esegue batch di task |
| `--interactive` | Prompt interattivo |
| `--interactive-control` | Menu interattivo avanzato |

### Rendering

| Argomento | Descrizione | Default |
|-----------|-------------|---------|
| `--render-quality` | Preset: turbo/fast/balanced/high/sharp/ultra_sharp | fast |
| `--spp` | Samples per pixel (override) | da preset |
| `--denoiser-blend` | Blend denoiser: 0.0=blur, 1.0=raw | da preset |
| `--taa` / `--no-taa` | TAA anti-aliasing | da preset |
| `--render-mode` | PathTracing o RayTracedLighting | da preset |
| `--width` / `--height` | Risoluzione rendering | da preset |
| `--enable-denoiser` | Abilita OptiX denoiser | True |
| `--headless` | Nessuna finestra GUI | False |

### Video Recording

| Argomento | Descrizione | Default |
|-----------|-------------|---------|
| `--record-video` | Abilita registrazione video | False |
| `--fps` | FPS del video | 10 |
| `--video-view` | head/composite/birds_eye/follow_cam/front_view | head |
| `--video-outdir` | Directory output video | debug_images/.../videos/ |

### Camera & Screenshot

| Argomento | Descrizione | Default |
|-----------|-------------|---------|
| `--head-pan` | Rotazione orizzontale camera (rad) | 1.57 |
| `--head-tilt` | Rotazione verticale camera (rad) | 0.0 |
| `--multi-view` | Abilita camere esterne | False |
| `--step-screenshots` | Screenshot dopo ogni primitiva | False |
| `--initial-scan` | Scansione panoramica se no target | False |
| `--scan-angles` | Numero angoli scansione | 8 |

### Execution

| Argomento | Descrizione | Default |
|-----------|-------------|---------|
| `--task` | Nome task BEHAVIOR | tidying_bedroom |
| `--scene` | Nome scena | Rs_int |
| `--robot` | Tipo robot | Tiago |
| `--symbolic` | Teleport invece di motion planning | False |
| `--max-ticks` | Max tick BT execution | 1000 |
| `--warmup-steps` | Step warmup simulazione | 50 |
