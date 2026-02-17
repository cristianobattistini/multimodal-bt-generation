# BEHAVIOR Tasks for Small VLM Models

This document lists the simplest BEHAVIOR tasks suitable for small VLM models trained on basic manipulation primitives.

## Selection Criteria

Tasks are selected based on:
1. **Few objects** (1-4 manipulable objects)
2. **Basic primitives only** (NAVIGATE_TO, GRASP, RELEASE, PLACE_ON_TOP, PLACE_INSIDE, OPEN, CLOSE)
3. **Short horizon** (< 15 estimated steps)
4. **Available scenes** (pre-sampled in house_single_floor or Rs_int)
5. **Well-tested** in existing codebase

---

## TIER 1: Trivial Tasks (Start Here!)

These are the simplest tasks - perfect for initial testing.

### 1. `hanging_pictures`
**Complexity:** TRIVIAL | **Objects:** 1 | **Steps:** ~4

**Goal:** Hang picture on wall

**BDDL Goal:**
```lisp
(ontop picture.n.01_1 wall.n.01_1)
```

**Required Primitives:** NAVIGATE_TO, GRASP, PLACE_ON_TOP

**Command:**
```bash
./run_continuous_pipeline.sh \
    --task hanging_pictures \
    --scene house_single_floor \
    --instruction "hang the picture on the wall" \
    --symbolic \
    --step-screenshots
```

---

### 2. `attach_a_camera_to_a_tripod`
**Complexity:** TRIVIAL | **Objects:** 1 | **Steps:** ~4

**Goal:** Attach camera to tripod

**Required Primitives:** NAVIGATE_TO, GRASP, PLACE_ON_TOP

**Command:**
```bash
./run_continuous_pipeline.sh \
    --task attach_a_camera_to_a_tripod \
    --scene house_single_floor \
    --instruction "attach the camera to the tripod" \
    --symbolic \
    --step-screenshots
```

---

## TIER 2: Simple Tasks (Good for Training)

These tasks have 2-3 objects and are well-tested.

### 3. `tidying_bedroom`
**Complexity:** SIMPLE | **Objects:** 2 | **Steps:** ~8

**Goal:** Move book to nightstand, place sandals near bed

**BDDL Goal:**
```lisp
(and
    (ontop hardback.n.01_1 nightstand.n.01_1)
    (nextto sandal.n.01_1 bed.n.01_1)
    (nextto sandal.n.01_2 bed.n.01_1)
)
```

**Required Primitives:** NAVIGATE_TO, GRASP, PLACE_ON_TOP, RELEASE

**Command:**
```bash
./run_continuous_pipeline.sh \
    --task tidying_bedroom \
    --scene house_single_floor \
    --instruction "put the book on the nightstand and place both sandals next to the bed" \
    --symbolic \
    --step-screenshots
```

**Note:** This is the most well-tested task in the codebase!

---

### 4. `putting_shoes_on_rack`
**Complexity:** SIMPLE | **Objects:** 2 | **Steps:** ~8

**Goal:** Put shoes on shoe rack

**Required Primitives:** NAVIGATE_TO, GRASP, PLACE_ON_TOP, RELEASE

**Command:**
```bash
./run_continuous_pipeline.sh \
    --task putting_shoes_on_rack \
    --scene house_single_floor \
    --instruction "put the shoes on the shoe rack" \
    --symbolic \
    --step-screenshots
```

---

### 5. `picking_up_trash`
**Complexity:** SIMPLE | **Objects:** 3 | **Steps:** ~12

**Goal:** Pick up soda cans and put in trash can

**BDDL Goal:**
```lisp
(forall
    (?can__of__soda.n.01 - can__of__soda.n.01)
    (inside ?can__of__soda.n.01 ashcan.n.01_1)
)
```

**Required Primitives:** NAVIGATE_TO, GRASP, PLACE_INSIDE, RELEASE

**Command:**
```bash
./run_continuous_pipeline.sh \
    --task picking_up_trash \
    --scene house_single_floor \
    --instruction "pick up all the soda cans and put them in the trash can" \
    --symbolic \
    --step-screenshots
```

**Note:** Uses `forall` but same action repeated - good for testing loops.

---

### 6. `bringing_water`
**Complexity:** SIMPLE | **Objects:** 2 | **Steps:** ~10

**Goal:** Bring water bottles from fridge to coffee table

**BDDL Goal:**
```lisp
(and
    (ontop bottle.n.01_1 coffee_table.n.01_1)
    (ontop bottle.n.01_2 coffee_table.n.01_1)
    (not (open fridge.n.01_1))
)
```

**Required Primitives:** NAVIGATE_TO, GRASP, PLACE_ON_TOP, OPEN, CLOSE, RELEASE

**Command:**
```bash
./run_continuous_pipeline.sh \
    --task bringing_water \
    --scene house_single_floor \
    --instruction "get the water bottles from the fridge and put them on the coffee table, then close the fridge" \
    --symbolic \
    --step-screenshots
```

**Note:** Requires OPEN/CLOSE for fridge - tests container manipulation.

---

## TIER 3: Medium Tasks (Advanced Testing)

These tasks have more objects or complexity.

### 7. `storing_food`
**Complexity:** MEDIUM | **Objects:** 4 | **Steps:** ~16

**Goal:** Store food items in cabinet

**Required Primitives:** NAVIGATE_TO, GRASP, PLACE_INSIDE, OPEN, CLOSE, RELEASE

**Command:**
```bash
./run_continuous_pipeline.sh \
    --task storing_food \
    --scene house_single_floor \
    --instruction "put the oatmeal, chips, olive oil, and sugar in the cabinet" \
    --symbolic \
    --step-screenshots
```

---

### 8. `picking_up_toys`
**Complexity:** MEDIUM | **Objects:** 3 | **Steps:** ~12

**Goal:** Collect toys and put in toy box

**Required Primitives:** NAVIGATE_TO, GRASP, PLACE_INSIDE, RELEASE

**Command:**
```bash
./run_continuous_pipeline.sh \
    --task picking_up_toys \
    --scene house_single_floor \
    --instruction "pick up the puzzles, board games, and tennis ball and put them in the toy box" \
    --symbolic \
    --step-screenshots
```

---

### 9. `preparing_lunch_box`
**Complexity:** MEDIUM | **Objects:** 4 | **Steps:** ~16

**Goal:** Pack lunch items into lunch box

**Required Primitives:** NAVIGATE_TO, GRASP, PLACE_INSIDE, OPEN, CLOSE, RELEASE

**Command:**
```bash
./run_continuous_pipeline.sh \
    --task preparing_lunch_box \
    --scene house_single_floor \
    --instruction "put the apple halves, sandwich, cookie, and tea bottle into the lunch box" \
    --symbolic \
    --step-screenshots
```

---

### 10. `putting_dishes_away_after_cleaning`
**Complexity:** MEDIUM | **Objects:** 4 | **Steps:** ~18

**Goal:** Put clean dishes in cabinet

**Required Primitives:** NAVIGATE_TO, GRASP, PLACE_INSIDE, OPEN, CLOSE, RELEASE

**Command:**
```bash
./run_continuous_pipeline.sh \
    --task putting_dishes_away_after_cleaning \
    --scene house_single_floor \
    --instruction "put all the plates from the counter into the cabinet and close it" \
    --symbolic \
    --step-screenshots
```

---

## AVOID These Tasks

These tasks require advanced primitives or are too complex for small VLMs.

| Task | Issue |
|------|-------|
| `slicing_vegetables` | Requires CUT primitive |
| `canning_food` | Requires CUT primitive |
| `clean_boxing_gloves` | Requires SOAK_INSIDE |
| `wash_a_baseball_cap` | Requires SOAK_INSIDE |
| `wash_dog_toys` | Requires SOAK_INSIDE |
| `cook_bacon` | Requires TOGGLE_ON, heating logic |
| `cook_cabbage` | Requires TOGGLE_ON, heating logic |
| `cook_hot_dogs` | Requires TOGGLE_ON, heating logic |

---

## Quick Test Sequence

Run these in order to verify your setup:

```bash
# 1. Test navigation only
./run_continuous_pipeline.sh --bt test_navigate --task tidying_bedroom --symbolic

# 2. Test navigation + grasp
./run_continuous_pipeline.sh --bt test_grasp --task tidying_bedroom --symbolic

# 3. Test complete simple task (pre-defined BT)
./run_continuous_pipeline.sh --bt tidying_bedroom_book --task tidying_bedroom --symbolic --step-screenshots

# 4. Test with VLM (simplest task)
./run_continuous_pipeline.sh \
    --task hanging_pictures \
    --instruction "hang the picture on the wall" \
    --colab-url http://localhost:7860 \
    --symbolic \
    --step-screenshots

# 5. Test with VLM (container task)
./run_continuous_pipeline.sh \
    --task bringing_water \
    --instruction "get water from the fridge and put it on the coffee table, then close the fridge" \
    --colab-url http://localhost:7860 \
    --symbolic \
    --step-screenshots
```

---

## Batch File for All Simple Tasks

Create a batch file to test all recommended tasks:

```
# simple_tasks_batch.txt
hang the picture on the wall | hanging_pictures | 2
put the book on the nightstand | tidying_bedroom | 2
put the shoes on the shoe rack | putting_shoes_on_rack | 2
pick up the soda cans and put them in the trash can | picking_up_trash | 3
get water from the fridge and put it on the coffee table | bringing_water | 3
```

Run with:
```bash
./run_continuous_pipeline.sh \
    --batch simple_tasks_batch.txt \
    --colab-url http://localhost:7860 \
    --symbolic \
    --step-screenshots
```

---

## BDDL Integration

For better object grounding, use the BDDL module:

```python
from behavior_integration.bddl import BDDLGrounder, BDDLParser

# Load BDDL for task
parser = BDDLParser()
task = parser.parse_file("picking_up_trash-0.bddl")

# In your pipeline
grounder = BDDLGrounder(env)
grounder.load_task("picking_up_trash", 0)

# Ground all objects
results = grounder.ground_all_objects()

# Rewrite BT with grounded names
bt_xml_grounded = grounder.rewrite_bt_with_grounding(bt_xml)
```

---

## RTX 5080 Blackwell Tips

If you're having CUDA issues with RTX 5080:

1. **Use symbolic mode** (`--symbolic`) - avoids CuRobo motion planning
2. **Pre-warm CuRobo** before OmniGibson (already in code)
3. **Disable CUDA graphs:**
   ```bash
   export OMNIGIBSON_CUROBO_USE_CUDA_GRAPH=0
   export PYTORCH_ALLOC_CONF=expandable_segments:True
   ```
4. **Use headless mode** (`--headless`) for batch testing
5. **Reduce warmup steps** if loading is slow: `--warmup-steps 30`
