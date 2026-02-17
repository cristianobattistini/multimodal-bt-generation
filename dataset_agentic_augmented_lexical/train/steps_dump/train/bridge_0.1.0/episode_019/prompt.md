Instruction: Put sushi on plate. Check precondition and retry grasping up to 3 times if it fails.
Allowed Actions: [PLACE_ON_TOP(obj), NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="3").
