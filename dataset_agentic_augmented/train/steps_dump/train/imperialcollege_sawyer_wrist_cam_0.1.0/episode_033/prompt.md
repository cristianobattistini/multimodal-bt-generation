Instruction: put apple in pot. Grasp the apple. If grasping fails, push the apple to reposition it and retry.
Allowed Actions: [GRASP(obj), PLACE_INSIDE(obj), NAVIGATE_TO(obj), PUSH(obj)]
* Constraints: Robustness: When primary manipulation actions (like grasping) can fail due to object pose or occlusion, include alternative strategies (e.g., pushing) that change the object's pose before retrying to improve success rates.
