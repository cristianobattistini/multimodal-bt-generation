Instruction: insert the peg into the hole
Allowed Actions: [PLACE_INSIDE(obj), PUSH(obj), NAVIGATE_TO(obj), GRASP(obj)]
* Constraints: Robustness strategy: If grasping fails, use PUSH to reposition the peg (addressing awkward pose or partial occlusion) before retrying the grasp.
