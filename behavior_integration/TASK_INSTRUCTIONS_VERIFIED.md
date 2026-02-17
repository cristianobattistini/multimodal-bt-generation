# 📋 Istruzioni Verificate per i 20 Task Demo

**Basate sui goal BDDL ufficiali di BEHAVIOR-1K**

---

## Formato

```
Task: nome_task
Scene: house_single_floor (tutti questi task)
Goal BDDL: [descrizione formale]
Istruzione: "testo da passare al VLM"
Primitive necessarie: [lista]
```

---

## 1. bringing_water

**Goal BDDL:** `bottles ontop coffee_table AND fridge NOT open`

**Istruzione:** "Take the bottles from the refrigerator and place them on the coffee table, then close the fridge"

**Primitive:** NAVIGATE_TO, OPEN, GRASP, PLACE_ON_TOP, CLOSE, RELEASE

---

## 2. can_meat

**Goal BDDL:** `bratwurst inside hinged_jars (2 each), jars inside cabinet, jars closed`

**Istruzione:** "Put bratwurst sausages into the jars, two per jar, then place the closed jars in the cabinet"

**Primitive:** NAVIGATE_TO, OPEN, GRASP, PLACE_INSIDE, CLOSE, RELEASE

---

## 3. canning_food

**Goal BDDL:** `dice steak and pineapple, put diced steak in one bowl and diced pineapple in another bowl (separate)`

**Istruzione:** "Dice the steak and pineapple, then put the diced steak in one bowl and the diced pineapple in a separate bowl"

**Primitive:** NAVIGATE_TO, GRASP, CUT, PLACE_INSIDE, RELEASE

**⚠️ Richiede:** `--allowed-actions` con CUT

---

## 4. clean_boxing_gloves

**Goal BDDL:** `boxing_gloves NOT covered with dust`

**Istruzione:** "Clean the boxing gloves to remove the dust using the washer"

**Primitive:** NAVIGATE_TO, GRASP, SOAK_INSIDE, RELEASE

**⚠️ Richiede:** `--allowed-actions` con SOAK_INSIDE

---

## 5. clean_up_your_desk

**Goal BDDL:** `folders in bookcase, pens in pencil_box, books in bookcase, pencil in pencil_box, stapler on desk, pencil_box on desk, laptop on desk and closed`

**Istruzione:** "Organize the desk: put folders and books in the bookcase, put pens and pencil in the pencil box, place the pencil box and stapler on the desk, and close the laptop"

**Primitive:** NAVIGATE_TO, OPEN, GRASP, PLACE_INSIDE, PLACE_ON_TOP, CLOSE, RELEASE

---

## 6. collecting_childrens_toys

**Goal BDDL:** `dice, teddies, board_games, train_set all inside bookcase`

**Istruzione:** "Collect all the children's toys (dice, teddy bears, board games, and train set) and put them in the bookcase"

**Primitive:** NAVIGATE_TO, OPEN, GRASP, PLACE_INSIDE, CLOSE, RELEASE

---

## 7. freeze_pies

**Goal BDDL:** `apple_pies inside tupperware, tupperware inside fridge, pies frozen, fridge closed`

**Istruzione:** "Put each apple pie in a tupperware container, then place the containers in the freezer and close it"

**Primitive:** NAVIGATE_TO, OPEN, GRASP, PLACE_INSIDE, CLOSE, RELEASE

**Nota:** Il goal richiede che le torte siano "frozen" - questo potrebbe richiedere tempo in simulazione

---

## 8. outfit_a_basic_toolbox

**Goal BDDL:** `drill, pliers, flashlight, allen_wrench, screwdriver all inside toolbox, toolbox on tabletop, toolbox closed`

**Istruzione:** "Put the drill, pliers, flashlight, allen wrench, and screwdriver into the toolbox, then place the closed toolbox on the table"

**Primitive:** NAVIGATE_TO, OPEN, GRASP, PLACE_INSIDE, PLACE_ON_TOP, CLOSE, RELEASE

---

## 9. picking_up_toys

**Goal BDDL:** `jigsaw_puzzles, board_games, tennis_ball all inside toy_box`

**Istruzione:** "Pick up all the toys (puzzles, board games, and tennis ball) and put them in the toy box"

**Primitive:** NAVIGATE_TO, OPEN, GRASP, PLACE_INSIDE, CLOSE, RELEASE

---

## 10. preparing_lunch_box

**Goal BDDL:** `half_apples, sandwich, cookie, tea_bottle all inside packing_box, fridge closed`

**Istruzione:** "Prepare a lunch box by putting the apple halves, sandwich, cookie, and tea bottle into the packing box, then close the refrigerator"

**Primitive:** NAVIGATE_TO, OPEN, GRASP, PLACE_INSIDE, CLOSE, RELEASE

---

## 11. putting_dishes_away_after_cleaning

**Goal BDDL:** `all plates inside cabinet, all cabinets closed`

**Istruzione:** "Put all the plates from the counter into the cabinet and close the cabinet"

**Primitive:** NAVIGATE_TO, OPEN, GRASP, PLACE_INSIDE, CLOSE, RELEASE

---

## 12. putting_up_Christmas_decorations_inside

**Goal BDDL:** `gift_boxes near/under christmas_tree, candles on table, candy_canes in basket on table, wreath on sofa`

**Istruzione:** "Set up Christmas decorations: place gift boxes under the Christmas tree, put candles on the table, put candy canes in the basket on the table, and place the wreath on the sofa"

**Primitive:** NAVIGATE_TO, GRASP, PLACE_ON_TOP, PLACE_INSIDE, RELEASE

---

## 13. set_up_a_coffee_station_in_your_kitchen

**Goal BDDL:** `coffee_maker on counter, coffee_bottle next to maker, filter on maker, saucer next to maker, cup on saucer, kettle next to maker`

**Istruzione:** "Set up a coffee station on the counter: place the coffee maker, put the coffee bottle and kettle next to it, put the filter on the maker, and place the cup on the saucer next to the coffee maker"

**Primitive:** NAVIGATE_TO, GRASP, PLACE_ON_TOP, RELEASE

---

## 14. slicing_vegetables

**Goal BDDL:** `dice bell_peppers, beets, zucchini (create diced versions), fridge closed`

**Istruzione:** "Slice the vegetables: dice the bell peppers, beets, and zucchini on the chopping board, then close the refrigerator"

**Primitive:** NAVIGATE_TO, GRASP, CUT, RELEASE, CLOSE

**⚠️ Richiede:** `--allowed-actions` con CUT

---

## 15. sorting_household_items

**Goal BDDL:** `detergent under sink (next to each other), sanitary_napkin on shelf, soap on sink, cup on sink with toothbrush inside, toothpaste next to cup`

**Istruzione:** "Sort the household items: put detergent bottles under the sink together, place the sanitary napkin box on the shelf, put soap dispenser and cup on the sink, put the toothbrush in the cup, and place the toothpaste next to the cup"

**Primitive:** NAVIGATE_TO, GRASP, PLACE_ON_TOP, PLACE_INSIDE, RELEASE

---

## 16. sorting_vegetables

**Goal BDDL:** `bok_choy and onions in one bowl, leeks and broccoli in another bowl, corn in a third bowl`

**Istruzione:** "Sort the vegetables into mixing bowls: put bok choy and onions together in one bowl, leeks and broccoli in another bowl, and corn in a third bowl"

**Primitive:** NAVIGATE_TO, GRASP, PLACE_INSIDE, RELEASE

---

## 17. storing_food

**Goal BDDL:** `oatmeal, chips, olive_oil, sugar_jars all inside cabinet`

**Istruzione:** "Store all the food items (oatmeal boxes, chip bags, olive oil bottles, and sugar jars) in the cabinet"

**Primitive:** NAVIGATE_TO, OPEN, GRASP, PLACE_INSIDE, CLOSE, RELEASE

---

## 18. tidying_bedroom

**Goal BDDL:** `sandals next to bed (and next to each other), book on table`

**Istruzione:** "Tidy the bedroom: place both sandals next to the bed together, and put the book on the table"

**Primitive:** NAVIGATE_TO, GRASP, PLACE_ON_TOP, RELEASE

---

## 19. wash_a_baseball_cap

**Goal BDDL:** `baseball_caps NOT covered with dirt`

**Istruzione:** "Wash the baseball caps to remove the dirt using the washer"

**Primitive:** NAVIGATE_TO, GRASP, SOAK_INSIDE, RELEASE

**⚠️ Richiede:** `--allowed-actions` con SOAK_INSIDE

---

## 20. wash_dog_toys

**Goal BDDL:** `teddies NOT covered with dirt/dust, tennis_ball NOT covered with debris, softball NOT covered with dirt`

**Istruzione:** "Wash all the dog toys (teddy bears, tennis ball, and softball) to remove dirt and debris using the washer"

**Primitive:** NAVIGATE_TO, GRASP, SOAK_INSIDE, RELEASE

**⚠️ Richiede:** `--allowed-actions` con SOAK_INSIDE

---

## 📊 Riepilogo per Categoria

### ✅ Task con SOLE primitive DEFAULT (14 task)

Usano solo: `NAVIGATE_TO, GRASP, RELEASE, PLACE_ON_TOP, PLACE_INSIDE, OPEN, CLOSE`

1. bringing_water
2. can_meat
3. clean_up_your_desk
4. collecting_childrens_toys
5. freeze_pies
6. outfit_a_basic_toolbox
7. picking_up_toys
8. preparing_lunch_box
9. putting_dishes_away_after_cleaning
10. putting_up_Christmas_decorations_inside
11. set_up_a_coffee_station_in_your_kitchen
12. sorting_household_items
13. sorting_vegetables
14. storing_food
15. tidying_bedroom

### ⚠️ Task che richiedono CUT (2 task)

Aggiungere: `--allowed-actions "NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,OPEN,CLOSE,CUT"`

- canning_food
- slicing_vegetables

### ⚠️ Task che richiedono SOAK (3 task)

Aggiungere: `--allowed-actions "NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,OPEN,CLOSE,SOAK_INSIDE,SOAK_UNDER"`

- clean_boxing_gloves
- wash_a_baseball_cap
- wash_dog_toys

---

## 🚀 Comando Esempio

### Task standard (primitive default):
```bash
/home/cristiano/miniconda3/envs/behavior_gpu/bin/python \
  behavior_integration/scripts/run_bt_agent_pipeline.py \
  --instruction "Pick up all the toys (puzzles, board games, and tennis ball) and put them in the toy box" \
  --task picking_up_toys \
  --scene house_single_floor \
  --robot Tiago \
  --headless \
  --symbolic \
  --warmup-steps 50 \
  --max-ticks 200 \
  --colab-url "http://127.0.0.1:7860"
```

### Task con CUT:
```bash
/home/cristiano/miniconda3/envs/behavior_gpu/bin/python \
  behavior_integration/scripts/run_bt_agent_pipeline.py \
  --instruction "Dice the steak and pineapple, then put the diced steak in one bowl and the diced pineapple in a separate bowl" \
  --task canning_food \
  --scene house_single_floor \
  --robot Tiago \
  --headless \
  --symbolic \
  --warmup-steps 50 \
  --max-ticks 200 \
  --allowed-actions "NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,OPEN,CLOSE,CUT" \
  --colab-url "http://127.0.0.1:7860"
```

### Task con SOAK:
```bash
/home/cristiano/miniconda3/envs/behavior_gpu/bin/python \
  behavior_integration/scripts/run_bt_agent_pipeline.py \
  --instruction "Wash the baseball caps to remove the dirt using the washer" \
  --task wash_a_baseball_cap \
  --scene house_single_floor \
  --robot Tiago \
  --headless \
  --symbolic \
  --warmup-steps 50 \
  --max-ticks 200 \
  --allowed-actions "NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,OPEN,CLOSE,SOAK_INSIDE,SOAK_UNDER" \
  --colab-url "http://127.0.0.1:7860"
```
