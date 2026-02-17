Instruction: pick the banana. If grasping fails, push it slightly to reposition it and retry.
Allowed Actions: [NAVIGATE_TO(obj), PUSH(obj), GRASP(obj)]
* Constraints: Robustness: If grasping fails, use the PUSH fallback to reposition the object (addressing awkward orientations, occlusions, or distance) and then retry grasping; this ensures a different physical strategy rather than retrying the same primitive.
