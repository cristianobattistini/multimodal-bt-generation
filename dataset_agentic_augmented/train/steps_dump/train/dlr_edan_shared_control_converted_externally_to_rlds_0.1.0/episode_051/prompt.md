Instruction: pick the cube. Check if visible, use a 15 second timeout for grasp; if it times out, try push.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PUSH(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Verify precondition, use Timeout (msec="15000") on GRASP, use Plan B if timeout.
