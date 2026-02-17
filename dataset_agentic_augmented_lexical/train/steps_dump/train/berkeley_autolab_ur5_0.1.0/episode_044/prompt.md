Instruction: put the ranch bottle into the pot. Check precondition and retry placing inside up to 3 times if it fails.
Allowed Actions: [PLACE_INSIDE(obj), GRASP(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Check condition before PLACE_INSIDE, then RetryUntilSuccessful (num_attempts="3").
