Instruction: Place the red pepper on the bottom right corner of the table. Check if reachable and use a 10 second timeout for navigation.
Allowed Actions: [GRASP(obj), PLACE_ON_TOP(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_REACHABLE]
* Constraints: Robustness: Check condition before NAVIGATE_TO, then use Timeout (msec="10000").
