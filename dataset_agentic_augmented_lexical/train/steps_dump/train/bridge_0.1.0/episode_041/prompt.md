Instruction: put carrot in pot cardboard fence. Check if reachable before grasping, retry grasping up to 3 times if it fails, use push as Plan B if unsuccessful.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PUSH(obj), PLACE_INSIDE(obj)]
Allowed Conditions: [IS_REACHABLE]
* Constraints: Robustness: Verify precondition, RetryUntilSuccessful (num_attempts="3") for GRASP, use alternative strategy if all attempts fail.
