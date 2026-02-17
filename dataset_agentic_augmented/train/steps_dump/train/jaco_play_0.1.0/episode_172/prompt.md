Instruction: place the burger meat in the black bowl.
Allowed Actions: [PUSH(obj), NAVIGATE_TO(obj), GRASP(obj), PLACE_INSIDE(obj)]
* Constraints: Robustness: If grasping fails, the plan includes a fallback strategy that repositions the object by pushing it and then retries grasping to improve success under occlusion or awkward pose.
