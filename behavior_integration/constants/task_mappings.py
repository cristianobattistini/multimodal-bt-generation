"""
Task Object Mappings for BEHAVIOR-1K Challenge50 Tasks.

These mappings determine which object the camera should focus on when
initializing a scene. The first object in each list has highest priority.

Key principles:
1. If objects start INSIDE a container -> container FIRST (to open)
2. If objects are accessible -> manipulable object FIRST
"""

# Per-task object mappings (highest priority when task_id is known)
# Format: task_id -> [object1, object2, ...] where first = primary focus
TASK_OBJECT_MAPPINGS = {
    # ═══════════════════════════════════════════════════════════════
    # TASK 00: turning_on_radio
    # Initial: radio on table (accessible)
    # ═══════════════════════════════════════════════════════════════
    '00_turning_on_radio': ['radio_receiver', 'radio'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 01: picking_up_trash
    # Initial: soda cans in living room (accessible)
    # ═══════════════════════════════════════════════════════════════
    '01_picking_up_trash': ['can__of__soda', 'soda', 'ashcan'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 02: putting_away_Halloween_decorations
    # Initial: pumpkins, candles, cauldron in living room (accessible)
    # ═══════════════════════════════════════════════════════════════
    '02_putting_away_Halloween_decorations': ['pumpkin', 'candle', 'caldron'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 03: cleaning_up_plates_and_food
    # Initial: pizzas on plates on breakfast table (accessible)
    # ═══════════════════════════════════════════════════════════════
    '03_cleaning_up_plates_and_food': ['pizza', 'plate', 'bowl'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 04: can_meat
    # Initial: jars IN cabinet -> cabinet FIRST, bratwursts on chopping board
    # ═══════════════════════════════════════════════════════════════
    '04_can_meat': ['cabinet', 'hinged_jar', 'bratwurst', 'chopping_board'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 05: setting_mousetraps
    # Initial: mousetraps IN cabinet -> cabinet FIRST
    # ═══════════════════════════════════════════════════════════════
    '05_setting_mousetraps': ['cabinet', 'mousetrap'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 06: hiding_Easter_eggs
    # Initial: eggs IN wicker basket (accessible, basket on lawn)
    # ═══════════════════════════════════════════════════════════════
    '06_hiding_Easter_eggs': ['wicker_basket', 'easter_egg', 'tree'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 07: picking_up_toys
    # Initial: toys scattered on bed/table (accessible)
    # ═══════════════════════════════════════════════════════════════
    '07_picking_up_toys': ['board_game', 'jigsaw_puzzle', 'tennis_ball', 'toy_box'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 08: rearranging_kitchen_furniture
    # Initial: appliances on countertop (accessible)
    # ═══════════════════════════════════════════════════════════════
    '08_rearranging_kitchen_furniture': ['toaster', 'food_processor', 'french_press', 'cabinet'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 09: putting_up_Christmas_decorations_inside
    # Initial: decorations IN wicker basket
    # ═══════════════════════════════════════════════════════════════
    '09_putting_up_Christmas_decorations_inside': ['wicker_basket', 'wreath', 'candy_cane', 'pillar_candle', 'gift_box'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 10: set_up_a_coffee_station_in_your_kitchen
    # Initial: coffee bottle on shelf, other items dispersed (accessible)
    # ═══════════════════════════════════════════════════════════════
    '10_set_up_a_coffee_station_in_your_kitchen': ['bottle__of__coffee', 'coffee_maker', 'paper_coffee_filter', 'saucer', 'coffee_cup', 'electric_kettle'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 11: putting_dishes_away_after_cleaning
    # Initial: plates on countertops (accessible)
    # ═══════════════════════════════════════════════════════════════
    '11_putting_dishes_away_after_cleaning': ['plate', 'cabinet'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 12: preparing_lunch_box
    # Initial: food on chopping board, tea IN refrigerator -> fridge needed
    # ═══════════════════════════════════════════════════════════════
    '12_preparing_lunch_box': ['half__apple', 'club_sandwich', 'chocolate_chip_cookie', 'packing_box', 'electric_refrigerator', 'bottle__of__tea'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 13: loading_the_car
    # Initial: camera/racket on table, container on floor (accessible)
    # NOTE: car is too large for look_at → bad camera angle. Focus on small objects.
    # ═══════════════════════════════════════════════════════════════
    '13_loading_the_car': ['digital_camera', 'container', 'tennis_racket', 'car'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 14: carrying_in_groceries
    # Sack first for better input image (car view shows only garage wall)
    # ═══════════════════════════════════════════════════════════════
    '14_carrying_in_groceries': ['sack', 'beefsteak_tomato', 'carton__of__milk', 'car', 'electric_refrigerator'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 15: bringing_in_wood
    # Initial: plywood in garden (accessible)
    # ═══════════════════════════════════════════════════════════════
    '15_bringing_in_wood': ['plywood'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 16: moving_boxes_to_storage
    # First step: open door -> orient camera to door
    # ═══════════════════════════════════════════════════════════════
    '16_moving_boxes_to_storage': ['door'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 17: bringing_water
    # Initial: bottles IN refrigerator -> refrigerator FIRST
    # ═══════════════════════════════════════════════════════════════
    '17_bringing_water': ['electric_refrigerator', 'refrigerator', 'bottle', 'coffee_table'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 18: tidying_bedroom
    # Initial: book on bed, sandals dispersed (accessible)
    # ═══════════════════════════════════════════════════════════════
    '18_tidying_bedroom': ['book', 'sandal', 'nightstand', 'bed'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 19: outfit_a_basic_toolbox
    # Initial: tools on tabletop (accessible)
    # ═══════════════════════════════════════════════════════════════
    '19_outfit_a_basic_toolbox': ['drill', 'pliers', 'flashlight', 'allen_wrench', 'screwdriver', 'toolbox'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 20: sorting_vegetables
    # Initial: vegetables IN wicker baskets on floor
    # ═══════════════════════════════════════════════════════════════
    '20_sorting_vegetables': ['wicker_basket', 'bok_choy', 'vidalia_onion', 'sweet_corn', 'broccoli', 'leek', 'mixing_bowl'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 21: collecting_childrens_toys
    # Initial: toys scattered on bed/floor/desk (accessible)
    # ═══════════════════════════════════════════════════════════════
    '21_collecting_childrens_toys': ['die', 'teddy', 'board_game', 'bookcase'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 22: putting_shoes_on_rack
    # Initial: shoes on corridor floor (accessible)
    # ═══════════════════════════════════════════════════════════════
    '22_putting_shoes_on_rack': ['gym_shoe', 'sandal', 'hallstand'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 23: boxing_books_up_for_storage
    # Initial: books in bookcases (accessible)
    # ═══════════════════════════════════════════════════════════════
    '23_boxing_books_up_for_storage': ['book', 'bookcase', 'box'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 24: storing_food
    # Initial: food on countertop (accessible)
    # ═══════════════════════════════════════════════════════════════
    '24_storing_food': ['box__of__oatmeal', 'bag__of__chips', 'bottle__of__olive_oil', 'jar__of__sugar', 'cabinet'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 25: clearing_food_from_table_into_fridge
    # Initial: food on plates on table, tupperware on counter (accessible)
    # ═══════════════════════════════════════════════════════════════
    '25_clearing_food_from_table_into_fridge': ['half__chicken', 'half__apple_pie', 'plate', 'tupperware', 'electric_refrigerator'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 26: assembling_gift_baskets
    # Initial: items on table, baskets on floor (accessible)
    # ═══════════════════════════════════════════════════════════════
    '26_assembling_gift_baskets': ['candle', 'butter_cookie', 'swiss_cheese', 'bow', 'wicker_basket'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 27: sorting_household_items
    # Initial: items IN baskets on bedroom floor
    # ═══════════════════════════════════════════════════════════════
    '27_sorting_household_items': ['basket', 'bottle__of__detergent', 'box__of__sanitary_napkin', 'soap_dispenser', 'tube__of__toothpaste', 'toothbrush', 'cup'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 28: getting_organized_for_work
    # Initial: items dispersed in bedroom (accessible)
    # ═══════════════════════════════════════════════════════════════
    '28_getting_organized_for_work': ['mouse', 'keyboard', 'monitor', 'computer', 'folder', 'notebook', 'pen', 'desk'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 29: clean_up_your_desk
    # Initial: items on desk/bed, stapler IN bookcase
    # ═══════════════════════════════════════════════════════════════
    '29_clean_up_your_desk': ['laptop', 'folder', 'paperback_book', 'pencil', 'pen', 'pencil_box', 'bookcase', 'stapler'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 30: setting_the_fire
    # Initial: newspaper on table, firewood on floor (accessible)
    # ═══════════════════════════════════════════════════════════════
    '30_setting_the_fire': ['newspaper', 'firewood', 'wood_fireplace', 'cigar_lighter'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 31: clean_boxing_gloves
    # Initial: gloves on countertop (accessible)
    # ═══════════════════════════════════════════════════════════════
    '31_clean_boxing_gloves': ['boxing_glove', 'washer'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 32: wash_a_baseball_cap
    # Initial: caps on countertop (accessible)
    # ═══════════════════════════════════════════════════════════════
    '32_wash_a_baseball_cap': ['baseball_cap', 'washer'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 33: wash_dog_toys
    # Initial: toys IN cabinet -> cabinet FIRST
    # ═══════════════════════════════════════════════════════════════
    '33_wash_dog_toys': ['cabinet', 'teddy', 'tennis_ball', 'softball', 'washer'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 34: hanging_pictures
    # Initial: poster on countertop (accessible)
    # ═══════════════════════════════════════════════════════════════
    '34_hanging_pictures': ['poster', 'wall_nail'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 35: attach_a_camera_to_a_tripod
    # Initial: camera and tripod in bedroom (accessible)
    # ═══════════════════════════════════════════════════════════════
    '35_attach_a_camera_to_a_tripod': ['digital_camera', 'camera_tripod'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 36: clean_a_patio
    # Initial: broom in garden (accessible)
    # ═══════════════════════════════════════════════════════════════
    '36_clean_a_patio': ['broom', 'floor'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 37: clean_a_trumpet
    # Initial: scrub brush and cornet on desk (accessible)
    # ═══════════════════════════════════════════════════════════════
    '37_clean_a_trumpet': ['scrub_brush', 'cornet'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 38: spraying_for_bugs
    # Initial: atomizer in garden (accessible)
    # ═══════════════════════════════════════════════════════════════
    '38_spraying_for_bugs': ['insectifuge__atomizer', 'pot_plant'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 39: spraying_fruit_trees
    # Initial: atomizer on garden floor (accessible)
    # ═══════════════════════════════════════════════════════════════
    '39_spraying_fruit_trees': ['pesticide__atomizer', 'tree'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 40: make_microwave_popcorn
    # Initial: popcorn bag on countertop (accessible)
    # ═══════════════════════════════════════════════════════════════
    '40_make_microwave_popcorn': ['popcorn__bag', 'microwave'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 41: cook_cabbage
    # Initial: cabbage and chili IN refrigerator -> refrigerator FIRST
    # ═══════════════════════════════════════════════════════════════
    '41_cook_cabbage': ['electric_refrigerator', 'head_cabbage', 'chili', 'carving_knife', 'chopping_board', 'frying_pan', 'stove'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 42: chop_an_onion
    # Initial: onion IN sink (accessible)
    # ═══════════════════════════════════════════════════════════════
    '42_chop_an_onion': ['sink', 'vidalia_onion', 'parer', 'chopping_board', 'bowl'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 43: slicing_vegetables
    # Initial: vegetables IN refrigerator -> refrigerator FIRST
    # ═══════════════════════════════════════════════════════════════
    '43_slicing_vegetables': ['electric_refrigerator', 'bell_pepper', 'beet', 'zucchini', 'parer', 'chopping_board'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 44: chopping_wood
    # Initial: logs on driveway (accessible)
    # ═══════════════════════════════════════════════════════════════
    '44_chopping_wood': ['log', 'ax', 'chopping_block'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 45: cook_hot_dogs
    # Initial: hot dogs IN refrigerator -> refrigerator FIRST
    # ═══════════════════════════════════════════════════════════════
    '45_cook_hot_dogs': ['electric_refrigerator', 'hotdog', 'microwave'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 46: cook_bacon
    # Initial: bacon tray IN refrigerator -> refrigerator FIRST
    # ═══════════════════════════════════════════════════════════════
    '46_cook_bacon': ['electric_refrigerator', 'tray', 'bacon', 'frying_pan', 'stove'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 47: freeze_pies
    # Initial: pies on plates on counter, tupperware IN cabinet
    # ═══════════════════════════════════════════════════════════════
    '47_freeze_pies': ['apple_pie', 'plate', 'cabinet', 'tupperware', 'electric_refrigerator'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 48: canning_food
    # Initial: steak/pineapple IN refrigerator, bowls IN cabinet
    # ═══════════════════════════════════════════════════════════════
    '48_canning_food': ['electric_refrigerator', 'cabinet', 'steak', 'pineapple', 'carving_knife', 'chopping_board', 'bowl'],

    # ═══════════════════════════════════════════════════════════════
    # TASK 49: make_pizza
    # Initial: toppings IN refrigerator tupperware, dough on cookie sheet
    # ═══════════════════════════════════════════════════════════════
    '49_make_pizza': ['electric_refrigerator', 'tupperware', 'grated_cheese', 'pepperoni', 'mushroom', 'vidalia_onion', 'pizza_dough', 'cookie_sheet', 'carving_knife', 'oven'],
}


# General fallback keyword mappings (used when task_id is NOT provided)
GENERAL_KEYWORD_MAPPINGS = {
    # Containers (often need to be opened first)
    'fridge': ['electric_refrigerator', 'refrigerator'],
    'refrigerator': ['electric_refrigerator', 'refrigerator'],
    'cabinet': ['cabinet', 'cupboard'],
    'basket': ['wicker_basket', 'basket'],
    'box': ['box', 'packing_box', 'toy_box', 'gift_box'],
    'car': ['car', 'car_trunk'],

    # Common objects
    'radio': ['radio_receiver', 'radio'],
    'bottle': ['bottle'],
    'plate': ['plate', 'dish'],
    'bowl': ['bowl', 'mixing_bowl'],
    'book': ['book', 'hardback', 'paperback'],
    'toy': ['board_game', 'jigsaw_puzzle', 'toy', 'teddy'],
    'ball': ['tennis_ball', 'softball', 'ball'],
    'shoe': ['gym_shoe', 'sandal', 'shoe'],
    'tool': ['drill', 'pliers', 'screwdriver', 'wrench'],

    # Appliances
    'microwave': ['microwave'],
    'stove': ['stove'],
    'oven': ['oven'],
    'washer': ['washer'],

    # Furniture
    'table': ['table', 'coffee_table', 'breakfast_table', 'desk'],
    'bed': ['bed'],
    'desk': ['desk'],
    'shelf': ['shelf', 'bookshelf'],
    'sink': ['sink'],

    # Food items
    'food': ['pizza', 'sandwich', 'apple', 'chicken', 'bacon', 'steak'],
    'vegetable': ['bok_choy', 'onion', 'pepper', 'cabbage', 'broccoli'],
    'fruit': ['apple', 'pineapple', 'tomato'],

    # Cleaning
    'clean': ['sponge', 'scrub_brush', 'broom', 'washer'],
}
