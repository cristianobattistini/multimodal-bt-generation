Instruction: folding a cloth. Check if unfolded before folding, retry folding up to 3 times if it fails, use unfold as a plan B if unsuccessful.
Allowed Actions: [PLACE_ON_TOP(obj), UNFOLD(), FOLD(), NAVIGATE_TO(obj), GRASP(obj)]
Allowed Conditions: [IS_UNFOLDED]
* Constraints: Robustness: Verify precondition, RetryUntilSuccessful (num_attempts="3") for FOLD, use alternative strategy if all attempts fail.
