Instruction: Move the eggplant and place it above the yellow cloth. Check the holding precondition and retry placing on top up to 3 times if it fails.
Allowed Actions: [PLACE_ON_TOP(obj), GRASP(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_HOLDING]
* Constraints: Robustness: Check condition before PLACE_ON_TOP, then RetryUntilSuccessful (num_attempts="3").
