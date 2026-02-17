Instruction: stack bowls. Check if graspable, use a 15 second timeout for grasping; if it times out, try pushing the object to improve graspability.
Allowed Actions: [PUSH(obj), NAVIGATE_TO(obj), PLACE_ON_TOP(obj), GRASP(obj)]
Allowed Conditions: [IS_GRASPABLE]
* Constraints: Robustness: Verify precondition, use Timeout (msec="15000") on GRASP, use Plan B if timeout.
