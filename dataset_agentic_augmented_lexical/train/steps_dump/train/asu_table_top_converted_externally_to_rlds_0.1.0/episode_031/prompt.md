Instruction: pick cocacola bottle. Use a 15 second timeout for grasping and retry up to 3 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="15000") and RetryUntilSuccessful (num_attempts="3").
