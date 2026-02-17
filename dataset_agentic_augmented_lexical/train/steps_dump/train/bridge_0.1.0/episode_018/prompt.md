Instruction: Put sweet potato in pot. If grasping fails, push the sweet potato to reposition it and retry grasping.
Allowed Actions: [PLACE_INSIDE(obj), NAVIGATE_TO(obj), GRASP(obj), PUSH(obj)]
* Constraints: Robustness strategy: If the primary grasp attempt fails due to poor pose or occlusion, use a push to change the sweet potato's position/orientation before retrying grasping; this improves success by addressing physical failure causes rather than retrying the same grasp.
