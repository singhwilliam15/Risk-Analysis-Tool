"""
Minimal schemas for the website JSON (site_data/build.py). A tiny checker, no extra dependency: each schema maps a
key to its type (or a nested schema); lists give the schema of their items.
"""

SUMMARY = {"question": str, "status": str, "verdict": str, "facts": [{"label": str, "value": str, "so_what": str}],
           "grades": [{"label": str, "name": str, "grade": str, "reasons": list}], "action": str, "methods": [str],
           "chips": [{"id": str, "signal": str, "badge": str, "lift": str, "window": str, "beyond_momentum": str}]}
SCHEMAS = {
    "page": {"preset": str, "preset_label": str, "page": str, "title": str, "app_link": str, "summary": SUMMARY,
             "sections": [{"title": str, "items": [dict]}], "data_note": str, "built": str, "stale": bool},
    "presets": [{"slug": str, "label": str, "kind": str, "stale": bool}],
    "evidence": {"signals": [{"id": str, "signal": str, "badge": str, "lift": str, "beyond_momentum": str,
                              "window": str, "note": str}],
                 "margin_trigger": dict, "case_tally": dict, "decisions": dict},
    "glossary": [{"plain": str, "technical": str, "definition": str, "section": str}],
}
STATUS_WORDS = ("Clear", "Watch", "Warning")
ITEM_TYPES = {"table", "chart", "metric", "note", "text"}


def _check(value, schema, path: str) -> list:
    if isinstance(schema, type):
        return [] if isinstance(value, schema) else [f"{path}: expected {schema.__name__}, got {type(value).__name__}"]
    if isinstance(schema, list):
        if not isinstance(value, list):
            return [f"{path}: expected a list"]
        return [e for i, v in enumerate(value) for e in _check(v, schema[0], f"{path}[{i}]")]
    if not isinstance(value, dict):
        return [f"{path}: expected an object"]
    missing = [f"{path}.{k}: missing" for k in schema if k not in value]
    return missing + [e for k, s in schema.items() if k in value for e in _check(value[k], s, f"{path}.{k}")]


def errors(payload, kind: str) -> list:
    errs = _check(payload, SCHEMAS[kind], kind)
    if kind == "page" and not errs:
        if payload["summary"]["status"] not in STATUS_WORDS:
            errs.append("page.summary.status: not a status word")
        errs += [f"page.sections: unknown item type {i.get('type')}" for s in payload["sections"] for i in s["items"]
                 if i.get("type") not in ITEM_TYPES]
    return errs


def validate(payload, kind: str) -> None:
    errs = errors(payload, kind)
    if errs:
        raise ValueError("; ".join(errs[:10]))
