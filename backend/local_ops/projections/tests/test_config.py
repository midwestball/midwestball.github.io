from pathlib import Path
import pytest
from projection_ops.config import SETTINGS


def test_write_escape_refused(tmp_path):
    with pytest.raises(ValueError):
        SETTINGS.assert_local_write(tmp_path / "outside")
