Instruction: put apple in pot. Use a 15 second timeout for grasping and retry up to 2 times if it fails.
Allowed Actions: [GRASP(obj), PLACE_INSIDE(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="15000") and RetryUntilSuccessful (num_attempts="2").
