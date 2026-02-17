Instruction: Close fridge. Retry closing up to 5 times if it fails.
Allowed Actions: [RELEASE(), NAVIGATE_TO(obj), GRASP(obj), CLOSE(obj)]
* Constraints: Robustness: Wrap CLOSE with RetryUntilSuccessful (num_attempts="5").
