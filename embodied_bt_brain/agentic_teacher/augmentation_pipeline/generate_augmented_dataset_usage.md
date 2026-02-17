# Generate Augmented Dataset - Usage Guide

Script per creare versioni aumentate di esempi BT aggiungendo decoratori (retry, timeout, fallback, condition, subtree).

## Comandi Disponibili

### Argomenti Base

| Argomento | Default | Descrizione |
|-----------|---------|-------------|
| `--input-dir` | `dataset_agentic` | Directory del dataset di input |
| `--output-dir` | `dataset_agentic_augmented` | Directory del dataset di output |
| `--max-train` | `735` | Numero massimo di augmentazioni per il train set (50% di 1470) |
| `--max-val` | `76` | Numero massimo di augmentazioni per il validation set (50% di 152) |

### Controllo Esecuzione

| Argomento | Default | Descrizione |
|-----------|---------|-------------|
| `--parallel` | `1` | Numero di workers paralleli (min: 1, max: 5) |
| `--dry-run` | `False` | Mostra cosa verrebbe processato senza effettuare modifiche |
| `--limit` | `None` | Limita il numero totale di episodi da processare (utile per testing) |
| `--no-resume` | `False` | Non salta gli episodi già processati (ricomincia da zero) |
| `--fail-fast` | `False` | Ferma l'esecuzione al primo errore |

### Configurazione LLM

| Argomento | Default | Descrizione |
|-----------|---------|-------------|
| `--model` | `None` | Modello LLM da usare (se non specificato, usa quello dall'environment) |
| `--seed` | `42` | Seed random per riproducibilità |

### Output e Logging

| Argomento | Default | Descrizione |
|-----------|---------|-------------|
| `--tqdm` | `False` | Mostra progress bar durante l'esecuzione |
| `--log-every` | `50` | Logga il progresso ogni N items processati |
| `--dump-intermediate-steps` | `False` | Aggiunge selection.json alle directory steps_dump (stessa struttura di dataset_agentic) |

---

## Esempi di Utilizzo

### 1. Dry Run - Test rapido
Vedere cosa verrebbe processato senza effettuare modifiche:
```bash
python generate_augmented_dataset.py --dry-run --limit 50
```

### 2. Esecuzione Standard
Esecuzione con valori di default (735 train, 76 val):
```bash
python generate_augmented_dataset.py
```

### 3. Esecuzione con Progress Bar
```bash
python generate_augmented_dataset.py --tqdm
```

### 4. Esecuzione Parallela
Usare 3 workers paralleli per velocizzare:
```bash
python generate_augmented_dataset.py --parallel 3
```

### 5. Esecuzione Parallela Massima con Progress Bar
```bash
python generate_augmented_dataset.py --parallel 5 --tqdm
```

### 6. Test Limitato
Processare solo 10 episodi per testing:
```bash
python generate_augmented_dataset.py --limit 10 --tqdm
```

### 7. Ricominciare da Zero
Non riprendere da episodi già processati:
```bash
python generate_augmented_dataset.py --no-resume
```

### 8. Debug con Fail Fast
Fermarsi al primo errore per debugging:
```bash
python generate_augmented_dataset.py --fail-fast --limit 20
```

### 9. Custom Train/Val Limits
Specificare limiti personalizzati:
```bash
python generate_augmented_dataset.py --max-train 500 --max-val 50
```

### 10. Custom Input/Output Directories
```bash
python generate_augmented_dataset.py --input-dir my_dataset --output-dir my_augmented
```

### 11. Specificare Modello LLM
```bash
python generate_augmented_dataset.py --model gpt-4o
```

### 12. Seed Diverso per Riproducibilità
```bash
python generate_augmented_dataset.py --seed 123
```

### 13. Logging Frequente
Log ogni 10 items invece di 50:
```bash
python generate_augmented_dataset.py --log-every 10 --tqdm
```

### 14. Produzione Completa
Esecuzione completa per produzione:
```bash
python generate_augmented_dataset.py --max-train 735 --max-val 76 --parallel 3 --tqdm
```

### 15. Quick Validation Test
Test rapido per validare il setup:
```bash
python generate_augmented_dataset.py --dry-run --limit 5 --max-train 3 --max-val 2
```

### 16. Debug con Dump Intermediate Steps
Aggiunge selection.json con info sul decoratore scelto:
```bash
python generate_augmented_dataset.py --dump-intermediate-steps --limit 5 --tqdm
```

### 17. Debug Completo
Combinare fail-fast con intermediate steps per debug dettagliato:
```bash
python generate_augmented_dataset.py --dump-intermediate-steps --fail-fast --limit 10
```

### 18. Ispezione Singolo Episodio
Processare un singolo episodio con tutti i dettagli:
```bash
python generate_augmented_dataset.py --dump-intermediate-steps --limit 1 --no-resume
```

---

## Output

Lo script genera (stessa struttura di `dataset_agentic`):
- `{output-dir}/planned_episodes.json` - **Manifest degli episodi pianificati** (creato prima di iniziare)
- `{output-dir}/train/data.jsonl` - Record aumentati per training
- `{output-dir}/val/data.jsonl` - Record aumentati per validation
- `{output-dir}/train/steps_dump/train/{dataset_id}/{episode_id}/` - Prompt e BT modificati
- `{output-dir}/val/steps_dump/train/{dataset_id}/{episode_id}/` - Prompt e BT modificati
- `{output-dir}/train/images/{dataset_id}/{episode_id}/` - Symlink alle immagini (frame1.jpg, contact_sheet.jpg)
- `{output-dir}/val/images/{dataset_id}/{episode_id}/` - Symlink alle immagini (frame1.jpg, contact_sheet.jpg)
- `{output-dir}/stats/augmentation_stats.json` - Statistiche di augmentation
- `{output-dir}/stats/manifest.json` - Manifest dell'esecuzione

### Struttura steps_dump (identica a dataset_agentic)

Ogni episodio in `{split}/steps_dump/train/{dataset_id}/{episode_id}/`:
- `contact_sheet.jpg` - Symlink al contact sheet originale
- `instruction.txt` - Istruzione modificata
- `prompt.md` - Prompt modificato per l'LLM
- `steps/02_conformance.xml` - BT XML modificato

### Con `--dump-intermediate-steps`

Quando attivato, aggiunge `selection.json` alla directory dell'episodio:
- `{output-dir}/{split}/steps_dump/train/{dataset_id}/{episode_id}/selection.json` - Info sulla selezione del decoratore (tipo, target, parametri)

---

## Manifest degli Episodi Pianificati

Prima di iniziare l'elaborazione, lo script scrive `planned_episodes.json` contenente:
- Lista completa degli episodi che verranno processati
- Parametri usati per la selezione (seed, max_train, max_val, ecc.)
- Timestamp di creazione

**Struttura del manifest:**
```json
{
  "created_at": "2024-01-15T10:30:00",
  "args": {
    "input_dir": "dataset_agentic",
    "output_dir": "dataset_agentic_augmented",
    "max_train": 735,
    "max_val": 76,
    "seed": 42
  },
  "total_planned": 811,
  "train_count": 735,
  "val_count": 76,
  "episodes": [
    {"dataset_id": "...", "episode_id": "...", "instruction": "...", "split": "train"},
    ...
  ]
}
```

**Vantaggi:**
- Resume riproducibile: al riavvio processa gli stessi episodi del run originale
- Tracciabilità: sai esattamente quali episodi sono stati selezionati
- Debug: puoi ispezionare la lista prima di processare

---

## Note

- **Frame1 per augmented**: Gli episodi augmented usano `frame1.jpg` come student image (gli episodi lineari usano `frame0.jpg`). Questo evita conflitti durante il training (stessa immagine con BT diversi).
- Il resume automatico usa il manifest per garantire riproducibilità
- Il resume salta episodi già processati (usa `--no-resume` per disabilitare)
- Ctrl+C una volta termina gracefully l'episodio corrente, due volte forza l'uscita
- I decoratori supportati sono: retry, timeout, fallback, condition, subtree (e combinazioni mixed)
- `--dump-intermediate-steps` è utile per debug e per ispezionare cosa fa l'LLM
