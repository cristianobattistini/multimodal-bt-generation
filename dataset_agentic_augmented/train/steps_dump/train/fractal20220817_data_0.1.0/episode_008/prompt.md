Instruction: Pick 7up can from bottom shelf of fridge. If grasping fails, push the 7up_can to reposition it and retry grasping.
Allowed Actions: [GRASP(obj), PUSH(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness strategy: If grasping fails due to awkward pose, occlusion, or being too close to shelf edges, perform a PUSH on the 7up_can to reposition it, then attempt grasping again. This fallback is a different strategy (reposition then retry), not a retry of the identical primitive.
