//! Local interpreter baseline; consumes the same non-model cases as Python.
use nexa_avm::bytecode::BytecodeCompiler;
use nexa_avm::compiler::Parser;
use nexa_avm::vm::interpreter::{Interpreter, InterpreterConfig};
use nexa_avm::vm::stack::Value;
use serde_json::{json, Value as Json};
use std::time::Instant;

fn main() {
    let cases: Vec<Json> = serde_json::from_str(include_str!(
        "../../tests/fixtures/conformance/programs.json"
    ))
    .unwrap();
    let mut results = Vec::new();
    for case in cases
        .iter()
        .filter(|case| case.get("model_reply").is_none())
    {
        let initialized = Instant::now();
        let program = Parser::parse_from_source(case["source"].as_str().unwrap()).unwrap();
        let module = BytecodeCompiler::new(case["name"].as_str().unwrap().into())
            .compile(&program)
            .unwrap();
        let initialization_ms = initialized.elapsed().as_secs_f64() * 1000.0;
        let mut samples = Vec::new();
        for iteration in 0..1050 {
            let started = Instant::now();
            let mut vm = Interpreter::new(InterpreterConfig::default());
            vm.load_module(module.clone());
            let result = vm.run().unwrap();
            let elapsed = started.elapsed().as_secs_f64() * 1e6;
            let actual = match result.value {
                Value::Int(value) => json!(value),
                Value::Float(value) => json!(value),
                other => panic!("Unexpected result: {other:?}"),
            };
            assert_eq!(actual, case["expected"]);
            if iteration >= 50 {
                samples.push(elapsed);
            }
        }
        samples.sort_by(f64::total_cmp);
        results.push(
            json!({"name": case["name"], "initialization_ms": initialization_ms,
            "median_us": (samples[499] + samples[500]) / 2.0, "p95_us": samples[949]}),
        );
    }
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"schema_version": 1, "backend": "rust",
            "profile": if cfg!(debug_assertions) { "debug" } else { "release" },
            "os": std::env::consts::OS, "arch": std::env::consts::ARCH,
            "samples": 1000, "warmup": 50, "concurrency": 1, "provider_calls": 0,
            "scope": "interpreter initialization, bytecode clone/load and execution",
            "cases": results}))
        .unwrap()
    );
}
