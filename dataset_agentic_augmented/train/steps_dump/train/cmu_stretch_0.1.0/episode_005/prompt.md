Instruction: lift open green garbage can lid. Retry opening up to 4 times if it fails.
Allowed Actions: [OPEN(obj), GRASP(obj), RELEASE(), NAVIGATE_TO(obj)]
* Constraints: Robustness: Wrap OPEN with RetryUntilSuccessful (num_attempts="4").
