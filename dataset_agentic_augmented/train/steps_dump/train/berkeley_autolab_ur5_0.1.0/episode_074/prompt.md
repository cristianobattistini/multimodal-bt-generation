Instruction: pick up the blue cup and put it into the brown cup. Use a 10 second timeout for grasping and retry up to 3 times if it fails.
Allowed Actions: [PLACE_INSIDE(obj), GRASP(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="10000") and RetryUntilSuccessful (num_attempts="3").
