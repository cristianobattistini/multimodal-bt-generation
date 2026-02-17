Instruction: Place the long bread in the sink. Use a 15 second timeout for grasping and retry up to 2 times if it fails.
Allowed Actions: [PLACE_INSIDE(obj), GRASP(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="15000") and RetryUntilSuccessful (num_attempts="2").
