Instruction: Pull open a dishwasher. Retry opening up to 5 times if it fails.
Allowed Actions: [RELEASE(), NAVIGATE_TO(obj), OPEN(obj), GRASP(obj)]
* Constraints: Robustness: Wrap OPEN with RetryUntilSuccessful (num_attempts="5").
