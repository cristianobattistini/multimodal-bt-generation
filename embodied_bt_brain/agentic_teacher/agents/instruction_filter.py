"""
Instruction Filter for Teacher Dataset Generation.

Filters out problematic instructions that should be excluded
from the training dataset.
"""

import re
from typing import Tuple


# Patterns that indicate problematic instructions
EXCLUDED_PATTERNS = [
    r"play with",              # Too vague
    r"NOT MOVING",             # Not a command
    r"Video format",           # Error message
    r"Interact with",          # Open-ended
    r"make a cup of",          # Too abstract
    r"make a piece of",        # Too abstract
    r"end effector",           # Meta-description
    r"end-effector",           # Meta-description (hyphenated)
    r"transition from",        # Meta-description
    r"diverse but meaningful", # Open-ended
    r"T-shaped block",         # RL task description (pusht)
    r"observation.*frequency", # RL task description
    r"control.*frequency",     # RL task description
    r"Navigate to the goal",   # Too vague, no specific goal (gnm dataset)
    r"^\s*$",                  # Empty instructions
    r"^N/A$",                  # N/A placeholder
    r"^nan$",                  # NaN value
    r"^none$",                 # None value
]

# Minimum instruction length (too short = likely garbage)
MIN_INSTRUCTION_LENGTH = 5

# Maximum instruction length (too long = likely concatenated/error)
MAX_INSTRUCTION_LENGTH = 500


def is_valid_instruction(instruction: str) -> Tuple[bool, str]:
    """
    Check if an instruction is valid for dataset generation.

    Args:
        instruction: The instruction text to validate.

    Returns:
        Tuple of (is_valid, reason).
        If valid, reason is empty string.
        If invalid, reason explains why.
    """
    if not instruction:
        return False, "Empty instruction"

    instruction_stripped = instruction.strip()

    # Check length
    if len(instruction_stripped) < MIN_INSTRUCTION_LENGTH:
        return False, f"Too short ({len(instruction_stripped)} chars)"

    if len(instruction_stripped) > MAX_INSTRUCTION_LENGTH:
        return False, f"Too long ({len(instruction_stripped)} chars)"

    # Check against exclusion patterns
    for pattern in EXCLUDED_PATTERNS:
        if re.search(pattern, instruction_stripped, re.IGNORECASE):
            return False, f"Matches excluded pattern: {pattern}"

    return True, ""


def filter_instructions(instructions: list[str]) -> list[str]:
    """
    Filter a list of instructions, keeping only valid ones.

    Args:
        instructions: List of instruction strings.

    Returns:
        List of valid instructions.
    """
    return [instr for instr in instructions if is_valid_instruction(instr)[0]]


if __name__ == "__main__":
    # Test examples
    test_cases = [
        "pick up the apple",
        "put the cup on the table",
        "play with the toy",
        "NOT MOVING",
        "Video format error",
        "",
        "a",
        "Interact with any object",
        "make a cup of coffee",
        "fold the towel",
        "move the can to the left",
    ]

    print("Instruction Filter Test Results:\n")
    for instr in test_cases:
        is_valid, reason = is_valid_instruction(instr)
        status = "VALID" if is_valid else f"INVALID ({reason})"
        print(f"  '{instr}' -> {status}")
