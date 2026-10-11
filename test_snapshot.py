"""
Demo snapshot (ui/snapshot.py, review P4): stable keys, hits and misses, version checks, and the bundled snapshot
running the whole app offline.
"""

import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from ui import snapshot, snapshot_format

ROOT = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A small snapshot file in tmp_path, switched on for this test only."""
    monkeypatch.delenv(snapshot.DISABLE_ENV, raising=False)
    monkeypatch.delenv(snapshot.RECORD_ENV, raising=False)
    path = tmp_path / "snapshot.zip"
    monkeypatch.setattr(snapshot, "PATH", path)
    snapshot.reset()

    def write(data: dict, meta: dict = None):
        path.write_bytes(snapshot_format.dumps(
            {"meta": meta or {**snapshot.versions(), "prices_as_of": "2026-09-30", "built": "2026-10-03"}, "data": data}))
        snapshot.reset()
    yield write
    snapshot.reset()


def test_key_is_canonical_and_sensitive():
    s = pd.Series([0.01, -0.02, 0.03], index=pd.date_range("2026-01-01", periods=3))
    frame = pd.DataFrame({"a": [1.0, 2.0], "b": ["x", "y"]})
    k = snapshot.key("f", (s, frame), {"c": {"y": 2, "x": 1}, "n": None})
    assert k == snapshot.key("f", (s.copy(), frame.copy()), {"n": None, "c": {"x": 1, "y": 2}})  # dict order ignored
    assert k != snapshot.key("f", (s * 1.000001, frame), {"c": {"y": 2, "x": 1}, "n": None})   # a changed value
    assert k != snapshot.key("g", (s, frame), {"c": {"y": 2, "x": 1}, "n": None})              # another function
    assert k != snapshot.key("f", (s.rename("r"), frame), {"c": {"y": 2, "x": 1}, "n": None})  # a renamed series
    assert snapshot.key("f", (np.array([1.0, np.nan]),), {}) == snapshot.key("f", (np.array([1.0, np.nan]),), {})


def test_key_is_the_same_in_another_process():
    code = ("import pandas as pd; from ui import snapshot; "
            "print(snapshot.key('f', (pd.Series([1.5, 2.5], index=pd.date_range('2026-01-01', periods=2)),), {'p': 'max'}))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    assert out == snapshot.key("f", (pd.Series([1.5, 2.5], index=pd.date_range("2026-01-01", periods=2)),), {"p": "max"})


def test_heavy_returns_the_stored_result_and_computes_a_miss(store):
    calls = []

    def calc(x, scale=2.0):
        calls.append(x)
        return x * scale

    named = {"x": 3.0, "scale": 2.0}
    store({snapshot.key("calc", (), named): "from the snapshot"})
    wrapped = snapshot.heavy(calc)
    assert wrapped(3.0) == "from the snapshot" and wrapped(x=3.0, scale=2.0) == "from the snapshot"  # same key
    assert calls == []
    assert wrapped(4.0) == 8.0 and calls == [4.0]  # not in the snapshot: computed live
    assert snapshot.misses() == ["calc"]


def test_download_follows_the_mode_and_returns_a_copy(store, monkeypatch):
    def _fetch(ticker, period="2y"):
        return {"source": "live", "df": pd.DataFrame({"Close": [1.0]})}

    stored = {"source": "snapshot", "df": pd.DataFrame({"Close": [9.0]})}
    store({snapshot.key("fetch", (), {"ticker": "ABC.NS", "period": "2y"}): stored})
    fetch = snapshot.download(_fetch)
    first = fetch("ABC.NS")
    assert first["source"] == "snapshot"
    first["df"].loc[0, "Close"] = -1.0  # a caller changing its copy must not change the store
    assert fetch("ABC.NS")["df"].loc[0, "Close"] == 9.0
    assert fetch("NEW.NS")["source"] == "live"
    monkeypatch.setattr(snapshot, "mode", lambda: snapshot.LIVE)
    assert fetch("ABC.NS")["source"] == "live"


def test_incompatible_or_disabled_snapshot_is_ignored(store, monkeypatch):
    store({"k": 1}, meta={"pandas": "0.0.1", "numpy": "1.0", "prices_as_of": "2026-09-30"})
    assert snapshot.load() is None and snapshot.mode() == snapshot.LIVE
    store({"k": 1})
    assert snapshot.load() is not None
    monkeypatch.setenv(snapshot.DISABLE_ENV, "1")
    snapshot.reset()
    assert snapshot.load() is None


def test_compatible_checks_pandas_and_numpy_major():
    now = snapshot.versions()
    assert snapshot.compatible({"pandas": now["pandas"], "numpy": now["numpy"]})
    assert snapshot.compatible({"pandas": now["pandas"], "numpy": now["numpy"].split(".")[0] + ".99.0"})
    assert not snapshot.compatible({"pandas": "1.5.3", "numpy": now["numpy"]})


def published(monkeypatch, data: dict, prices_as_of: str, sha256: str = None, meta: dict = None, blob: bytes = None):
    """
    Serve a published snapshot from memory: the zip on the data branch and published.json (with the sha256) on main.
    Returns the list of fetched file names.
    """
    meta = meta or {**snapshot.versions(), "prices_as_of": prices_as_of, "built": prices_as_of + "T18:40:00"}
    blob = blob if blob is not None else snapshot_format.dumps({"meta": meta, "data": data})
    files = {"main/published.json": json.dumps({**meta, "sha256": sha256 or hashlib.sha256(blob).hexdigest()}).encode(),
             "snapshot-data/snapshot.zip": blob}
    fetched = []

    def fetch(url, timeout):
        name = "/".join(url.rsplit("/", 2)[-2:])
        fetched.append(name.rsplit("/", 1)[-1])
        if name not in files:
            raise OSError(f"404 {url}")
        return files[name]
    monkeypatch.setenv(snapshot.REMOTE_ENV, "https://example.invalid/snapshot-data/")
    monkeypatch.setenv(snapshot.HASH_ENV, "https://example.invalid/main/published.json")
    monkeypatch.setattr(snapshot, "_fetch", fetch)
    return fetched


def test_newer_compares_prices_then_build():
    old = {"prices_as_of": "2026-10-02T00:00:00", "built": "2026-10-03T14:36:55"}
    assert snapshot.newer({"prices_as_of": "2026-10-05T00:00:00", "built": "2026-10-05T18:40:00"}, old)
    assert snapshot.newer({"prices_as_of": "2026-10-02T00:00:00", "built": "2026-10-04T18:40:00"}, old)
    assert not snapshot.newer({"prices_as_of": "2026-10-01T00:00:00", "built": "2026-10-05T18:40:00"}, old)
    assert snapshot.newer(old, None) and snapshot.newer(old, {})


def test_newer_published_snapshot_replaces_the_bundled_one(store, monkeypatch):
    store({"k": "bundled"})
    fetched = published(monkeypatch, {"k": "published"}, "2026-10-05")
    assert snapshot.load()["data"] == {"k": "published"}
    assert snapshot.meta()["prices_as_of"] == "2026-10-05"
    assert fetched == ["published.json", "snapshot.zip"]  # the hash from main first, then the zip
    snapshot.load()
    assert fetched == ["published.json", "snapshot.zip"]  # not checked again within REMOTE_EVERY
    monkeypatch.setattr(snapshot, "_checked", snapshot._checked - snapshot.REMOTE_EVERY)
    snapshot.load()
    assert fetched[-1] == "published.json" and len(fetched) == 3  # checked again; same snapshot, so not downloaded


def test_published_snapshot_is_ignored_when_older_corrupt_incompatible_or_offline(store, monkeypatch):
    store({"k": "bundled"})  # prices to 2026-09-30
    for kwargs in ({"prices_as_of": "2026-09-29"},                                 # older
                   {"prices_as_of": "2026-10-05", "sha256": "0" * 64},             # not the zip main vouches for
                   {"prices_as_of": "2026-10-05", "blob": b"not a zip"},             # garbage, with a matching hash
                   {"prices_as_of": "2026-10-05", "meta": {"pandas": "0.0.1", "numpy": "1.0",
                                                           "prices_as_of": "2026-10-05"}}):  # other versions
        snapshot.reset()
        published(monkeypatch, {"k": "published"}, **kwargs)
        assert snapshot.load()["data"] == {"k": "bundled"}, kwargs

    def offline(url, timeout):
        raise OSError("network blocked")
    snapshot.reset()
    monkeypatch.setattr(snapshot, "_fetch", offline)
    assert snapshot.load()["data"] == {"k": "bundled"}
    monkeypatch.setenv(snapshot.REMOTE_ENV, "")  # refresh switched off: never fetched
    snapshot.reset()
    monkeypatch.setattr(snapshot, "_fetch", lambda url, timeout: pytest.fail("fetched with the refresh off"))
    assert snapshot.load()["data"] == {"k": "bundled"}


def test_published_snapshot_is_used_when_none_is_bundled(store, monkeypatch):
    published(monkeypatch, {"k": "published"}, "2026-10-05")
    assert snapshot.load()["data"] == {"k": "published"}


def test_a_zip_changed_on_the_data_branch_is_rejected(store, monkeypatch):
    """Tampering: the data branch serves a different (even valid) zip than the one whose hash main committed."""
    store({"k": "bundled"})
    genuine = {**snapshot.versions(), "prices_as_of": "2026-10-05", "built": "2026-10-05T18:40:00"}
    forged = snapshot_format.dumps({"meta": genuine, "data": {"k": "forged"}})
    published(monkeypatch, {"k": "genuine"}, "2026-10-05", meta=genuine)  # main's hash is the genuine zip's
    real_fetch = snapshot._fetch
    monkeypatch.setattr(snapshot, "_fetch", lambda url, timeout: forged if url.endswith("snapshot.zip") else real_fetch(url, timeout))
    assert snapshot.load()["data"] == {"k": "bundled"}


def test_missing_hash_on_main_means_no_download(store, monkeypatch):
    store({"k": "bundled"})
    fetched = published(monkeypatch, {"k": "published"}, "2026-10-05")
    monkeypatch.setenv(snapshot.HASH_ENV, "https://example.invalid/main/missing.json")
    assert snapshot.load()["data"] == {"k": "bundled"} and "snapshot.zip" not in fetched


def test_the_loader_never_unpickles():
    for path in ("ui/snapshot.py", "ui/snapshot_format.py"):
        text = open(os.path.join(ROOT, path), encoding="utf-8").read()
        assert "pickle.load" not in text and "pickle.loads" not in text and "gzip" not in text, path


def test_format_round_trips_every_kind_exactly(tmp_path):
    from garch import GarchParams
    days = pd.date_range("2026-01-01", periods=4).as_unit("s")
    frame = pd.DataFrame({"Date": days, "Close": [1.0, np.nan, 3.0, 4.0], "Name": ["a", "b", "c", "d"],
                          "Volume": [1, 2, 3, 4], "Flag": [True, False, True, False]})
    data = {"k1": {"frame": frame, "series": pd.Series([0.1, 0.2], index=pd.Index(["x", "y"]), name="r"),
                   "dated": pd.Series([1.0, 2.0, 3.0, 4.0], index=pd.DatetimeIndex(days)),
                   "nd": np.arange(6.0).reshape(2, 3), "np": np.float64(0.25), "flag": np.bool_(True), "py": 0.1 + 0.2,
                   "inf": float("inf"), "ts": pd.Timestamp("2026-10-02").as_unit("s"), "garch": GarchParams(0.1, 0.02, 0.05, 0.9, 6.0),
                   "tuple": (1, "a", None), "list": [1, 2.5], 5: "int key", (0.25, True): "tuple key", "__t": "a real key",
                   "empty": pd.DataFrame(index=pd.RangeIndex(3))}}
    back = snapshot_format.loads(snapshot_format.dumps({"meta": {"m": 1}, "data": data}))
    assert back["meta"] == {"m": 1}
    b, a = back["data"]["k1"], data["k1"]
    assert snapshot.key("f", (a,), {}) == snapshot.key("f", (b,), {})
    assert b["frame"]["Date"].dtype == "datetime64[s]" and b["dated"].index.dtype == "datetime64[s]"
    assert type(b["np"]) is np.float64 and type(b["flag"]) is np.bool_ and b["py"] == 0.1 + 0.2 and b["inf"] == float("inf")
    assert b["ts"].unit == "s" and b["garch"] == a["garch"] and b["tuple"] == (1, "a", None)
    assert b[5] == "int key" and b[(0.25, True)] == "tuple key" and b["__t"] == "a real key"
    assert b["empty"].shape == (3, 0)


BUNDLED = os.path.join(ROOT, "data", "snapshot", "snapshot.zip")


@pytest.mark.skipif(not os.path.exists(BUNDLED), reason="no bundled snapshot (scripts/build_snapshot.py)")
def test_bundled_snapshot_runs_every_page_offline(monkeypatch):
    """The demo snapshot alone (network blocked by conftest) renders every page of the default portfolio."""
    from streamlit.testing.v1 import AppTest
    import streamlit as st
    from ui.pages import PAGE_KEY, PAGES
    monkeypatch.delenv(snapshot.DISABLE_ENV, raising=False)
    monkeypatch.setattr(snapshot, "PATH", __import__("pathlib").Path(BUNDLED))
    snapshot.reset()
    st.cache_data.clear()
    if snapshot.load() is None:
        pytest.skip("bundled snapshot built with another pandas/numpy version")
    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=600)
    at.run()
    next(r for r in at.sidebar.radio if r.label == "Analysis Mode").set_value("Portfolio")
    at.run()
    for page in PAGES:
        at.radio(key=PAGE_KEY).set_value(page)
        at.run()
        assert not at.exception, f"{page}: {at.exception[0].value}"
        assert not at.error, f"{page}: {at.error[0].value}"
    # Every result from the snapshot when running on the versions it was built with (elsewhere, e.g. CI on another
    # numpy, a last-digit difference in a derived input can send a calculation live, which is allowed)
    built = snapshot.meta()
    if all(built.get(k) == v for k, v in snapshot.versions().items()):
        assert snapshot.misses() == [], f"computed live instead of from the snapshot: {sorted(set(snapshot.misses()))}"
    snapshot.reset()
    st.cache_data.clear()


@pytest.mark.skipif(not os.path.exists(BUNDLED), reason="no bundled snapshot (scripts/build_snapshot.py)")
def test_bundled_snapshot_entries_keep_their_hash_through_the_format():
    first = snapshot_format.loads(open(BUNDLED, "rb").read())
    again = snapshot_format.loads(snapshot_format.dumps(first))
    assert first["meta"] == again["meta"] and set(first["data"]) == set(again["data"])
    for k, v in first["data"].items():
        assert snapshot.key("x", (v,), {}) == snapshot.key("x", (again["data"][k],), {}), k


def test_published_json_on_main_describes_the_bundled_zip():
    published = os.path.join(ROOT, "data", "snapshot", "published.json")
    info = json.loads(open(published, encoding="utf-8").read())
    assert set(info) >= {"sha256", "prices_as_of", "built", "pandas", "numpy"}
