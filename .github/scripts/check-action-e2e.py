"""Verify real composite Action outcomes and captured step summaries."""
import html
import os
from pathlib import Path
import sys


def verify(root, passing_outcome, passing_conclusion, failing_outcome, failing_conclusion):
    if (passing_outcome, passing_conclusion) != ("success", "success"):
        raise ValueError(f"Expected successful Action invocation; got {passing_outcome}/{passing_conclusion}.")
    # outcome precedes continue-on-error; conclusion includes its effect.
    if (failing_outcome, failing_conclusion) != ("failure", "success"):
        raise ValueError(f"Expected tolerated Action failure; got {failing_outcome}/{failing_conclusion}.")
    for point, outcome, code in (("summary-first", "PASS", 0), ("summary-second", "FAIL", 1)):
        text = (root / f"{point}.md").read_text()
        expected = (f"— {point}", f"**{outcome}**", f"CLI exit code: **{code}**",
                    "| 1/1 |", "Hosted composite summary acceptance")
        if text.count("## Please Behave") != 1 or not all(value in html.unescape(text) for value in expected):
            raise ValueError(f"Unexpected summary content for {point}:\n{text}")
        other = "summary-second" if point == "summary-first" else "summary-first"
        if f"— {other}" in html.unescape(text):
            raise ValueError(f"Summary for {point} contains another invocation's heading.")


if __name__ == "__main__":
    try:
        verify(Path(os.environ["RUNNER_TEMP"]), os.environ["PASSING_OUTCOME"],
               os.environ["PASSING_CONCLUSION"], os.environ["FAILING_OUTCOME"],
               os.environ["FAILING_CONCLUSION"])
        print("Action E2E passed: success and expected failure observed; independent summaries verified.")
    except (OSError, ValueError, KeyError) as error:
        sys.exit(f"Action E2E failed: {error}")
