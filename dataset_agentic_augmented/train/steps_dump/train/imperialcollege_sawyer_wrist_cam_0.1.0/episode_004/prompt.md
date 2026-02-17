Instruction: insert cap in bottle. Check if visible, use a 10 second timeout for grasp, try push if timeout occurs.
Allowed Actions: [PLACE_INSIDE(obj), NAVIGATE_TO(obj), GRASP(obj), PUSH(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Verify precondition, use Timeout (msec="10000") on GRASP, use Plan B if timeout.
