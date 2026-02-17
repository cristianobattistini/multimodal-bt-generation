"""
OXE → Triplet Builder (RLDS-aligned) — multi-dataset config.
Usa la semantica OXE: episodi con campo 'steps'.
"""
import os

# Puoi lasciare 'dataset' vuoto quando usi 'datasets'.
dataset  = ""

# Dataset reali (usa questi nomi TFDS; se la tua copia locale è registrata, funzionano).
# In alcuni rilasci i PR2/xarm compaiono come *_converted_externally_to_rlds/0.1.0.
# Se uno dei nomi non viene risolto, prova a sostituirlo con la variante *_converted_externally_to_rlds/0.1.0.
# datasets = [
#     "columbia_cairlab_pusht_real/0.1.0",
#     "utokyo_pr2_opening_fridge/0.1.0",
#     "utokyo_pr2_tabletop_manipulation/0.1.0",
#     "utokyo_xarm_pick_and_place/0.1.0",
#     "cmu_stretch/0.1.0"
# ]
datasets = [
    # "austin_sirius_dataset_converted_externally_to_rlds/0.1.0",
    # "berkeley_autolab_ur5/0.1.0",
    # "bridge/0.1.0",
    # "fractal20220817_data/0.1.0",
    # "jaco_play/0.1.0",
    # "nyu_franka_play_dataset_converted_externally_to_rlds/0.1.0",
    # "stanford_hydra_dataset_converted_externally_to_rlds/0.1.0",
    "stanford_kuka_multimodal_dataset_converted_externally_to_rlds/0.1.0",
]

# Subset rapido per prove (puoi aumentare in seguito)
split = "train[:100%]"

# Output root
out_root = "out_temp"

# Chiavi RLDS di default
image_key = "steps/observation/image"
instruction_key = "natural_language_instruction"

# Override per dataset specifici
dataset_keys = {
    "nyu_rot_dataset_converted_externally_to_rlds/0.1.0": (
        "image",
        None,
    ),
    "imperialcollege_sawyer_wrist_cam/0.1.0": (
        "steps/observation/wrist_image",
        "steps/language_instruction",
    ),
    "tokyo_u_lsmo_converted_externally_to_rlds/0.1.0": (
        "steps/observation/image",
        "steps/language_instruction",
    ),
    "dlr_edan_shared_control_converted_externally_to_rlds/0.1.0": (
        "steps/observation/image",
        "steps/language_instruction",
    ),
    "dlr_sara_pour_converted_externally_to_rlds/0.1.0": (
        "steps/observation/image",
        "steps/language_instruction",
    ),
    "ucsd_pick_and_place_dataset_converted_externally_to_rlds/0.1.0": (
        "steps/observation/image",
        "steps/language_instruction",
    ),
    "ucsd_kitchen_dataset_converted_externally_to_rlds/0.1.0": (
        "steps/observation/image",
        "steps/language_instruction",
    ),
    "utokyo_xarm_bimanual_converted_externally_to_rlds/0.1.0": (
        "steps/observation/image",
        "steps/language_instruction",
    ),
    "utokyo_xarm_pick_and_place/0.1.0": (
        "steps/observation/image",
        "steps/language_instruction",
    ),
    "dlr_sara_grid_clamp_converted_externally_to_rlds/0.1.0": (
        "steps/observation/image",
        "steps/language_instruction",
    ),
    "berkeley_gnm_cory_hall/0.1.0": (
        "steps/observation/image",
        "steps/language_instruction",
    ),
}

# Quanti frame max per episodio (GIF inclusa se ≥2)
max_frames = 1000

# Limite episodi per dataset (fase di prova)
limit_episodes_per_dataset = 200

# Resume: riprendi dall'ultimo episodio già esportato in out_root/<dataset>/episode_XXX
resume_from_existing = True
skip_existing = True
resume_mode = "fill_gaps"  # "append" (vecchio comportamento) | "fill_gaps" (recupera buchi/incompleti)

# Se una cartella episode_### esiste ma non è completa, ricreala per evitare frame "stale"
overwrite_incomplete = True

# Se True, cancella la cartella episodio quando fallisce l'export (utile per retry puliti)
cleanup_failed_episode = False

# Criterio per considerare "completo" un episodio già esportato
episode_complete_phase = "final_selected"

# Se True, ignora CFG.datasets e processa tutti i dataset presenti in tfds_data_dir
discover_local_datasets = False
# Opzionale: regex per filtrare i nomi durante la discovery (es. "rlds")
local_tfds_include_regex = None
# Opzionale: lista/regex per escludere dataset (nome base o "nome/version")
local_tfds_exclude = []
local_tfds_exclude_regex = None

# Parallelismo per scrittura immagini (0/1 = disabilitato)
io_workers = int(os.getenv("OXE_IO_WORKERS", "4"))

# Directory TFDS (usa variabile d'ambiente per evitare hardcode di percorsi host)
# Esempio Windows: TFDS_DATA_DIR=/mnt/c/Users/<USER>/Documents/tensorflow_datasets
tfds_data_dir = os.getenv("TFDS_DATA_DIR", "/home/cristiano/tensorflow_datasets")


# Embedding-based selection
embeds = {
    "mode": "embed_kcenter",      # "embed_kcenter" (default) oppure "k_only"
    "backbone": "mobilenet_v2",   # anche: "efficientnet_b0"
    "img_size": 224,
    "k_slicing": 0.10,              # usa 1 frame ogni 10 come candidati se 100, 1 ogni 5 se 50, ecc.
    "K": 9,                      # quanti frame finali tenere
    "batch_size": 32,
    "include_boundaries": False,   # include primo/ultimo del sottoinsieme
    "force_global_boundaries": False,  # se True, forza anche 0 e T-1 globali
    "cache_embeddings": True
}

export_mode    = "final_only"    # "full" | "final_only"
filename_mode  = "sequential"    # ordina frame_000.jpg, frame_001.jpg, ...
normalize_names = True           # (alias legacy; tenerlo True non fa danni)
prune_only     = True            # in pratica tiene solo final_selected/ anche in "full"
prune_keep     = ["final_selected"]
run_embed_selection = True       # assicurati che sia attivo

def get(key, default=None):
    return globals().get(key, default)
