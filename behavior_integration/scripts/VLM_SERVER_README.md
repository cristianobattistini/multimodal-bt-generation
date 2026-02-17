# VLM Server - Behavior Tree Generator

Server Gradio per la generazione di Behavior Trees da immagini usando modelli VLM fine-tuned con LoRA.

## Modelli Supportati

Il server supporta due modelli VLM trainati:

### 1. Qwen2.5-VL-3B
- **Base model**: `unsloth/Qwen2.5-VL-3B-Instruct`
- **LoRA adapter**: `/home/cristiano/lora_models/qwen2dot5-3B-Instruct_bt_lora_08012026`
- **Chat template**: None (usa default)
- **Parametri di inference** (da notebook cell 24):
  - temperature: 0.2
  - min_p: 0.1

### 2. Gemma3-4B Vision
- **Base model**: `unsloth/gemma-3-4b-pt`
- **LoRA adapter**: `/home/cristiano/lora_models/gemma3_4b_vision_bt_lora_08012026`
- **Chat template**: gemma-3 (applicato DOPO LoRA setup)
- **Parametri di inference** (da notebook cell 18, 26):
  - temperature: 0.3
  - min_p: 0.1
  - top_p: 0.95
  - top_k: 64

## Utilizzo

### Lanciare il server con Qwen

```bash
cd /home/cristiano/multimodal-bt-generation
python behavior_integration/scripts/vlm_server.py --model qwen --port 7860
```

### Lanciare il server con Gemma

```bash
cd /home/cristiano/multimodal-bt-generation
python behavior_integration/scripts/vlm_server.py --model gemma --port 7861
```

### Parametri

- `--model`: Scegli tra `qwen` o `gemma` (obbligatorio)
- `--port`: Porta su cui lanciare il server (default: 7860)

## Differenze di Implementazione

### Caricamento Modelli

Il server implementa correttamente il caricamento dei LoRA adapter seguendo i notebook di training:

1. **Load base model** con 4-bit quantization
2. **Setup LoRA architecture** (stesso config del training)
3. **Apply chat template** (solo per Gemma)
4. **Load trained LoRA weights** usando PeftModel
5. **Set to inference mode**

### Processor

I due modelli hanno gestione identica del processor, ma **solo Gemma** richiede il chat template:

- **Qwen**: Usa processor default, NO chat template
- **Gemma**: Applica `get_chat_template(processor, "gemma-3")` DOPO il setup LoRA

Entrambi usano la stessa chiamata al processor:
```python
inputs = processor(
    text=input_text,
    images=image,
    add_special_tokens=False,
    return_tensors="pt"
).to("cuda")
```

### Parametri di Generazione

I parametri sono esattamente quelli dei notebook:

- **Qwen** (notebook cell 24):
  ```python
  temperature=0.2, min_p=0.1
  ```

- **Gemma** (notebook cell 18, 26):
  ```python
  temperature=0.3, min_p=0.1, top_p=0.95, top_k=64
  ```

## Output

Il server genera:
1. **State Analysis**: Analisi semantica dello stato (target, destination, primitives, risks)
2. **BehaviorTree XML**: Piano in formato BehaviorTree.CPP

## Interfaccia Gradio

L'interfaccia web è disponibile su `http://127.0.0.1:<port>` e include:

- Upload immagine (robot camera view)
- Input task instruction
- Slider temperature (opzionale, usa default del modello)
- Output testuale con State Analysis + XML

## Troubleshooting

### LoRA adapter non caricato correttamente

Verifica che:
1. Il path del LoRA adapter esista: `ls -la /home/cristiano/lora_models/`
2. La LoRA architecture setup matchi il training (r=16, lora_alpha=16, etc.)
3. Per Gemma, il chat template sia applicato DOPO il setup LoRA

### Temperature non produce risultati corretti

Usa le temperature di default dai notebook:
- Qwen: 0.2
- Gemma: 0.3

Questi valori sono ottimizzati durante il training e producono output consistenti.

## Note Tecniche

- Il server usa `FastVisionModel.for_inference()` per ottimizzare la generazione
- Streaming output in real-time tramite `TextIteratorStreamer`
- Inference su GPU (cuda)
- 4-bit quantization per efficienza memoria
