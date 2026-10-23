"""Measure local Python execution of the shared arithmetic corpus, without a model."""
from __future__ import annotations

import json
import platform
import statistics
import time
from pathlib import Path
from typing import Any

from src.compiler import compile_source

SAMPLES = 1000
WARMUP = 50


def measure(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter_ns()
    compilation = compile_source(case['source'])
    namespace: dict[str, Any] = {'__name__': 'nexa_benchmark'}
    exec(compile(compilation.python_code, '<benchmark>', 'exec'), namespace)  # noqa: S102 - Executes the fixed repository corpus.
    initialization_ns = time.perf_counter_ns() - started
    run = namespace['flow_main']
    for _ in range(WARMUP):
        assert run() == case['expected']
    durations = []
    for _ in range(SAMPLES):
        started = time.perf_counter_ns()
        result = run()
        durations.append(time.perf_counter_ns() - started)
        assert result == case['expected']
    return {'name': case['name'], 'initialization_ms': initialization_ns / 1e6,
            'median_us': statistics.median(durations) / 1000, 'p95_us': sorted(durations)[949] / 1000}


def main() -> None:
    corpus = Path(__file__).resolve().parents[1] / 'tests/fixtures/conformance/programs.json'
    cases = json.loads(corpus.read_text())
    report = {'schema_version': 1, 'backend': 'python', 'version': platform.python_version(),
              'platform': platform.platform(), 'samples': SAMPLES, 'warmup': WARMUP, 'concurrency': 1,
              'provider_calls': 0, 'scope': 'compiled flow invocation, including flow runtime scope',
              'cases': [measure(case) for case in cases if 'model_reply' not in case]}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
