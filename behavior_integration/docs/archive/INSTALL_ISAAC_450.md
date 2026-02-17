# 🚀 Guida Installazione Isaac Sim 4.5.0

## Metodo 1: NVIDIA Omniverse Launcher (CONSIGLIATO)

### Passo 1: Scarica Omniverse Launcher

Apri il browser e vai su:
```
https://www.nvidia.com/en-us/omniverse/download/
```

Clicca su **"Download Launcher"** per Linux

### Passo 2: Installa il Launcher

```bash
cd ~/Downloads
# Trova il file scaricato (es: omniverse-launcher-linux.AppImage)
chmod +x omniverse-launcher-linux.AppImage
./omniverse-launcher-linux.AppImage
```

### Passo 3: Nel Launcher

1. **Login**: Crea account NVIDIA (gratuito) o fai login
2. **Exchange Tab**: Clicca sulla tab "Exchange"
3. **Cerca Isaac Sim**: Scrivi "Isaac Sim" nella barra di ricerca
4. **Seleziona versione**: Scegli **"Isaac Sim 4.5.0"**
5. **Install**: Clicca sul pulsante "Install"
6. **Aspetta**: Download + installazione (~20-30 minuti, ~10GB)

### Passo 4: Verifica Installazione

```bash
ls ~/.local/share/ov/pkg/isaac-sim-4.5.0
```

Se vedi la cartella, sei pronto! ✅

---

## Metodo 2: Download Diretto (ALTERNATIVO)

Se Omniverse Launcher non funziona:

### Passo 1: Account NVIDIA

1. Vai su: https://developer.nvidia.com/isaac-sim
2. Fai login o crea account NVIDIA Developer (gratuito)

### Passo 2: Download

1. Nella pagina Isaac Sim, cerca **"Isaac Sim 4.5.0"**
2. Clicca su **"Download"** per Linux
3. Salva il file (es: `isaac-sim-4.5.0-linux.tar.gz`)

### Passo 3: Estrai e Installa

```bash
cd ~/Downloads
# Estrai l'archivio
tar -xzf isaac-sim-4.5.0-linux.tar.gz

# Sposta nella posizione corretta
mkdir -p ~/.local/share/ov/pkg
mv isaac-sim-4.5.0 ~/.local/share/ov/pkg/

# Verifica
ls ~/.local/share/ov/pkg/isaac-sim-4.5.0
```

---

## 🎯 Dopo l'Installazione: LANCIA IL TUO SOGNO!

Una volta completata l'installazione:

```bash
cd /home/cristiano/oxe-bt-pipeline

# Imposta il path
export ISAAC_PATH="$HOME/.local/share/ov/pkg/isaac-sim-4.5.0"

# Attiva environment
conda activate vlm

# 🚀 LANCIO COMPLETO!
python run_bt_agent.py \
    --instruction "pick up the apple and place it in the basket" \
    --task cleaning_windows \
    --scene Rs_int \
    --symbolic \
    --show-window \
    --max-ticks 200
```

### Cosa Vedrai:

1. **Step 1**: VLM genera il Behavior Tree (~30s)
   ```
   ✓ VLM loaded successfully!
   ✓ BT generated (1424 chars)
   ```

2. **Step 2**: BT viene parsato
   ```
   ✓ BT parsed successfully!
   Root node: SequenceNode
   ```

3. **Step 3**: OmniGibson si avvia (~60s)
   ```
   ⏳ Launching OmniGibson...
   ⏳ Loading scene (1-2 min)...
   ```

4. **Step 4**: 🎥 **FINESTRA SI APRE!**
   - Vedrai la scena 3D
   - Il robot Fetch
   - Gli oggetti (apple, basket)

5. **Step 5**: 🤖 **ROBOT IN AZIONE!**
   ```
   🚀 Running BT...
   ⏱️  Tick    1: RUNNING
   ⏱️  Tick   25: RUNNING
   ⏱️  Tick   50: SUCCESS
   🎉 SUCCESS after 50 ticks!
   ```

---

## 🔧 Troubleshooting

### Problema: "ISAAC_PATH not found"

**Soluzione**: Aggiungi al tuo `.bashrc`:

```bash
echo 'export ISAAC_PATH="$HOME/.local/share/ov/pkg/isaac-sim-4.5.0"' >> ~/.bashrc
source ~/.bashrc
```

### Problema: "Version mismatch"

**Verifica versione installata**:
```bash
ls ~/.local/share/ov/pkg/
```

Assicurati che ci sia `isaac-sim-4.5.0` (non 4.2.0)

### Problema: Launcher non si apre

**Installa dipendenze**:
```bash
sudo apt-get update
sudo apt-get install libfuse2 libgl1
```

---

## 📊 Installazione in Parallelo (SICURO)

Isaac Sim 4.5.0 verrà installato **insieme** a 4.2.0:

```
~/.local/share/ov/pkg/
├── isaac-sim-comp-check-4.2.0/  ← Vecchia (usata da IsaacLab)
└── isaac-sim-4.5.0/              ← Nuova (usata da BEHAVIOR-1K)
```

Nessun conflitto! Ogni progetto usa la sua versione via `ISAAC_PATH`.

---

## ✅ Quick Check

Dopo l'installazione, verifica tutto funzioni:

```bash
# Test rapido (no simulation)
cd /home/cristiano/oxe-bt-pipeline
conda activate vlm
python -c "
import sys
sys.path.insert(0, '/home/cristiano/BEHAVIOR-1K/OmniGibson')
import omnigibson as og
print('✓ OmniGibson importato correttamente!')
"
```

Se vedi `✓ OmniGibson importato correttamente!`, sei pronto! 🎉

---

## 🎬 Comando Finale - Il Tuo Sogno!

```bash
cd /home/cristiano/oxe-bt-pipeline
export ISAAC_PATH="$HOME/.local/share/ov/pkg/isaac-sim-4.5.0"
conda activate vlm

# Genera BT + Mostra Robot in Azione!
python run_bt_agent.py \
    --instruction "pick up the apple and place it in the basket" \
    --task cleaning_windows \
    --scene Rs_int \
    --symbolic \
    --show-window \
    --max-ticks 200
```

**Questo è il momento che stavi aspettando!** 🚀✨

La finestra si aprirà e vedrai:
- 🏠 La scena 3D
- 🤖 Il robot Fetch  
- 🍎 Gli oggetti
- ⚡ Il robot che esegue il BT generato in tempo reale

**IL TUO SOGNO SI REALIZZERÀ!** 🎉
