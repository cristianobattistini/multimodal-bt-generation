Instruction: move water bottle near rxbar chocolate. Check if visible, use a 10 second timeout for grasp; if it times out, try push as a fallback.
Allowed Actions: [PLACE_NEXT_TO(obj), GRASP(obj), PUSH(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Verify precondition, use Timeout (msec="10000") on GRASP, use Plan B if timeout.
