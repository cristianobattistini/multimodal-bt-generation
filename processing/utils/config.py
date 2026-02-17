"""
OXE → Triplet Builder (RLDS-aligned) — multi-dataset config.
Uses OXE semantics: episodes with 'steps' field.
"""
import os

# You can leave 'dataset' empty when using 'datasets'.
dataset  = ""

# Real datasets (use these TFDS names; if your local copy is registered, they work).
# In some releases, PR2/xarm appear as *_converted_externally_to_rlds/0.1.0.
# If one of the names is not resolved, try replacing it with the *_converted_externally_to_rlds/0.1.0 variant.
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

# Quick subset for testing (increase later if needed)
split = "train[:100%]"

# Output root
out_root = "out_temp"

# Default RLDS keys
image_key = "steps/observation/image"
instruction_key = "natural_language_instruction"

# Overrides for specific datasets
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

# Max frames per episode (GIF included if >=2)
max_frames = 1000

# Episode limit per dataset (testing phase)
limit_episodes_per_dataset = 200

# Resume: pick up from last already exported episode in out_root/<dataset>/episode_XXX
resume_from_existing = True
skip_existing = True
resume_mode = "fill_gaps"  # "append" (old behavior) | "fill_gaps" (recover gaps/incomplete)

# If an episode_### folder exists but is incomplete, recreate it to avoid stale frames
overwrite_incomplete = True

# If True, delete episode folder on export failure (useful for clean retries)
cleanup_failed_episode = False

# Criterion for considering an already exported episode as 'complete'
episode_complete_phase = "final_selected"

# If True, ignore CFG.datasets and process all datasets in tfds_data_dir
discover_local_datasets = False
# Optional: regex to filter names during discovery (e.g. "rlds")
local_tfds_include_regex = None
# Optional: list/regex to exclude datasets (base name or "name/version")
local_tfds_exclude = []
local_tfds_exclude_regex = None

# Parallelism for image writing (0/1 = disabled)
io_workers = int(os.getenv("OXE_IO_WORKERS", "4"))

# TFDS directory (use environment variable to avoid hardcoding host paths)
# Example Windows: TFDS_DATA_DIR=/mnt/c/Users/<USER>/Documents/tensorflow_datasets
tfds_data_dir = os.getenv("TFDS_DATA_DIR", "/home/cristiano/tensorflow_datasets")


# Embedding-based selection
embeds = {
    "mode": "embed_kcenter",      # "embed_kcenter" (default) or "k_only"
    "backbone": "mobilenet_v2",   # also: "efficientnet_b0"
    "img_size": 224,
    "k_slicing": 0.10,              # use 1 frame every 10 as candidates if 100, 1 every 5 if 50, etc.
    "K": 9,                      # how many final frames to keep
    "batch_size": 32,
    "include_boundaries": False,   # include first/last of the subset
    "force_global_boundaries": False,  # if True, also force global 0 and T-1
    "cache_embeddings": True
}

export_mode    = "final_only"    # "full" | "final_only"
filename_mode  = "sequential"    # orders frame_000.jpg, frame_001.jpg, ...
normalize_names = True           # (legacy alias; keeping it True causes no harm)
prune_only     = True            # in practice keeps only final_selected/ even in "full"
prune_keep     = ["final_selected"]
run_embed_selection = True       # make sure this is active

def get(key, default=None):
    return globals().get(key, default)
