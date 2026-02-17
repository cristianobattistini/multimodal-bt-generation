Instruction: insert cap in bottle. Check precondition and retry placing inside up to 3 times if it fails.
Allowed Actions: [NAVIGATE_TO(obj), PLACE_INSIDE(obj), GRASP(obj)]
Allowed Conditions: [IS_EMPTY]
* Constraints: Robustness: Check condition before PLACE_INSIDE, then RetryUntilSuccessful (num_attempts="3").
