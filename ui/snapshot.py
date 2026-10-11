"""
Demo snapshot (review P4): precomputed results for the presets, so the hosted app answers instantly.

- `scripts/build_snapshot.py` runs the app on every preset with the default settings and records the downloads and
  the result of every heavy cached function in data/snapshot/snapshot.zip, with the date of the last price.
- In "Demo snapshot" mode (the default when the file is present), downloads come from the snapshot, so the heavy
  functions see the same inputs and their stored results are reused. A ticker or setting that is not in the snapshot
  is downloaded and computed live as usual.
- Heavy results are keyed on a hash of their inputs, not on the mode, so a stored result is only ever returned for
  exactly the inputs it was computed from.

- Daily refresh: .github/workflows/refresh-snapshot.yml rebuilds the snapshot after each NSE session, publishes the
  zip on the `snapshot-data` branch, and commits its sha256 (with its meta) to data/snapshot/published.json on
  `main`. Every REMOTE_EVERY seconds the app reads main's published.json; if it describes a newer snapshot, the app
  downloads the zip from `snapshot-data` and swaps it in only if its sha256 matches the one committed on main. The
  copy bundled in the repository is the fallback.

Integrity (Phase H): the file is a zip of JSON and Parquet (ui/snapshot_format.py), so loading it never runs code,
and a file changed on the data branch alone is rejected, because the hash it must match lives on `main`. The
snapshot is ignored (live mode) if it is missing, or was built with a different pandas or numpy major version, or
if RISK_TOOL_NO_SNAPSHOT is set (the test suite sets it). RISK_TOOL_SNAPSHOT_URL="" turns the refresh off.
"""

import copy
import functools
import hashlib
import inspect
import json
import os
import pickle  # only to hash unhashable table cells in key(); never to load data
import platform
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from ui import snapshot_format

PATH = Path(__file__).resolve().parent.parent / "data" / "snapshot" / "snapshot.zip"
SNAPSHOT, LIVE = "snapshot", "live"
MODE_KEY = "data_mode"  # session-state key of the sidebar choice
RECORD_ENV, DISABLE_ENV = "RISK_TOOL_SNAPSHOT_RECORD", "RISK_TOOL_NO_SNAPSHOT"
REMOTE_ENV = "RISK_TOOL_SNAPSHOT_URL"
REMOTE_URL = "https://raw.githubusercontent.com/singhwilliam15/Risk-Analysis-Tool/snapshot-data/"
HASH_ENV = "RISK_TOOL_SNAPSHOT_HASH_URL"  # where the expected sha256 is committed: main, not the data branch
HASH_URL = "https://raw.githubusercontent.com/singhwilliam15/Risk-Analysis-Tool/main/data/snapshot/published.json"
REMOTE_EVERY = 15 * 60  # seconds between checks for a newer published snapshot

_lock = threading.Lock()
_refresh_lock = threading.Lock()
_store = None  # {"meta": {...}, "data": {key: result}}, loaded once per process, replaced by a newer published one
_checked = None  # time.monotonic() of the last check for a published snapshot
_recorded = {}
_misses = []


# ---------------------------------------------------------------
# Keys
# ---------------------------------------------------------------

def _feed(h, obj) -> None:
    """Feed a canonical byte form of `obj` into the hash: equal inputs give equal keys in any process."""
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        names = obj.columns if isinstance(obj, pd.DataFrame) else [obj.name]
        h.update(f"{type(obj).__name__}|{list(map(str, names))}|"
                 f"{list(map(str, (obj.dtypes if isinstance(obj, pd.DataFrame) else [obj.dtype])))}|{obj.shape}".encode())
        try:
            h.update(pd.util.hash_pandas_object(obj, index=True).to_numpy().tobytes())
        except TypeError:  # unhashable cells (e.g. dicts): fall back to the pickle of the values
            h.update(pickle.dumps(obj, protocol=4))
    elif isinstance(obj, np.ndarray):
        h.update(f"nd|{obj.dtype}|{obj.shape}".encode())
        h.update(np.ascontiguousarray(obj).tobytes())
    elif isinstance(obj, dict):
        h.update(f"dict|{len(obj)}".encode())
        for k in sorted(obj, key=repr):
            _feed(h, k)
            _feed(h, obj[k])
    elif isinstance(obj, (list, tuple)):
        h.update(f"{type(obj).__name__}|{len(obj)}".encode())
        for item in obj:
            _feed(h, item)
    else:
        h.update(f"{type(obj).__name__}|{obj!r}".encode())


def key(name: str, args: tuple, kwargs: dict) -> str:
    h = hashlib.sha256(name.encode())
    _feed(h, list(args))
    _feed(h, kwargs)
    return h.hexdigest()


# ---------------------------------------------------------------
# The store
# ---------------------------------------------------------------

def versions() -> dict:
    return {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__}


def compatible(meta: dict) -> bool:
    """Same pandas version and numpy major version as the build (the stored results' input hashes need them)."""
    now = versions()
    return meta.get("pandas") == now["pandas"] and str(meta.get("numpy", "")).split(".")[0] == now["numpy"].split(".")[0]


def recording() -> bool:
    return bool(os.environ.get(RECORD_ENV))


def remote_url() -> str:
    """Base URL of the published snapshot ("" when the refresh is off)."""
    if os.environ.get(DISABLE_ENV) or recording():
        return ""
    return os.environ.get(REMOTE_ENV, REMOTE_URL)


def newer(info: dict, current: dict) -> bool:
    """Whether the snapshot described by `info` has later prices (or, on the same prices, a later build)."""
    if not current:
        return True
    order = lambda m: (str(m.get("prices_as_of") or ""), str(m.get("built") or ""))  # noqa: E731 (ISO strings)
    return order(info) > order(current)


def _fetch(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def hash_url() -> str:
    return os.environ.get(HASH_ENV, HASH_URL)


def _published(current: dict):
    """
    The published snapshot if main's published.json says it is newer than `current`, the zip downloaded from the
    data branch has exactly the sha256 committed on main, and its versions are compatible; otherwise None.
    """
    base = remote_url()
    if not base:
        return None
    try:
        expected = json.loads(_fetch(hash_url(), timeout=5))
        if not compatible(expected) or not newer(expected, current):
            return None
        blob = _fetch(base + "snapshot.zip", timeout=60)
        if hashlib.sha256(blob).hexdigest() != expected.get("sha256"):
            return None  # not the file main vouches for: tampered, partial, or published without its hash
        store = snapshot_format.loads(blob)
        return store if compatible(store.get("meta", {})) and newer(store["meta"], current) else None
    except Exception:  # offline, not published yet, or unreadable: keep what we have
        return None


def _refresh() -> None:
    """At most every REMOTE_EVERY seconds, one thread swaps in a newer published snapshot; others never wait."""
    global _store, _checked
    if not remote_url() or not _refresh_lock.acquire(blocking=False):
        return
    try:
        if _checked is not None and time.monotonic() - _checked < REMOTE_EVERY:
            return
        _checked = time.monotonic()
        store = _published((_store or {}).get("meta"))
        if store is not None:
            with _lock:
                _store = store
    finally:
        _refresh_lock.release()


def load(path: Path = None):
    """The snapshot, or None when it is missing, disabled or incompatible (then the app runs live)."""
    global _store
    if os.environ.get(DISABLE_ENV) or recording():
        return None
    path = Path(path or PATH)  # looked up at call time (tests point PATH elsewhere)
    with _lock:
        if _store is None:
            store = {}
            if path.exists():
                try:
                    candidate = snapshot_format.loads(path.read_bytes())
                    store = candidate if compatible(candidate.get("meta", {})) else {}
                except Exception:
                    store = {}
            _store = store
    _refresh()
    return _store or None


def reset() -> None:
    """Forget the loaded snapshot and the recording (tests)."""
    global _store, _checked
    with _lock:
        _store = None
        _checked = None
        _recorded.clear()
        _misses.clear()


def meta():
    store = load()
    return store["meta"] if store else None


def mode() -> str:
    """This session's choice: the snapshot when it is available and not switched off in the sidebar."""
    if load() is None:
        return LIVE
    try:
        import streamlit as st
        return st.session_state.get(MODE_KEY, SNAPSHOT)
    except Exception:
        return SNAPSHOT


def lookup(name: str, args: tuple, kwargs: dict):
    """(True, result) if the snapshot holds this call, else (False, None)."""
    store = load()
    if store is None:
        return False, None
    k = key(name, args, kwargs)
    if k in store["data"]:
        return True, store["data"][k]
    _misses.append(name)
    return False, None


def record(name: str, args: tuple, kwargs: dict, result) -> None:
    if recording():
        _recorded[key(name, args, kwargs)] = result


def misses() -> list:
    return list(_misses)


def save(path: Path = None, prices_as_of=None) -> dict:
    """Write everything recorded in this process; returns the meta."""
    import datetime
    info = {**versions(), "built": datetime.datetime.now().isoformat(timespec="seconds"),
            "prices_as_of": None if prices_as_of is None else pd.Timestamp(prices_as_of).isoformat(),
            "entries": len(_recorded)}
    path = Path(path or PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(snapshot_format.dumps({"meta": info, "data": dict(_recorded)}))
    return info


# ---------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------

def _bound(fn, args, kwargs) -> dict:
    """Arguments by name with defaults filled in, so f(x, "max") and f(x, period="max") share a key."""
    bound = inspect.signature(fn).bind(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)


def heavy(fn):
    """
    For a cached calculation: reuse the snapshot's result for exactly these inputs; record it when building.
    Used under st.cache_data, which hands each caller its own copy of the result.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        named = _bound(fn, args, kwargs)
        hit, result = lookup(fn.__name__, (), named)
        if hit:
            return result
        result = fn(*args, **kwargs)
        record(fn.__name__, (), named, result)
        return result
    return wrapper


def download(live_fn):
    """
    For a download: in snapshot mode, the stored download (prices to the snapshot date); otherwise, or for a call the
    snapshot does not hold, the live (Streamlit-cached) one. Not itself cached, so the mode is read on every call.
    """
    name = live_fn.__name__.lstrip("_")

    @functools.wraps(live_fn)
    def wrapper(*args, **kwargs):
        named = _bound(live_fn, args, kwargs)
        if mode() == SNAPSHOT:
            hit, result = lookup(name, (), named)
            if hit:
                return copy.deepcopy(result)  # callers may modify what they get; the store must not change
        result = live_fn(*args, **kwargs)
        record(name, (), named, result)
        return result
    return wrapper
