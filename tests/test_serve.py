import serve


def test_default_port_is_8004():
    assert serve.DEFAULT_PORT == 8004
