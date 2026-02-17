Instruction: Pick brown chip bag from top drawer and place on counter. Use a 10 second timeout for grasping and retry up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_ON_TOP(obj), GRASP(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="2").
