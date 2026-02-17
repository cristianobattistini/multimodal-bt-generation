Instruction: Pick up the bread. If placing on top fails, push the plate to clear obstacles and retry placing on top.
Allowed Actions: [PLACE_ON_TOP(obj), GRASP(obj), PUSH(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness strategy: When a placement action fails due to destination clutter or instability, the plan must attempt a semantic recovery action (PUSH) to clear or reorient the destination, then retry placement.
