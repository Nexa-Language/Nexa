use nexa_avm::wasm::runtime::{WasmConfig, WasmRuntime, WasmValue};

fn runtime(source: &str, config: WasmConfig) -> WasmRuntime {
    let mut runtime = WasmRuntime::new(config);
    runtime
        .load_module("fixture", wat::parse_str(source).unwrap())
        .unwrap();
    runtime.instantiate("fixture").unwrap();
    runtime
}

#[cfg(not(feature = "wasm"))]
#[test]
fn missing_feature_fails_explicitly() {
    let mut runtime = runtime(
        "(module (func (export \"answer\") (result i32) i32.const 42))",
        WasmConfig::default(),
    );
    assert!(runtime
        .call("fixture", "answer", &[])
        .unwrap_err()
        .to_string()
        .contains("wasm feature"));
}

#[cfg(feature = "wasm")]
#[test]
fn executes_arguments_and_preserves_module_state() {
    let mut runtime = runtime(
        "(module (global $counter (mut i32) (i32.const 0))
        (func (export \"add\") (param i32) (result i32)
            global.get $counter local.get 0 i32.add global.set $counter global.get $counter))",
        WasmConfig::default(),
    );
    assert_eq!(
        runtime
            .call("fixture", "add", &[WasmValue::I32(2)])
            .unwrap(),
        vec![WasmValue::I32(2)]
    );
    assert_eq!(
        runtime
            .call("fixture", "add", &[WasmValue::I32(3)])
            .unwrap(),
        vec![WasmValue::I32(5)]
    );
}

#[cfg(feature = "wasm")]
#[test]
fn infinite_loop_exhausts_resources() {
    let config = WasmConfig {
        execution_timeout_ms: 10,
        ..WasmConfig::default()
    };
    let mut runtime = runtime(
        "(module (func (export \"loop\") (loop $again br $again)))",
        config,
    );
    let started = std::time::Instant::now();
    assert!(runtime.call("fixture", "loop", &[]).is_err());
    assert!(started.elapsed() < std::time::Duration::from_secs(5));
}

#[cfg(feature = "wasm")]
#[test]
fn memory_growth_obeys_configured_limit() {
    let config = WasmConfig {
        max_memory_pages: 1,
        ..WasmConfig::default()
    };
    let mut runtime = runtime(
        "(module (memory 1) (func (export \"grow\") (result i32) i32.const 1 memory.grow))",
        config,
    );
    assert_eq!(
        runtime.call("fixture", "grow", &[]).unwrap(),
        vec![WasmValue::I32(-1)]
    );
}

#[cfg(feature = "wasm")]
#[test]
fn host_and_guest_share_exported_memory() {
    let mut runtime = runtime(
        "(module (memory (export \"memory\") 1)
        (func (export \"load\") (result i32) i32.const 0 i32.load8_u)
        (func (export \"store\") i32.const 1 i32.const 43 i32.store8))",
        WasmConfig::default(),
    );
    runtime
        .get_instance("fixture")
        .unwrap()
        .write_memory(0, &[42])
        .unwrap();
    assert_eq!(
        runtime.call("fixture", "load", &[]).unwrap(),
        vec![WasmValue::I32(42)]
    );
    runtime.call("fixture", "store", &[]).unwrap();
    let instance = runtime.get_instance("fixture").unwrap();
    assert_eq!(instance.read_memory(1, 1).unwrap(), vec![43]);
    assert!(instance.read_memory(usize::MAX, 1).is_err());
    assert!(instance.write_memory(usize::MAX, &[1]).is_err());
}

#[test]
fn malformed_metadata_returns_error_without_panicking() {
    use nexa_avm::wasm::runtime::WasmModule;
    for section in [
        vec![7, 2, 1, 127],
        vec![0, 1, 127],
        vec![2, 1, 1],
        vec![7, 0xff, 0xff, 0xff, 0xff, 0x7f],
    ] {
        let mut bytes = b"\0asm\x01\0\0\0".to_vec();
        bytes.extend(section);
        let mut module = WasmModule::from_bytes("malformed", bytes).unwrap();
        assert!(module.parse_metadata().is_err());
    }
}
