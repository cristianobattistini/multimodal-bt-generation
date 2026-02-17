Instruction: Take the lid off the pot, put the pot on the plate, and use the tool to push to pot to the front of the table. Check if visible, use a 10 second timeout for grasp, and try pushing if the grasp times out.
Allowed Actions: [OPEN(obj), PLACE_ON_TOP(obj), NAVIGATE_TO(obj), PUSH(obj), GRASP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Verify precondition, use Timeout (msec="10000") on GRASP, use Plan B if timeout.
