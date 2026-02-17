Instruction: Opening the fridge. If grasping fails, push the fridge (reposition handle/object) and retry grasping.
Allowed Actions: [NAVIGATE_TO(obj), OPEN(obj), GRASP(obj), RELEASE(), PUSH(obj)]
* Constraints: Robustness strategy: If the primary grasp fails because the handle or object is poorly positioned, use the PUSH action to reposition the object to a more favorable pose, then retry grasping.
