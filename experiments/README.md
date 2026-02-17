# BEHAVIOR-1K Experiment Tracking

This directory contains the experiment tracking system for evaluating models on the BEHAVIOR-1K benchmark tasks.

## Directory Structure

```
multimodal-bt-generation/
├── experiments/
│   ├── README.md                        # This file
│   └── behavior_1k_experiments.json     # Tracking file with all 50 tasks
└── behavior-1k-challenge/
    ├── baseline/                        # Results for base VLM (no adapter)
    ├── adapter/                         # Results for VLM + trained adapter
    └── gpt5/                            # Results for GPT-5 proprietary model
```

## Metrics

We evaluate models using two complementary metrics:

### 1. Success Rate (SR) - Single Shot

**Definition**: `SR = 1` if the first attempt succeeds, `0` otherwise.

**Rationale**:
- Measures the model's ability to generate a correct behavior tree on the first try
- Reflects real-world deployment scenarios where immediate success is critical
- Penalizes models that rely on luck or trial-and-error
- Standard metric in robotics and embodied AI benchmarks (BEHAVIOR-100, RoboTurk)

**Interpretation**:
| Value | Meaning |
|-------|---------|
| 1.0 | Perfect first-attempt performance |
| 0.5 | Model succeeds half the time on first try |
| 0.0 | Model never succeeds on first attempt |

### 2. Pass@N (N=3)

**Definition**: `Pass@3 = 1` if at least one of 3 attempts succeeds, `0` otherwise.

**Rationale**:
- Inspired by code generation benchmarks (HumanEval, MBPP) where Pass@k is standard
- Captures model capability even when execution is stochastic
- Accounts for:
  - Environment variability (object positions, physics)
  - Model sampling variance (temperature, randomness)
  - Minor execution failures that don't reflect true capability
- More forgiving than single-shot, useful for research comparison

**Why N=3**:
- Balances thoroughness with practical experiment time
- 3 attempts provide statistical significance without excessive runs
- Common choice in literature (AlphaCode, Codex evaluations)

### Combined Analysis

| SR | Pass@3 | Interpretation |
|----|--------|----------------|
| High | High | Reliable, production-ready |
| Low | High | Capable but inconsistent |
| Low | Low | Fundamental capability gap |

**Key insight**: A large gap between `Pass@3` and `SR` indicates the model "knows" how to solve the task but struggles with reliability.

---

## Task Difficulty Classification

Tasks are classified into three difficulty levels based on objective structural factors.

### Classification Criteria

| Factor | Low | Medium | High |
|--------|-----|--------|------|
| **Object Count** | 1-3 | 4-8 | 9+ |
| **Action Types** | 1-2 | 3-4 | 5+ |
| **Containers** | None | 1-2 (open/close) | Multiple nested |
| **State Changes** | None | Simple (toggle) | Cooking, cutting, washing |
| **Spatial Constraints** | None | Basic (next to) | Complex (stacking, under) |
| **Rooms Involved** | 1 | 1-2 | 2+ with navigation |

### Distribution

```
Low:    12 tasks (24%)  ████████████
Medium: 25 tasks (50%)  █████████████████████████
High:   13 tasks (26%)  █████████████
```

### Low Difficulty (12 tasks)

**Characteristics**:
- Single action type (toggle, attach, spray)
- Minimal object manipulation
- No container interactions
- Clear, unambiguous goals

**Tasks**:
- `00_turning_on_radio` - toggle only, 1 object
- `15_bringing_in_wood` - 3 objects, simple placement
- `17_bringing_water` - 2 objects, fridge open/close
- `18_tidying_bedroom` - 3 objects, simple placement
- `31_clean_boxing_gloves` - 2 objects, washing
- `32_wash_a_baseball_cap` - 2 objects, washing
- `34_hanging_pictures` - 1 object, attachment
- `35_attach_a_camera_to_a_tripod` - 2 objects, attachment
- `36_clean_a_patio` - 1 object, sweeping
- `37_clean_a_trumpet` - 2 objects, cleaning
- `38_spraying_for_bugs` - 2 targets, spraying
- `39_spraying_fruit_trees` - 2 targets, spraying

### Medium Difficulty (25 tasks)

**Characteristics**:
- Multiple action types (navigate, grasp, place)
- Container interactions (open/close cabinets, fridges)
- Multiple objects of same type
- Basic spatial arrangements

**Tasks**:
- `01_picking_up_trash` - 3 objects to container
- `03_cleaning_up_plates_and_food` - 4 objects, fridge + sink
- `05_setting_mousetraps` - 4 objects, spatial constraints
- `06_hiding_Easter_eggs` - 3 objects, spatial placement
- `08_rearranging_kitchen_furniture` - 3 objects to cabinet
- `10_set_up_a_coffee_station` - 5 objects, spatial arrangement
- `11_putting_dishes_away_after_cleaning` - 8 objects to cabinet
- `13_loading_the_car` - 3 objects, multi-room
- `14_carrying_in_groceries` - 3 objects, multi-room
- `16_moving_boxes_to_storage` - 2 objects, stacking
- `19_outfit_a_basic_toolbox` - 5 objects to container
- `21_collecting_childrens_toys` - 6 objects to bookcase
- `22_putting_shoes_on_rack` - 4 objects, spatial arrangement
- `23_boxing_books_up_for_storage` - 6 objects to box
- `24_storing_food` - 8 objects to cabinets
- `27_sorting_household_items` - 7 objects, multi-room
- `28_getting_organized_for_work` - 7 objects, stacking
- `29_clean_up_your_desk` - 7 objects, multi-container
- `30_setting_the_fire` - 4 objects, toggle + placement
- `33_wash_dog_toys` - 4 objects, washing
- `40_make_microwave_popcorn` - 1 object, cooking
- `42_chop_an_onion` - 3 objects, cutting
- `45_cook_hot_dogs` - 2 objects, cooking
- `46_cook_bacon` - 6 objects, cooking
- `47_freeze_pies` - 4 objects, container + state change

### High Difficulty (13 tasks)

**Characteristics**:
- Many objects (10+) with different destinations
- Complex state changes (cooking, cutting, freezing)
- Multi-step sequences with dependencies
- Strict spatial/logical constraints

**Tasks**:
- `02_putting_away_Halloween_decorations` - 7 objects, multiple cabinets
- `04_can_meat` - 8 objects, open/close jars + cabinet
- `07_picking_up_toys` - 6 objects from multiple locations
- `09_putting_up_Christmas_decorations` - 9 objects, multi-room
- `12_preparing_lunch_box` - 5 objects, fridge + cutting
- `20_sorting_vegetables` - 14 objects, 3 specific destinations
- `25_clearing_food_from_table_into_fridge` - 4 objects, containers + fridge
- `26_assembling_gift_baskets` - 16 objects, 4 baskets
- `41_cook_cabbage` - 4 objects, cutting + cooking
- `43_slicing_vegetables` - 5 objects, cutting
- `44_chopping_wood` - 4 objects, cutting
- `48_canning_food` - 6 objects, cutting + containers
- `49_make_pizza` - 15+ objects, cutting + cooking + assembly

---

## Running Experiments

### Command Format

Run the pipeline with interactive control:

```bash
./run_continuous_pipeline.sh --task <TASK_ID> --interactive-control --server-url http://10.79.2.183:7860
```

### Model Selection (Interactive Menu)

When you press **[7] Generate Behavior Tree**, you'll see:

```
  === GENERATE / SELECT BT ===
    [1] Generate from VLM (adapter - LoRA finetuned)  → saves to adapter/
    [2] Select predefined BT template                  → saves to mock/
    [3] Generate from VLM (baseline - no adapter)     → saves to baseline/
    [4] Generate from GPT-5 (OpenAI API)              → saves to gpt5/
```

The output folder is automatically determined by your choice. When you execute the BT with **[8]**, results are saved to:

```
behavior-1k-challenge/{model_variant}/{task_id}/experiment_N/
├── bddl_result.json      # Success/failure and metrics
├── bt_executed.xml       # The executed behavior tree
├── bt_execution_head.mp4 # Video from robot head camera
├── bt_execution_wrist.mp4# Video from wrist camera
├── mapping.json          # BDDL → scene object mapping
└── frames/               # Captured action frames
```

Experiment numbers are auto-incremented per model/task combination.

### Workflow

1. **Run the command**: `./run_continuous_pipeline.sh --task <TASK_ID> --interactive-control --server-url ...`
2. **Generate BT** with option [7], selecting the model variant (1-4)
3. **Execute BT** with option [8] - results are automatically saved to the correct folder
4. **Update the tracking file** with the result:
   ```json
   "attempts": [true, false, true]  // Results of 3 attempts
   "success_rate": 1,               // First attempt succeeded
   "pass_at_3": 1                   // At least one attempt succeeded
   ```

### Recording Results (Automatic Sync)

After running experiments, use the sync script to automatically update the tracking file:

```bash
# Sync all results from bddl_result.json files
python experiments/sync_results.py

# Preview changes without saving
python experiments/sync_results.py --dry-run

# Sync specific task or model
python experiments/sync_results.py --task 00_turning_on_radio
python experiments/sync_results.py --model baseline

# View progress summary
python experiments/sync_results.py --summary
```

The script reads `bddl_result.json` from each `experiment_N/` folder and updates:
- `attempts[]` array with success/failure for each experiment
- `success_rate` = 1 if first attempt succeeded, else 0
- `pass_at_3` = 1 if any of 3 attempts succeeded, else 0

---

## Task Categories

| Category | Count | Description |
|----------|-------|-------------|
| `toggle` | 2 | Turn on/off objects |
| `placement_simple` | 16 | Move objects to locations |
| `placement_container` | 17 | Place objects inside containers |
| `cutting` | 6 | Cutting/chopping operations |
| `cooking` | 3 | Cooking operations |
| `cooking_cutting` | 1 | Combined cooking and cutting |
| `attachment` | 2 | Attach objects together |
| `spraying` | 2 | Spray operations |

---

## LaTeX Table Generation

The JSON structure supports generating a results table. Example output format:

```latex
\begin{table}[h]
\centering
\begin{tabular}{llc|cc|cc|cc}
\toprule
Task & Cat & Diff & \multicolumn{2}{c|}{Baseline} & \multicolumn{2}{c|}{Adapter} & \multicolumn{2}{c}{GPT-5} \\
     &     &      & SR & P@3 & SR & P@3 & SR & P@3 \\
\midrule
00\_turning\_on\_radio & toggle & L & 1 & 1 & 1 & 1 & 1 & 1 \\
...
\bottomrule
\end{tabular}
\end{table}
```

---

## References

- **BEHAVIOR-1K**: Stanford's benchmark for household robotic tasks
- **Pass@k metric**: Chen et al., "Evaluating Large Language Models Trained on Code" (2021)
- **Success Rate**: Standard robotics evaluation metric
