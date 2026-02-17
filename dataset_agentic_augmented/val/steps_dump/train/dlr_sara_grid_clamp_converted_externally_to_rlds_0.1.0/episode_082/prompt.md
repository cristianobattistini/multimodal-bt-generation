Instruction: Place grid clamp. Use a 10 second timeout for grasping and retry up to 3 times if it fails.
Allowed Actions: [PLACE_ON_TOP(obj), NAVIGATE_TO(obj), GRASP(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="3").
