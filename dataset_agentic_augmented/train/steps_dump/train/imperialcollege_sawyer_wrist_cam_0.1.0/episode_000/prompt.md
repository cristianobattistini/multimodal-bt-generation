Instruction: insert toast. If grasping fails, push the toast to reposition it and retry grasping.
Allowed Actions: [GRASP(obj), PLACE_INSIDE(obj), NAVIGATE_TO(obj), PUSH(obj)]
* Constraints: Robustness: If primary grasping fails, use a fallback push to change the toast pose/position before retrying grasping to handle occlusion, awkward pose, or out-of-reach edges.
