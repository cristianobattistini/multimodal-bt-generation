Instruction: Reach a towel. If grasping fails, push the towel to reposition it and retry grasping.
Allowed Actions: [PUSH(obj), GRASP(obj), RELEASE(), NAVIGATE_TO(obj)]
* Constraints: Robustness constraint: If grasping fails due to poor object pose or occlusion, perform a push to improve object pose and then retry grasping; ensure the push is gentle to avoid scattering nearby items.
