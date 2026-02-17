#!/usr/bin/env python3
"""
Raccoglie le instruction come insiemi (set) per un elenco fisso di dataset,
senza passare argomenti da CLI. Produce:

  analysis/instruction_sets.batch1.json
  analysis/instructions_all_unique.batch1.txt

Per passare al secondo batch, rimuovere i commenti sulle righe dei dataset
al fondo dell'array DATASETS (sezione 'BATCH 2') e, opzionalmente, cambiare TAG.
"""

import os
import sys

# Assicura che la repo root sia in sys.path anche quando eseguito da tools/
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from processing._bootstrap import ensure_repo_root
ensure_repo_root()

from pathlib import Path
import json, re

# Radice contenente i dataset già processati (cartelle "out_temp/<dataset>/episode_XXX/")
ROOT = Path("out_temp")

# Auto-discover all datasets in ROOT
DATASETS = [p.name for p in ROOT.iterdir() if p.is_dir()] if ROOT.exists() else []

# Tag fisso per distinguere i file di output.
TAG = "all"

def norm(s: str) -> str:
    """Normalizzazione blanda: trim + collasso di whitespace in singoli spazi."""
    if s is None:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s

def iter_instructions(dataset_dir: Path):
    """Itera le instruction da final_selected/episode_data.json in tutte le episode_* del dataset."""
    for ep in sorted(dataset_dir.glob("episode_*")):
        # Prima prova episode_data.json in final_selected
        data_path = ep / "final_selected" / "episode_data.json"
        if data_path.exists():
            try:
                data = json.loads(data_path.read_text(encoding="utf-8"))
                instr = data.get("instruction", "")
                if instr:
                    yield instr
                    continue
            except Exception:
                pass
        # Fallback: instruction.txt nella root dell'episodio
        txt_path = ep / "instruction.txt"
        if txt_path.exists():
            try:
                yield txt_path.read_text(encoding="utf-8")
            except Exception:
                pass

def collect_unique_instructions(ds_name: str):
    """Legge e deduplica (per stringa normalizzata) le instruction di un dataset."""
    uniq = set()
    ds_dir = ROOT / ds_name
    if not ds_dir.exists():
        return []
    for raw in iter_instructions(ds_dir):
        text = norm(raw)
        if text:
            uniq.add(text)
    return sorted(uniq)

def main():
    if not ROOT.exists():
        raise SystemExit(f"Cartella radice non trovata: {ROOT.resolve()}")

    payload = {}
    global_set = set()

    for name in DATASETS:
        ds_dir = ROOT / name
        if not ds_dir.exists():
            print(f"Avviso: dataset mancante o non trovato: {name}")
            continue
        uniq = collect_unique_instructions(name)
        if not uniq:
            print(f"Nota: nessuna instruction trovata in {name}")
            continue
        payload[name] = uniq
        global_set.update(uniq)

    if not payload:
        raise SystemExit("Nessuna instruction raccolta. Verificare l'array DATASETS e la struttura 'out/<dataset>/episode_XXX/'.")

    payload["_all_unique"] = sorted(global_set)

    out_dir = Path("analysis")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"instruction_sets.{TAG}.json"
    txt_path  = out_dir / f"instructions_all_unique.{TAG}.txt"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_path.write_text("\n".join(payload["_all_unique"]), encoding="utf-8")

    ds_count = len([k for k in payload.keys() if k != "_all_unique"])
    print(f"Creato: {json_path}")
    print(f"Creato: {txt_path}")
    print(f"Dataset coperti: {ds_count} — Istruzioni uniche globali: {len(payload['_all_unique'])}")

if __name__ == "__main__":
    main()
# python tools/collect_instruction_sets.py
