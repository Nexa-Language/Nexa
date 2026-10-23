use nexa_avm::bytecode::{BytecodeCompiler, BytecodeModule, OpCode, Operand};
use nexa_avm::compiler::Parser as NexaParser;
use nexa_avm::vm::interpreter::{Interpreter, InterpreterConfig, InterpreterState};
use nexa_avm::vm::stack::Value;

#[test]
fn shared_python_rust_programs() {
    let cases: serde_json::Value = serde_json::from_str(include_str!(
        "../../tests/fixtures/conformance/programs.json"
    ))
    .unwrap();
    for case in cases.as_array().unwrap() {
        let source = case["source"].as_str().unwrap();
        let program = NexaParser::parse_from_source(source).unwrap();
        let module = BytecodeCompiler::new(case["name"].as_str().unwrap().into())
            .compile(&program)
            .unwrap();
        let mut vm = Interpreter::new(InterpreterConfig::default());
        if let Some(reply) = case["model_reply"].as_str() {
            let reply = reply.to_owned();
            let input = case["agent_input"].as_str().unwrap().to_owned();
            vm.set_agent_executor(move |definition, arguments| {
                assert_eq!(
                    definition["prompt"],
                    Value::String("Repeat accurately".into())
                );
                assert_eq!(arguments, &[Value::String(input.clone())]);
                Ok(Value::String(reply.clone()))
            });
        }
        vm.load_module(module);
        let result = vm
            .run()
            .unwrap_or_else(|error| panic!("case {}: {error}", case["name"]));
        let actual = match result.value {
            Value::Int(n) => serde_json::json!(n),
            Value::Float(n) => serde_json::json!(n),
            Value::String(s) => serde_json::json!(s),
            value => panic!("Unexpected value {value:?}"),
        };
        assert_eq!(actual, case["expected"], "{}", case["name"]);
    }
}

#[test]
fn unsupported_instruction_is_an_error() {
    let mut module = BytecodeModule::new("unsupported".into());
    module.emit(OpCode::ForkAgent, None, None);
    let mut vm = Interpreter::new(InterpreterConfig::default());
    vm.load_module(module);
    assert!(vm
        .run()
        .unwrap_err()
        .to_string()
        .contains("Unimplemented opcode"));
    assert_eq!(vm.state(), InterpreterState::Error);
}

#[test]
fn instruction_budget_stops_an_infinite_loop() {
    let mut module = BytecodeModule::new("loop".into());
    module.emit(OpCode::Jump, Some(Operand::JumpOffset(0)), None);
    let mut vm = Interpreter::new(InterpreterConfig::default());
    vm.set_instruction_limit(10);
    vm.load_module(module);
    assert!(vm.run().unwrap_err().to_string().contains("budget"));
}
