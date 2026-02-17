Instruction: lift up a lid from the pot. Use a 20 second timeout for grasping and retry up to 2 times if it fails.
Allowed Actions: [GRASP(obj), RELEASE(), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="20000") and RetryUntilSuccessful (num_attempts="2").
