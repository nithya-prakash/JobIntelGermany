# German Job Market Intelligence — LLM serving readiness

Generated: 2026-10-04T20:43:49.251322+00:00

**Decision:** blocked_no_benchmark. No inference or quantization benchmark was run.

## Runtime and artifact

- Host: macOS-15.7.9-arm64-arm-64bit-Mach-O.
- Model path exists: False.
- Fine-tuned model from Phase 8: False.
- Serving packages available: none.

## Benchmark results

| Format | Latency | Throughput | Tokens/sec | Memory |
| --- | ---: | ---: | ---: | ---: |
| FP16/BF16 | not measured | not measured | not measured | not measured |
| 8-bit | not measured | not measured | not measured | not measured |
| 4-bit | not measured | not measured | not measured | not measured |

## Blockers

- Phase 8 did not produce a fine-tuned model artifact
- no selected model artifact exists at models/finetuned-skill-extractor
- vLLM is not installed
- Apple Silicon serving requires the separate MLX/vLLM-Metal runtime, which is absent
- no compatible model serving runtime is available

The upstream vLLM project documents Apple Silicon through a separate vLLM-Metal path that uses MLX-compatible models. That runtime is not installed here. Do not compare CPU and GPU throughput or quantization quality until the same selected model and workload can be run on a supported backend.

## Reproduction

Run `.venv/bin/gjmi-serve audit` after placing a selected model at the configured path and installing its documented local serving backend.
