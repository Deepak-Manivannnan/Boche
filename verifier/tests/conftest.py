import pytest
from drawfiles import DrawFiles


@pytest.fixture
def draw(tmp_path) -> DrawFiles:
    """A genuine Draw day's public files in a temporary folder, ready to be tampered with."""
    return DrawFiles(tmp_path)
