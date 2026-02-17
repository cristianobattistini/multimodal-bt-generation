Instruction: pick the cube. If grasping fails, push the cube to reposition it and retry grasping.
Allowed Actions: [PUSH(obj), NAVIGATE_TO(obj), GRASP(obj)]
* Constraints: Robustness strategy: If grasping the cube fails due to poor pose, occlusion, or being slightly out of reach, the plan uses a push action to reposition the cube (clearing/rotating/sliding it) before attempting grasping again. This fallback is a distinct alternative strategy, not a retry of the same action.
