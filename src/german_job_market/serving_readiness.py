"""Audit local LLM serving and quantization benchmark prerequisites."""

from __future__ import annotations

import importlib.util
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_RUNTIME_PACKAGES = ("vllm", "mlx", "mlx_lm", "llmcompressor")


def _markdown(report: dict[str, Any]) -> str:
    runtime = report["runtime"]
    blockers = report["blockers"]
    available_packages = (
        ", ".join(name for name, available in runtime["packages"].items() if available) or "none"
    )
    lines = [
        "# German Job Market Intelligence — LLM serving readiness",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        f"**Decision:** {report['decision']}. No inference or quantization benchmark was run.",
        "",
        "## Runtime and artifact",
        "",
        f"- Host: {runtime['platform']}.",
        f"- Model path exists: {report['model_artifact']['exists']}.",
        f"- Fine-tuned model from Phase 8: {report['phase8_model']['trained']}.",
        f"- Serving packages available: {available_packages}.",
        "",
        "## Benchmark results",
        "",
        "| Format | Latency | Throughput | Tokens/sec | Memory |",
        "| --- | ---: | ---: | ---: | ---: |",
        "| FP16/BF16 | not measured | not measured | not measured | not measured |",
        "| 8-bit | not measured | not measured | not measured | not measured |",
        "| 4-bit | not measured | not measured | not measured | not measured |",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- {blocker}" for blocker in blockers)
    lines.extend(
        [
            "",
            "The upstream vLLM project documents Apple Silicon through a separate vLLM-Metal path "
            "that uses MLX-compatible models. That runtime is not installed here. Do not compare "
            "CPU and GPU throughput or quantization quality until the same selected model and "
            "workload can be run on a supported backend.",
            "",
            "## Reproduction",
            "",
            "Run `.venv/bin/gjmi-serve audit` after placing a selected model at the configured "
            "path and installing its documented local serving backend.",
            "",
        ]
    )
    return "\n".join(lines)


def audit_serving_readiness(
    phase8_report_path: Path,
    model_path: Path,
    json_path: Path,
    markdown_path: Path,
) -> dict[str, Any]:
    """Inspect artifacts and local backends without downloading or serving a model."""
    phase8_report = (
        json.loads(phase8_report_path.read_text(encoding="utf-8"))
        if phase8_report_path.is_file()
        else None
    )
    phase8_model = (
        phase8_report.get("fine_tuned_model", {"trained": False})
        if phase8_report is not None
        else {"trained": False}
    )
    packages = {name: importlib.util.find_spec(name) is not None for name in _RUNTIME_PACKAGES}
    model_exists = model_path.exists()
    blockers: list[str] = []
    if phase8_model.get("trained") is not True:
        blockers.append("Phase 8 did not produce a fine-tuned model artifact")
    if not model_exists:
        blockers.append(f"no selected model artifact exists at {model_path}")
    if not packages["vllm"]:
        blockers.append("vLLM is not installed")
    if platform.system() == "Darwin" and not (packages["mlx"] and packages["mlx_lm"]):
        blockers.append(
            "Apple Silicon serving requires the separate MLX/vLLM-Metal runtime, which is absent"
        )
    if not any(packages[name] for name in ("vllm", "mlx_lm")):
        blockers.append("no compatible model serving runtime is available")

    report: dict[str, Any] = {
        "phase": 9,
        "audit_type": "llm_serving_and_quantization_readiness",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "decision": "blocked_no_benchmark" if blockers else "ready_for_benchmark_review",
        "inputs": {
            "phase8_report_path": phase8_report_path.name,
            "model_path": str(model_path),
        },
        "phase8_model": phase8_model,
        "model_artifact": {"exists": model_exists},
        "runtime": {"platform": platform.platform(), "packages": packages},
        "benchmark_results": None,
        "blockers": blockers,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return report
