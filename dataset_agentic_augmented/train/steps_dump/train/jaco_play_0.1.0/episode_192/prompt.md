Instruction: Pick up the orange fruit. If grasping fails, push it slightly to reposition it and retry.
Allowed Actions: [RELEASE(), NAVIGATE_TO(obj), PUSH(obj), GRASP(obj)]
* Constraints: Robustness strategy: If the primary grasp fails due to object pose or occlusion, the fallback will push the object to improve its pose, then retry grasping.
