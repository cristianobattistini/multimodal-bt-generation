Instruction: pull open a dishwasher. If grasping the dishwasher fails, push it slightly to reposition or expose a better handle and retry.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), RELEASE(), PUSH(obj), OPEN(obj)]
* Constraints: Robustness strategy: If the primary grasp fails due to poor pose, occlusion, or unreachable handle, the plan must perform a repositioning push on the dishwasher to improve graspability, then retry the grasp.
