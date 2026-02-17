Instruction: place down red cube. Check if visible and retry grasping up to 3 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PLACE_ON_TOP(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="3").
