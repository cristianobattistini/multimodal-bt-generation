Instruction: Pick up white carton. Use a 20 second timeout for grasping and retry up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="20000") and RetryUntilSuccessful (num_attempts="3").
