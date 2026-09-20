"""Agreement against known classifications.

Fixtures in tests/fixtures/ are device profiles whose real ARTG classification is
known. The percentage of fixtures the engine gets right is the project's only
meaningful quality measure. Add a fixture before fixing a rule, not after.
"""

import pytest

from reguide.rules import classify


@pytest.mark.skip(reason="rules not implemented")
def test_known_classifications():
    raise NotImplementedError
