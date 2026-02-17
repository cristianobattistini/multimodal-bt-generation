Instruction: Hang cup. Use a 15 second timeout for grasping and retry up to 2 times if it fails.
Allowed Actions: [RELEASE(), GRASP(obj), NAVIGATE_TO(obj), HANG(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="15000") and RetryUntilSuccessful (num_attempts="2").
