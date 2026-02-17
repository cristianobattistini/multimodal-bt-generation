Instruction: pick up the yellow cup. Check if visible before grasping, retry grasping up to 2 times if it fails; if all attempts fail, push it as a plan B.
Allowed Actions: [GRASP(obj), NAVIGATE_TO(obj), PUSH(obj)]
Allowed Conditions: [IS_VISIBLE]
* Constraints: Robustness: Verify precondition, RetryUntilSuccessful (num_attempts="2") for GRASP, use alternative strategy if all attempts fail.
