Instruction: Insert the blue gear onto the right peg, followed by the red gear. Check if graspable and retry grasping up to 3 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PLACE_ON_TOP(obj)]
Allowed Conditions: [IS_REACHABLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="3").
