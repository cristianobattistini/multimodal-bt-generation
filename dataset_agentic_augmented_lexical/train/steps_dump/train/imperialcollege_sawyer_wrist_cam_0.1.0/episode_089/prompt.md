Instruction: Pick up pan. Check if visible, use a 10 second timeout for grasp, and try push if timeout occurs.
Allowed Actions: [PUSH(obj), GRASP(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Verify precondition, use Timeout (msec="10000") on GRASP, use Plan B if timeout.
