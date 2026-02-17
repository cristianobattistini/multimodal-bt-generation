Instruction: put apple in pot. Only navigate to the object if it is reachable.
Allowed Actions: [PLACE_INSIDE(obj), NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_REACHABLE]
* Constraints: Robustness: Check IS_REACHABLE condition before NAVIGATE_TO.
