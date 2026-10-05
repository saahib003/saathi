"""Canonical tool-argument hashes used to bind approvals."""

import hashlib
import json


def arguments_hash(arguments: dict) -> str:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

