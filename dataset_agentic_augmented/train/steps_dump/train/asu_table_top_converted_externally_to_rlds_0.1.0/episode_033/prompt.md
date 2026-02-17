Instruction: place down red square. Use a 20 second timeout for grasping and retry up to 3 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PLACE_ON_TOP(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="20000") and RetryUntilSuccessful (num_attempts="3").
