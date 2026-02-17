Instruction: pick up bottle
Allowed Actions: [GRASP(obj), PUSH(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: If grasping fails due to awkward pose, occlusion, or being too far, the plan must use PUSH to reposition the bottle and then retry grasping as a fallback strategy.
