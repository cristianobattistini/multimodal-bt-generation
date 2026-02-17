Instruction: put broccoli in pot cardboardfence. Use a 20 second timeout for grasping and retry up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_INSIDE(obj), GRASP(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="20000") and RetryUntilSuccessful (num_attempts="2").
