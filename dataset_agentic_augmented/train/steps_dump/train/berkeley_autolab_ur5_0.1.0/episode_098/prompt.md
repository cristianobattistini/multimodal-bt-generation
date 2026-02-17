Instruction: take the tiger out of the red bowl and put it in the grey bowl. If grasping the tiger fails, push it to reposition it and retry grasping.
Allowed Actions: [PUSH(obj), PLACE_INSIDE(obj), GRASP(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness constraint: If primary grasping fails due to poor pose/occlusion, the plan must attempt a repositioning action (push) that addresses the failure cause before retrying the grasp.
