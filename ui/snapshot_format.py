"""
The demo snapshot's file format (NEXT_STEPS_V5 Phase H): a zip of JSON and Parquet, so loading it can never run code.

    snapshot.zip
      meta.json            versions, build time, prices_as_of, entries
      tree.json            the stored results as tagged JSON (see `encode`)
      tables/NNNN.parquet  every DataFrame, Series and ndarray, with its exact dtypes and index in tree.json

Tagged nodes are dicts with a "__t" key: tuple, dict (non-string keys), np (numpy scalar with its dtype), ts
(pandas.Timestamp with its unit), garch (garch.GarchParams), table (a Parquet member). Floats keep full precision
(repr) and NaN/inf are allowed. Tables are cast back to their recorded dtypes after reading, because Parquet stores
datetime64[s] as milliseconds and the snapshot's lookups hash the exact inputs (ui/snapshot.key).
"""

import dataclasses
import io
import json
import zipfile

import numpy as np
import pandas as pd

TAG = "__t"
TABLES = "tables/"


# ---------------------------------------------------------------
# Tables
# ---------------------------------------------------------------

def _index_spec(index: pd.Index, prefix: str, frame: dict) -> dict:
    """Describe an index; non-range values are added to `frame` as column `prefix`."""
    if isinstance(index, pd.RangeIndex):
        return {"kind": "range", "start": index.start, "stop": index.stop, "step": index.step,
                "name": encode(index.name, [])}
    if isinstance(index, pd.MultiIndex):
        raise TypeError("MultiIndex is not supported in the snapshot")
    frame[prefix] = index.to_numpy()
    spec = {"kind": "values", "dtype": str(index.dtype), "name": encode(index.name, [])}
    if isinstance(index, pd.DatetimeIndex) and index.freq is not None:
        spec["freq"] = index.freqstr
    return spec


def _restore_index(spec: dict, values=None) -> pd.Index:
    if spec["kind"] == "range":
        return pd.RangeIndex(spec["start"], spec["stop"], spec["step"], name=decode(spec["name"], {}))
    index = pd.Index(pd.Series(values).astype(spec["dtype"]), name=decode(spec["name"], {}))
    if spec.get("freq"):
        index = pd.DatetimeIndex(index, freq=spec["freq"])
    return index


def table_to_parquet(obj) -> tuple:
    """(spec, parquet bytes) for a DataFrame, Series or ndarray."""
    frame = {}
    if isinstance(obj, np.ndarray):
        spec = {"kind": "nd", "dtype": str(obj.dtype), "shape": list(obj.shape)}
        frame["v"] = obj.ravel(order="C")
    elif isinstance(obj, pd.Series):
        spec = {"kind": "series", "dtype": str(obj.dtype), "name": encode(obj.name, []), "rows": len(obj),
                "index": _index_spec(obj.index, "i", frame)}
        frame["c0"] = obj.to_numpy()
    elif isinstance(obj, pd.DataFrame):
        cols = obj.columns
        spec = {"kind": "df", "rows": len(obj), "dtypes": [str(t) for t in obj.dtypes],
                "index": _index_spec(obj.index, "i", frame),
                "columns": _index_spec(cols, "_unused", {}) if isinstance(cols, pd.RangeIndex)
                else {"kind": "labels", "labels": [encode(c, []) for c in cols], "dtype": str(cols.dtype),
                      "name": encode(cols.name, [])}}
        for j in range(obj.shape[1]):
            frame[f"c{j}"] = obj.iloc[:, j].to_numpy()
    else:
        raise TypeError(type(obj))
    buf = io.BytesIO()
    pd.DataFrame(frame).to_parquet(buf, engine="pyarrow", compression="zstd", index=False)
    return spec, buf.getvalue()


def table_from_parquet(spec: dict, blob: bytes):
    data = pd.read_parquet(io.BytesIO(blob), engine="pyarrow")
    if spec["kind"] == "nd":
        return data["v"].to_numpy().astype(spec["dtype"]).reshape(spec["shape"], order="C")
    if spec["kind"] == "series":
        index = _restore_index(spec["index"], data["i"] if "i" in data else None)
        return pd.Series(data["c0"].astype(spec["dtype"]).to_numpy(), index=index, name=decode(spec["name"], {}))
    index = _restore_index(spec["index"], data["i"] if "i" in data else None)
    columns = spec["columns"]
    if columns["kind"] == "range":
        labels = _restore_index(columns)
    else:
        labels = pd.Index([decode(c, {}) for c in columns["labels"]], dtype=columns["dtype"],
                          name=decode(columns["name"], {}))
    out = pd.DataFrame({j: data[f"c{j}"].astype(t).to_numpy() for j, t in enumerate(spec["dtypes"])}, index=index)
    if not len(spec["dtypes"]):
        out = pd.DataFrame(index=index)
    out.columns = labels
    return out


# ---------------------------------------------------------------
# Tagged JSON
# ---------------------------------------------------------------

def encode(obj, tables: list):
    """JSON-ready form of `obj`; DataFrames, Series and ndarrays are appended to `tables` and referenced."""
    if obj is None or isinstance(obj, (str, bool)) and not isinstance(obj, np.generic):
        return obj
    if isinstance(obj, np.generic):
        return {TAG: "np", "dtype": str(obj.dtype), "v": obj.item()}
    if isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, pd.Timestamp):
        return {TAG: "ts", "v": obj.isoformat(), "unit": obj.unit, "tz": None if obj.tz is None else str(obj.tz)}
    if dataclasses.is_dataclass(obj) and type(obj).__name__ == "GarchParams":
        return {TAG: "garch", "v": {f.name: encode(getattr(obj, f.name), tables) for f in dataclasses.fields(obj)}}
    if isinstance(obj, tuple):
        return {TAG: "tuple", "v": [encode(v, tables) for v in obj]}
    if isinstance(obj, list):
        return [encode(v, tables) for v in obj]
    if isinstance(obj, dict):
        if all(isinstance(k, str) for k in obj) and TAG not in obj:
            return {k: encode(v, tables) for k, v in obj.items()}
        return {TAG: "dict", "v": [[encode(k, tables), encode(v, tables)] for k, v in obj.items()]}
    if isinstance(obj, (pd.DataFrame, pd.Series, np.ndarray)):
        tables.append(table_to_parquet(obj))
        return {TAG: "table", "id": len(tables) - 1}
    raise TypeError(f"cannot store {type(obj).__module__}.{type(obj).__name__} in the snapshot")


def decode(node, tables: dict):
    if isinstance(node, list):
        return [decode(v, tables) for v in node]
    if not isinstance(node, dict):
        return node
    kind = node.get(TAG)
    if kind is None:
        return {k: decode(v, tables) for k, v in node.items()}
    if kind == "np":
        return np.dtype(node["dtype"]).type(node["v"])
    if kind == "ts":
        ts = pd.Timestamp(node["v"])
        return ts.as_unit(node["unit"])
    if kind == "garch":
        from garch import GarchParams
        return GarchParams(**{k: decode(v, tables) for k, v in node["v"].items()})
    if kind == "tuple":
        return tuple(decode(v, tables) for v in node["v"])
    if kind == "dict":
        return {_hashable(decode(k, tables)): decode(v, tables) for k, v in node["v"]}
    if kind == "table":
        return tables[node["id"]]
    raise ValueError(f"unknown snapshot node {kind!r}")


def _hashable(key):
    return tuple(_hashable(k) for k in key) if isinstance(key, list) else key


# ---------------------------------------------------------------
# The zip
# ---------------------------------------------------------------

def dumps(store: dict) -> bytes:
    """{"meta": {...}, "data": {key: result}} → zip bytes."""
    tables = []
    tree = encode(store["data"], tables)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("meta.json", json.dumps(store["meta"], indent=1), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("tree.json", json.dumps({"tables": [spec for spec, _ in tables], "data": tree}),
                   compress_type=zipfile.ZIP_DEFLATED)
        for i, (_, blob) in enumerate(tables):
            z.writestr(f"{TABLES}{i:05d}.parquet", blob, compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


def read_meta(blob: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return json.loads(z.read("meta.json"))


def loads(blob: bytes) -> dict:
    """zip bytes → {"meta": {...}, "data": {key: result}}. Only JSON and Parquet are read."""
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        meta = json.loads(z.read("meta.json"))
        tree = json.loads(z.read("tree.json"))
        tables = {i: table_from_parquet(spec, z.read(f"{TABLES}{i:05d}.parquet")) for i, spec in enumerate(tree["tables"])}
    return {"meta": meta, "data": decode(tree["data"], tables)}
