Instruction: take the tiger out of the red bowl and put it in the grey bowl. If grasping fails, push the tiger to reposition it and retry grasping.
Allowed Actions: [GRASP(obj), PUSH(obj), NAVIGATE_TO(obj), PLACE_INSIDE(obj)]
* Constraints: Robustness: If the primary grasp attempt fails, use the fallback push to reposition the tiger before retrying the grasp, improving success under occlusion or awkward poses.
