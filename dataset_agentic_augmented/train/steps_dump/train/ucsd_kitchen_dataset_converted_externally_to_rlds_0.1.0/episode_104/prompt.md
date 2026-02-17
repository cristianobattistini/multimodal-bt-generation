Instruction: Put the canned spam into the sink. Check if graspable, use a 10 second timeout for grasp, try push if timeout occurs.
Allowed Actions: [GRASP(obj), PLACE_INSIDE(obj), PUSH(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_GRASPABLE]
* Constraints: Robustness: Verify precondition, use Timeout (msec="10000") on GRASP, use Plan B if timeout.
