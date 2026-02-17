Instruction: take the tiger out of the red bowl and put it in the grey bowl. Use a 20 second timeout for grasping and retry up to 2 times if it fails.
Allowed Actions: [PLACE_INSIDE(obj), GRASP(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="20000") and RetryUntilSuccessful (num_attempts="2").
