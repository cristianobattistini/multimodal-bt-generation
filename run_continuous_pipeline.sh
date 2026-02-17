#!/bin/bash
# Continuous BT Pipeline - Persistent OmniGibson Session
#
# Runs multiple episodes without restarting OmniGibson.
# Startup happens once (~5 min), then each episode is fast (~30s reset).
#
# Usage examples:
#
#   # Interactive mode
#   ./run_continuous_pipeline.sh --scene house_single_floor --robot Tiago --colab-url "http://127.0.0.1:7860"
#
#   # Single instruction with retries
#   ./run_continuous_pipeline.sh --instruction "bring water to counter" --task bringing_water --retries 3 --colab-url "http://127.0.0.1:7860"
#
#   # Batch mode from file
#   ./run_continuous_pipeline.sh --batch tasks.txt --colab-url "http://127.0.0.1:7860"
#
# Batch file format (tasks.txt):
#   # Comments start with #
#   bring water to the counter | bringing_water | 3
#   clean the table | cleaning_table | 2
#   put apple in fridge | storing_food
#

set -e

export OMNIHUB_ENABLED=0
export OMNIGIBSON_DATA_PATH=/home/cristiano/BEHAVIOR-1K/datasets

# PyTorch memory allocation optimization
export PYTORCH_ALLOC_CONF=expandable_segments:True

PYTHON_BIN=/home/cristiano/miniconda3/envs/behavior/bin/python

cd /home/cristiano/multimodal-bt-generation

mkdir -p debug_logs

# User arguments (reset ARGS to avoid environment pollution)
ARGS="$@"

echo "=================================================="
echo "CONTINUOUS BT PIPELINE"
echo "OmniGibson will start once, then run multiple episodes"
echo "=================================================="
echo ""
echo "Arguments: $ARGS"
echo ""

$PYTHON_BIN behavior_integration/scripts/run_continuous_pipeline.py $ARGS 2>&1 | tee debug_logs/continuous_$(date +%Y%m%d_%H%M%S).log
