# Multi-View Camera System

Documentazione del sistema di telecamere multi-view per la cattura di immagini da più angolazioni durante l'esecuzione dei task.

## Attivazione

```bash
# Aggiungi --multi-view al comando
./run_continuous_pipeline.sh --bt tidying_bedroom_book --task tidying_bedroom --interactive-control --multi-view
```

## Telecamere Disponibili

### Panoramica Visuale

```
        VISTA DALL'ALTO (stanza)

    (22,22,2.5)
        📷 room_cam ←── FISSA nella stanza (pose_frame: "world")
         \
          \  vista diagonale
           \
            ↘
              🤖 robot (si muove)
             /|\
            / | \
    follow   |   front_view
    _cam  birds_eye

    (queste 3 SEGUONO il robot - pose_frame: "parent")


        VISTA LATERALE

                    birds_eye 📷
                         |
                         | 2.5m sopra
                         ↓
        follow_cam 📷 ← 🤖 → 📷 front_view
           (2m dietro)     (2m davanti)
           (1.5m alto)     (1.2m alto)
```

## Dettaglio Telecamere

### 1. `head` (Robot Camera)
La telecamera negli "occhi" del robot.

| Proprietà | Valore |
|-----------|--------|
| Tipo | Integrata nel robot |
| Risoluzione | 512x512 |
| Posizione | Testa del robot |
| Controllo | `[1]` head_pan, `[2]` head_tilt |

### 2. `birds_eye` (Vista dall'alto)
Vista a volo d'uccello, guarda dritto verso il basso.

| Proprietà | Valore |
|-----------|--------|
| pose_frame | `parent` (segue il robot) |
| Posizione | `[0, 0, 2.5]` - 2.5m sopra il robot |
| Orientamento | `[0.5, 0.5, 0.5, 0.5]` - guarda GIÙ |
| Risoluzione | 512x512 |

```
     📷 birds_eye
      |
      | 2.5m
      ↓
     🤖 robot (sempre centrato)
```

### 3. `follow_cam` (Terza Persona)
Telecamera "videogioco" - segue il robot da dietro.

| Proprietà | Valore |
|-----------|--------|
| pose_frame | `parent` (segue il robot) |
| Posizione | `[-2, 0, 1.5]` - 2m dietro, 1.5m alto |
| Orientamento | `[0, 0, 0, 1]` - guarda AVANTI |
| Risoluzione | 512x512 |

```
    📷 follow_cam
     \
      \  2m
       \
        → 🤖 robot (di spalle)
```

### 4. `front_view` (Vista Frontale)
Telecamera davanti al robot, lo guarda di fronte.

| Proprietà | Valore |
|-----------|--------|
| pose_frame | `parent` (segue il robot) |
| Posizione | `[2, 0, 1.2]` - 2m davanti, 1.2m alto |
| Orientamento | `[0, 0, 1, 0]` - guarda INDIETRO (verso robot) |
| Risoluzione | 512x512 |

```
        🤖 robot (di fronte)
       /
      /  2m
     /
    📷 front_view
```

### 5. `room_cam` (Telecamera Fissa)
Telecamera fissa nella stanza - NON segue il robot.

| Proprietà | Valore |
|-----------|--------|
| pose_frame | `world` (FISSA) |
| Posizione | `[22, 22, 2.5]` - angolo stanza |
| Orientamento | `[0.35, 0.35, 0.61, 0.61]` - diagonale verso centro |
| Risoluzione | 512x512 |
| Nota | Posizione specifica per `tidying_bedroom` |

```
    📷 room_cam (FISSA qui)
     \
      \  vista diagonale
       \
        ↘
         🤖 robot (si muove liberamente)
```

## Comandi Interactive Control

| Comando | Azione |
|---------|--------|
| `[3]` | Screenshot singolo (head camera) → `single/` |
| `[4]` | Screenshot multi-view (tutte le camere) → `multi-view/` |
| `[a]` | **Auto-calibra** tutte le telecamere per guardare il robot |
| `[s]` | Regola posizione/orientamento sensori (manuale) |

## Auto-Calibrazione `[a]` (CONSIGLIATO)

Il comando `[a]` calibra automaticamente tutte le telecamere per guardare verso il robot.
Usa le utility native di OmniGibson (`T.euler2quat`) per calcoli precisi.

```
Command> a

  === AUTO-CALIBRATE CAMERAS ===
  Using OmniGibson transform utilities
  Robot position: [24.50, 23.80, 0.50]
  Target (chest): [24.50, 23.80, 1.50]

  birds_eye: repositioning above robot, looking DOWN
    From: [24.50, 23.80, 3.00]
    To:   [24.50, 23.80, 3.50]

  follow_cam: orienting to look at robot
    From: [22.50, 23.80, 1.50]
    To:   [22.50, 23.80, 1.50]

  Calibrated 4 sensors!
  Take multi-view screenshot [4] to verify.
```

### Cosa fa:
1. **birds_eye**: Si posiziona 3m sopra il robot, guarda dritto GIÙ
2. **Altre telecamere**: Calcola l'orientamento per guardare verso il petto del robot (1m sopra la base)

### Workflow consigliato:
```
1. Lancia con --multi-view
2. [a] Auto-calibra tutte le telecamere
3. [4] Screenshot per verificare
4. [s] Regola manualmente se necessario
5. [4] Screenshot finale
```

## Regolazione Sensori `[s]`

Il comando `[s]` permette di modificare posizione e orientamento di qualsiasi sensore in tempo reale.

### Posizione
```
Enter new position (x y z):
  - Per 'parent': coordinate relative al robot
  - Per 'world': coordinate assolute nella scena
```

### Orientamento (Angoli Euler in gradi)
```
Enter new rotation (roll pitch yaw):
  '0 -90 0'   → guarda dritto GIÙ
  '0 0 0'     → guarda AVANTI (direzione robot)
  '0 0 180'   → guarda INDIETRO
  '0 -45 0'   → guarda 45° verso il basso
  '0 -45 -135'→ diagonale dall'angolo
```

### Tabella Orientamenti Comuni

| Descrizione | Roll | Pitch | Yaw |
|-------------|------|-------|-----|
| Guarda giù (birds_eye) | 0 | -90 | 0 |
| Guarda avanti | 0 | 0 | 0 |
| Guarda indietro | 0 | 0 | 180 |
| Guarda a sinistra | 0 | 0 | 90 |
| Guarda a destra | 0 | 0 | -90 |
| 45° giù + avanti | 0 | -45 | 0 |
| 45° giù + indietro | 0 | -45 | 180 |
| Angolo stanza (diagonale) | 0 | -45 | -135 |

## Struttura Output

```
debug_tasks/mock/tidying_bedroom/20260131_XXXXXX/
├── single/                          # Screenshot singoli [3]
│   ├── single_20260131_143025_001.png
│   └── single_20260131_143030_002.png
├── multi-view/                      # Screenshot multi-view [4]
│   ├── 20260131_143035_head.png
│   ├── 20260131_143035_birds_eye.png
│   ├── 20260131_143035_follow_cam.png
│   ├── 20260131_143035_front_view.png
│   └── 20260131_143035_room_cam.png
├── experiment_1/                    # Prima esecuzione BT [8]
│   ├── post_execution_XXX.png
│   ├── bt_executed.xml
│   ├── mapping.json
│   └── bddl_result.json
└── experiment_2/                    # Seconda esecuzione BT [8]
    └── ...
```

## Configurazione Tecnica

Le telecamere sono configurate in:
- **File**: `behavior_integration/pipeline/environment_manager.py`
- **Sezione**: `env_config["external_sensors"]` (linee 212-270)

### Formato Configurazione

```python
{
    "sensor_type": "VisionSensor",
    "name": "camera_name",
    "relative_prim_path": "/camera_prim",
    "modalities": ["rgb"],
    "sensor_kwargs": {
        "image_height": 512,
        "image_width": 512,
    },
    "position": [x, y, z],           # Posizione
    "orientation": [qx, qy, qz, qw], # Quaternione
    "pose_frame": "parent" | "world" # Segue robot o fissa
}
```

### Differenza `pose_frame`

| Valore | Comportamento | Uso |
|--------|---------------|-----|
| `parent` | Coordinate relative al robot, si muove con lui | birds_eye, follow_cam, front_view |
| `world` | Coordinate assolute nella scena, resta ferma | room_cam |

## Troubleshooting

### Le immagini mostrano angolazioni sbagliate
**Prima prova** `[a]` per auto-calibrare tutte le telecamere.

Se ancora non funziona, usa `[s]` per regolare manualmente:
- `0 -90 0` per guardare dritto giù
- `0 0 0` per guardare avanti

### room_cam mostra stanza sbagliata
La posizione `[22, 22, 2.5]` è specifica per `tidying_bedroom`.
Per altre scene, usa `[s]` per trovare coordinate corrette.

### Telecamera "dentro" un muro
Riduci la distanza dal robot:
- `position: [0, 0, 2.0]` invece di `[0, 0, 3.0]`
- Oppure usa `[s]` per regolare runtime

## Conversione Quaternioni ↔ Euler

Il sistema converte automaticamente tra:
- **Quaternioni** `[x, y, z, w]` - usati internamente
- **Euler** `[roll, pitch, yaw]` in gradi - mostrati all'utente

Formula nel codice: `_quaternion_to_euler()` e `_euler_to_quaternion()` in `interactive_control.py`
