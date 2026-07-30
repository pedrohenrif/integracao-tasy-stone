import base64

from stone_extracao.infrastructure.stone.auth import build_client_auth_headers, decode_stone_body


def test_basic_auth_header_format():
    headers = build_client_auth_headers("sk_test_key")
    assert headers["x-user-type"] == "client"
    assert headers["Accept-Encoding"] == "gzip"
    assert headers["Authorization"].startswith("Basic ")

    encoded = headers["Authorization"].removeprefix("Basic ")
    decoded = base64.b64decode(encoded).decode("ascii")
    assert decoded == "sk_test_key:"


def test_decode_gzip_body():
    import gzip

    raw = b"<Conciliation/>"
    compressed = gzip.compress(raw)
    assert decode_stone_body(compressed) == raw
    assert decode_stone_body(raw) == raw
