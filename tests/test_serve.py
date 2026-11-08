import serve


def test_default_port_is_8004():
    assert serve.DEFAULT_PORT == 8004


# ---- live-server tests for the save/token endpoints ----
import base64
import gzip
import http.client
import json
import threading

import nibabel as nib
import numpy as np
import pytest

from test_save_case import SHAPE, make_case, paint_new, painted, snapshot

VALUES = {"1": "femur", "2": "tibia", "3": "patella"}


@pytest.fixture
def live(tmp_path):
    case = make_case(tmp_path, side="")
    srv = serve.make_server(tmp_path, 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    port = srv.server_address[1]
    yield port, case
    srv.shutdown()
    srv.server_close()
    t.join(5)


def call(port, method, path, body=None, headers=None, host=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Host": host or f"127.0.0.1:{port}"}
    h.update(headers or {})
    c.putrequest(method, path, skip_host=True)
    for k, v in h.items():
        c.putheader(k, v)
    if body is not None:
        c.putheader("Content-Length", str(len(body)))
    c.endheaders(body)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, r.getheader("Content-Type"), data


def post(port, payload, headers=None, host=None, raw=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    body = raw if raw is not None else json.dumps(payload).encode()
    return call(port, "POST", "/api/save", body, h, host)


def get_token(port):
    s, ct, d = call(port, "GET", "/api/token?case=knee-t")
    assert s == 200 and ct.startswith("application/json")
    return json.loads(d)["token"]


def payload(case, token, bitmap=None, **kw):
    bm = paint_new(case) if bitmap is None else bitmap
    p = {"case_id": "knee-t", "token": token,
         "labels_gz_b64": base64.b64encode(gzip.compress(bm.tobytes())).decode(),
         "values": VALUES, "checked": [], "points": []}
    p.update(kw)
    return p


def test_token_then_save(live):
    port, case = live
    tok = get_token(port)
    s, ct, d = post(port, payload(case, tok))
    assert s == 200 and ct.startswith("application/json"), d
    res = json.loads(d)
    assert res["structures"] == 3 and res["token"] != tok
    assert res["labelled"] == ["femur", "patella", "tibia"]
    assert json.loads((case / "lut.json").read_text())["3"]["id"] == "patella"
    assert get_token(port) == res["token"]


def test_token_unknown_or_bad_case(live):
    port, _ = live
    assert call(port, "GET", "/api/token?case=nope")[0] == 404
    assert call(port, "GET", "/api/token?case=..%2F..")[0] == 404
    assert call(port, "GET", "/api/token")[0] == 404


def test_save_requires_json(live):
    port, case = live
    before = snapshot(case)
    s, ct, d = post(port, payload(case, get_token(port)), headers={"Content-Type": "text/plain"})
    assert s == 403 and "error" in json.loads(d)
    assert snapshot(case) == before


def test_save_rejects_foreign_host_and_origin(live):
    port, case = live
    tok = get_token(port)
    before = snapshot(case)
    assert post(port, payload(case, tok), host="evil.example:8004")[0] == 403
    assert post(port, payload(case, tok), headers={"Origin": "http://evil.example"})[0] == 403
    assert post(port, payload(case, tok), headers={"Origin": f"https://127.0.0.1:{port}"})[0] == 403
    assert call(port, "GET", "/api/token?case=knee-t", host="evil.example")[0] == 403
    assert snapshot(case) == before
    # own page is fine, by either name
    ok = post(port, payload(case, tok), host=f"localhost:{port}",
              headers={"Origin": f"http://localhost:{port}"})
    assert ok[0] == 200


def test_save_error_statuses(live):
    port, case = live
    tok = get_token(port)
    before = snapshot(case)
    assert post(port, payload(case, "stale-token"))[0] == 409
    assert post(port, payload(case, tok, labels_gz_b64="!!!not base64!!!"))[0] == 400
    bad_gz = base64.b64encode(b"not gzip at all").decode()
    assert post(port, payload(case, tok, labels_gz_b64=bad_gz))[0] == 400
    assert post(port, None, raw=b"{nope")[0] == 400
    assert post(port, payload(case, tok, case_id="../x"))[0] == 400
    assert post(port, payload(case, tok, case_id="missing"))[0] in (400, 404)
    short = np.zeros(5, np.uint8)
    assert post(port, payload(case, tok, bitmap=short))[0] == 400
    assert snapshot(case) == before
    # oversize Content-Length -> 413 without the body being sent
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.putrequest("POST", "/api/save", skip_host=True)
    c.putheader("Host", f"127.0.0.1:{port}")
    c.putheader("Content-Type", "application/json")
    c.putheader("Content-Length", str(65 * 1024 * 1024))
    c.endheaders()
    assert c.getresponse().status == 413
    c.close()
    # no Content-Length -> 411
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.putrequest("POST", "/api/save", skip_host=True)
    c.putheader("Host", f"127.0.0.1:{port}")
    c.putheader("Content-Type", "application/json")
    c.endheaders()
    assert c.getresponse().status == 411
    c.close()


def test_gunzip_cap(live, monkeypatch):
    port, case = live
    monkeypatch.setattr(serve, "MAX_LABELS_BYTES", 1000)
    big = np.zeros(5000, np.uint8)
    s, _, d = post(port, payload(case, get_token(port), bitmap=big))
    assert s == 400 and "large" in json.loads(d)["error"]


def test_options_not_answered(live):
    port, _ = live
    s, _, _ = call(port, "OPTIONS", "/api/save")
    assert s in (404, 405, 501)


def test_static_files_still_served(live):
    port, case = live
    s, _, d = call(port, "GET", "/data/knee-t/lut.json", host="phone.tailnet.ts.net")
    assert s == 200 and json.loads(d)
    s, _, _ = call(port, "GET", "/")
    assert s == 302
