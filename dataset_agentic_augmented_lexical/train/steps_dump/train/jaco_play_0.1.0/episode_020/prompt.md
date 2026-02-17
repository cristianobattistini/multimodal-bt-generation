Instruction: Pick up the burger meat. If grasping fails, push the burger meat to reposition it and retry grasping.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), PUSH(obj)]
* Constraints: Robustness strategy: If grasping fails due to awkward pose or occlusion, the plan must attempt a repositioning action (push) to address the cause, then retry the grasp.
