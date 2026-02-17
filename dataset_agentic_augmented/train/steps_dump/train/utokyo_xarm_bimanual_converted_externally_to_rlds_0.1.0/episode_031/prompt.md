Instruction: Unfold a wrinkled towel. If unfolding fails, flip the towel to reposition it and retry unfolding.
Allowed Actions: [GRASP(obj), UNFOLD(), PLACE_ON_TOP(obj), NAVIGATE_TO(obj), FLIP(obj)]
* Constraints: Robustness strategy: Provide a fallback that addresses common physical failure modes (e.g., flipping the towel to resolve tangles) and then retry the primary action so the plan can recover from typical execution failures.
