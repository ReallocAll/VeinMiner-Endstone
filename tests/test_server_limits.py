import json

import pytest

from endstone_vein_miner.server_limits import OPTIONS, ServerLimits


def test_admin_override_is_bounded_and_persistent(tmp_path):
    path = tmp_path / "server.json"
    caps = ServerLimits(path)
    caps.load()
    assert caps.for_category("ores") == 24
    assert caps.for_category("logs") == 160
    caps.set(256)
    assert caps.for_category("ores") == 256
    assert caps.for_category("logs") == 256
    assert json.loads(path.read_text()) == {"max_blocks": 256}
    other = ServerLimits(path)
    other.load()
    assert other.override == 256
    other.set(0)
    assert other.for_category("logs") == 160


def test_invalid_limits_do_not_write_or_mutate(tmp_path):
    caps = ServerLimits(tmp_path / "server.json")
    for bad in (-1, 1, 10, 257, 512, True, 3.5):
        with pytest.raises(ValueError):
            caps.set(bad)
    assert not caps.path.exists()
    assert caps.override == 0
    assert OPTIONS == (0, 24, 64, 128, 256)


def test_invalid_server_config_fails_closed_without_overwriting(tmp_path):
    path = tmp_path / "server.json"
    caps = ServerLimits(path)
    caps.set(128)
    path.write_text('{"max_blocks": "256"}')
    with pytest.raises(ValueError):
        caps.load()
    assert caps.override == 128
    assert json.loads(path.read_text())["max_blocks"] == "256"
