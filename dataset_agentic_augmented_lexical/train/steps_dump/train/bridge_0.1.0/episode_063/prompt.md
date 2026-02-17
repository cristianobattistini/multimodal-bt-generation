Instruction: Move the pot on the yellow towel. Check precondition and retry grasping up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), PLACE_ON_TOP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="2").
