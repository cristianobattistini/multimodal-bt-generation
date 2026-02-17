Instruction: Place the bread, butter, and milk from the table onto the serving area. Use a 20 second timeout for grasping and retry up to 3 times if it fails.
Allowed Actions: [PLACE_ON_TOP(obj), GRASP(obj), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap GRASP with Timeout (msec="20000") and RetryUntilSuccessful (num_attempts="3").
