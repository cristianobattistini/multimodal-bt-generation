Instruction: place down red can. Check if reachable before grasping, retry grasping up to 3 times if it fails, use push as plan B if unsuccessful.
Allowed Actions: [GRASP(obj), PUSH(obj), PLACE_ON_TOP(obj), NAVIGATE_TO(obj)]
Allowed Conditions: [IS_REACHABLE]
* Constraints: Robustness: Verify precondition, RetryUntilSuccessful (num_attempts="3") for GRASP, use alternative strategy if all attempts fail.
