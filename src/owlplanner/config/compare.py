"""
Configuration comparison utilities.
"""

from __future__ import annotations
from typing import Any, Dict

from owlplanner.config.defaults import default_config
from owlplanner.config.schema import (
    CaseConfig,
    config_dict_to_model,
    model_to_config_dict,
)


# =========================================================
# Public API
# =========================================================

def compare_configs(
    a: dict,
    b: dict | None = None,
    *,
    mode: str = "compare",
    include_equal: bool = True,
    include_metadata: bool = True,
    flat: bool = False,
    reference: str = "b",
    path_filter: list[str] | None = None,
) -> dict:

    if mode not in {"compare", "diff", "describe"}:
        raise ValueError(f"Invalid mode '{mode}'")

    a_norm = _normalize_config(a)

    if b is None:
        b_norm = _normalize_config(default_config(_infer_ni(a)))
    else:
        b_norm = _normalize_config(b)

    if mode == "describe":
        result = _describe(a_norm, b_norm, include_metadata)
    else:
        result = _compare(a_norm, b_norm, include_metadata)

    # flatten AFTER building structured result
    if flat:
        pass  # already flat
    else:
        result = _unflatten_result(result)
        
    # filter equal
    if not include_equal:
        result = {k: v for k, v in result.items() if v["different"]}

    # diff mode
    if mode == "diff":
        result = {k: v for k, v in result.items() if v["different"]}

    # path filter
    if path_filter:
        result = {
            k: v for k, v in result.items()
            if any(k.startswith(p) for p in path_filter)
        }

    return result


# =========================================================
# Core comparison
# =========================================================

def _compare(a: dict, b: dict, include_metadata: bool) -> dict:
    flat_a = _flatten_values(a)
    flat_b = _flatten_values(b)

    keys = sorted(set(flat_a) | set(flat_b))

    out = {}

    for k in keys:
        va = flat_a.get(k)
        vb = flat_b.get(k)

        entry = {
            "a": va,
            "b": vb,
            "different": va != vb,
        }

        if include_metadata:
            desc = _get_description(k)
            if desc:
                entry["description"] = desc

        out[k] = entry

    return out


def _describe(a: dict, defaults: dict, include_metadata: bool) -> dict:
    flat_a = _flatten_values(a)
    flat_d = _flatten_values(defaults)

    keys = sorted(set(flat_a) | set(flat_d))

    out = {}

    for k in keys:
        va = flat_a.get(k)
        vd = flat_d.get(k)

        entry = {
            "value": va,
            "default": vd,
            "different": va != vd,
        }

        if include_metadata:
            desc = _get_description(k)
            if desc:
                entry["description"] = desc

        out[k] = entry

    return out


# =========================================================
# Normalization
# =========================================================

def _normalize_config(d: dict) -> dict:
    ni = _infer_ni(d)
    base = default_config(ni)
    merged = _deep_merge(base, d or {})

    model, extra = config_dict_to_model(merged)
    return model_to_config_dict(model, extra)


def _infer_ni(d: dict) -> int:
    try:
        names = d.get("basic_info", {}).get("names", [])
        return max(1, len(names))
    except Exception:
        return 1


# =========================================================
# Flatten helpers
# =========================================================

def _flatten_values(d: dict, prefix: str = "") -> Dict[str, Any]:
    """
    Flatten dict into path → raw value
    """
    out = {}

    if isinstance(d, dict):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            out.update(_flatten_values(v, key))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            key = f"{prefix}[{i}]"
            out.update(_flatten_values(v, key))
    else:
        out[prefix] = d

    return out


def _flatten_result(d: dict) -> dict:
    """
    Result is already flat → just return as-is
    """
    return d


# =========================================================
# Schema metadata
# =========================================================

def _get_description(path: str) -> str | None:
    parts = path.replace("]", "").split(".")

    model = CaseConfig

    for part in parts:
        if "[" in part:
            part = part.split("[")[0]

        if not hasattr(model, "model_fields"):
            return None

        field = model.model_fields.get(part)
        if not field:
            return None

        desc = field.description

        try:
            model = field.annotation
        except Exception:
            model = None

    return desc


# =========================================================
# Merge
# =========================================================

def _deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)

    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v

    return out

import re


import re


def _unflatten_result(flat: dict) -> dict:
    """
    Reconstruct nested structure from flattened keys.
    Handles multi-dimensional list indices like foo[0][1][2].
    """

    def parse_path(path: str):
        """
        Convert:
            "a.b[0][1].c"
        into:
            ["a", "b", 0, 1, "c"]
        """
        tokens = []
        for part in path.split("."):
            # split name + indices
            name_match = re.match(r"^[^\[]+", part)
            if name_match:
                tokens.append(name_match.group())

            for idx in re.findall(r"\[(\d+)\]", part):
                tokens.append(int(idx))

        return tokens

    root = {}

    for path, value in flat.items():
        tokens = parse_path(path)

        current = root
        for i, tok in enumerate(tokens):
            is_last = i == len(tokens) - 1

            if isinstance(tok, str):
                if is_last:
                    current[tok] = value
                else:
                    current = current.setdefault(tok, {})

            else:  # integer index → list
                if not isinstance(current, list):
                    # convert dict placeholder into list if needed
                    parent = current
                    current = []
                    # ⚠️ attach list back into parent
                    # find last string key used
                    # (safe because lists only follow keys)
                    last_key = tokens[i - 1]
                    parent[last_key] = current

                while len(current) <= tok:
                    current.append({})

                if is_last:
                    current[tok] = value
                else:
                    current = current[tok]

    return root
