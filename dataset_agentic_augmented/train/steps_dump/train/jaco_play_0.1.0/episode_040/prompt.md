Instruction: Place the long bread in the gray bowl. Check precondition and retry placing inside the gray bowl up to 2 times if it fails.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PLACE_INSIDE(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Check condition before PLACE_INSIDE, then RetryUntilSuccessful (num_attempts="2").
