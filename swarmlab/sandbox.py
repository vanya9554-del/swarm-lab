"""Safe WASM plugin sandbox: no WASI, no network, fuel-limited."""
from __future__ import annotations

import base64
import binascii
from typing import Any

from .store import SwarmError


def run_wasm(code: str, timeout_s: float = 2.0) -> dict[str, Any]:
    """Run a WASM/WAT module in an isolated wasmtime store.

    Imports are rejected (no WASI/network/filesystem), execution is fuel-limited,
    and only an exported run/main/_start function is called.
    """
    try:
        import wasmtime
    except ImportError as exc:  # pragma: no cover - runtime optional
        raise SwarmError("FORBIDDEN", "wasm sandbox unavailable") from exc
    if not str(code).strip():
        raise SwarmError("BAD_REQUEST", "code is required")
    try:
        wasm = wasmtime.wat2wasm(code) if str(code).lstrip().startswith("(module") else base64.b64decode(code, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SwarmError("BAD_REQUEST", "invalid wasm/wat") from exc
    try:
        config = wasmtime.Config()
        config.consume_fuel = True
        config.max_wasm_stack = 512 * 1024
        engine = wasmtime.Engine(config)
        module = wasmtime.Module(engine, wasm)
        store = wasmtime.Store(engine)
        store.set_fuel(20_000_000)
        linker = wasmtime.Linker(engine)
        instance = linker.instantiate(store, module)
        exports = instance.exports(store)
        func = None
        for name in ("run", "main", "_start"):
            candidate = exports.get(name) if hasattr(exports, "get") else None
            if callable(candidate):
                func = candidate
                break
        if func is None:
            raise SwarmError("BAD_REQUEST", "plugin must export run/main/_start")
        result = func(store)
        return {"ok": True, "result": result, "fuel_left": store.get_fuel()}
    except SwarmError:
        raise
    except Exception as exc:  # noqa: BLE001 - sandbox must turn any trap into 400
        raise SwarmError("BAD_REQUEST", f"sandbox error: {exc}") from exc
