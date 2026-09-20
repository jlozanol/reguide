"""MSAC public summary documents.

The precedent corpus. Each document records what a committee asked for and what
happened to the application. This is what lets the tool say what comparable
technologies were required to show, rather than predicting an outcome.
"""


def comparable_assessments(intended_purpose: str, limit: int = 5) -> list[dict]:
    raise NotImplementedError
