# Runtime Validation README

This document maps the available tasks per scene (from the 2025 challenge dataset)
and provides a minimal workflow for running fast tests with pre-sampled instances.

## Dataset and scene root

- Dataset root: `/home/cristiano/BEHAVIOR-1K/datasets/2025-challenge-task-instances`
- Scenes: `/home/cristiano/BEHAVIOR-1K/datasets/2025-challenge-task-instances/scenes/<scene>/json`

## Scene -> task matrix (challenge instances)

### house_single_floor (23 tasks)
- bringing_water
- can_meat
- canning_food
- clean_boxing_gloves
- clean_up_your_desk
- collecting_childrens_toys
- cook_bacon
- cook_cabbage
- cook_hot_dogs
- freeze_pies
- outfit_a_basic_toolbox
- picking_up_toys
- preparing_lunch_box
- putting_dishes_away_after_cleaning
- putting_up_Christmas_decorations_inside
- set_up_a_coffee_station_in_your_kitchen
- slicing_vegetables
- sorting_household_items
- sorting_vegetables
- storing_food
- tidying_bedroom
- wash_a_baseball_cap
- wash_dog_toys

### house_double_floor_lower (22 tasks)
- assembling_gift_baskets
- bringing_in_wood
- carrying_in_groceries
- chop_an_onion
- chopping_wood
- clean_a_patio
- cleaning_up_plates_and_food
- clearing_food_from_table_into_fridge
- hanging_pictures
- hiding_Easter_eggs
- loading_the_car
- make_microwave_popcorn
- make_pizza
- moving_boxes_to_storage
- picking_up_trash
- putting_away_Halloween_decorations
- putting_shoes_on_rack
- rearranging_kitchen_furniture
- setting_the_fire
- spraying_for_bugs
- spraying_fruit_trees
- turning_on_radio

### house_double_floor_upper (5 tasks)
- attach_a_camera_to_a_tripod
- boxing_books_up_for_storage
- clean_a_trumpet
- getting_organized_for_work
- setting_mousetraps

## Picking a concrete instance (fast)

Each task has a directory `*_instances` with filenames like:
`house_single_floor_task_bringing_water_0_107_template-tro_state.json`

Use:
- `activity_definition_id = 0`
- `activity_instance_id = 107`

To list instances:
```
ls /home/cristiano/BEHAVIOR-1K/datasets/2025-challenge-task-instances/scenes/house_single_floor/json/house_single_floor_task_bringing_water_instances | head
```

## Suggested fast tasks to start

These tend to load quickly and use fewer objects:
- `bringing_water`
- `clean_up_your_desk`
- `clean_boxing_gloves`

## Command template (server + pipeline)

```
OMNIHUB_ENABLED=0 OMNIGIBSON_DATA_PATH=/home/cristiano/BEHAVIOR-1K/datasets \
/home/cristiano/miniconda3/envs/behavior/bin/python -u \
/home/cristiano/multimodal-bt-generation/behavior_integration/scripts/run_bt_agent_pipeline.py \
  --instruction "<your instruction>" \
  --task <task_name> \
  --scene <scene_name> \
  --activity-definition-id 0 \
  --activity-instance-id <instance_id> \
  --robot Tiago \
  --symbolic \
  --max-ticks 50 \
  --allowed-actions "NAVIGATE_TO,GRASP,RELEASE,PLACE_ON_TOP,PLACE_INSIDE,OPEN,CLOSE" \
  --temperature 0.7 \
  --colab-url "http://127.0.0.1:7860"
```

Notes:
- Use `--symbolic` for faster testing.
- Keep `--allowed-actions` as strict as possible for each task.
- Instance `0` is usually the fastest for quick checks.
