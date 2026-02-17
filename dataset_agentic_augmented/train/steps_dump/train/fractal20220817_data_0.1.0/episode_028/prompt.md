Instruction: Pick pepsi can from top drawer and place on counter. Retry grasping up to 5 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PLACE_ON_TOP(obj)]
* Constraints: Robustness: Wrap GRASP with RetryUntilSuccessful (num_attempts="5").
