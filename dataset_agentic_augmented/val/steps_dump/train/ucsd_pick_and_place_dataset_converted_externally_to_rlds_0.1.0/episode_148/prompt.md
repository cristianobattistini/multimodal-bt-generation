Instruction: place the pot in the sink. Check if pot is visible and retry grasping up to 2 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), GRASP(obj), PLACE_INSIDE(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Check condition before GRASP, then RetryUntilSuccessful (num_attempts="2").
