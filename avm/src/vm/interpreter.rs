//! AVM 解释器

use crate::bytecode::{BytecodeModule, Instruction, OpCode, Operand, Constant};
use crate::utils::error::{AvmError, AvmResult};
use super::stack::{Stack, Value, CallFrame};
use std::collections::HashMap;

/// 解释器配置
#[derive(Debug, Clone)]
pub struct InterpreterConfig {
    pub max_stack_depth: usize,
    pub max_call_depth: usize,
    pub debug_mode: bool,
}

impl Default for InterpreterConfig {
    fn default() -> Self {
        Self {
            max_stack_depth: 1024,
            max_call_depth: 128,
            debug_mode: false,
        }
    }
}

/// 解释器状态
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InterpreterState {
    Ready,
    Running,
    Finished,
    Error,
}

/// 执行结果
#[derive(Debug, Clone)]
pub struct ExecutionResult {
    pub value: Value,
    pub instructions_executed: u64,
}

/// AVM 解释器
pub struct Interpreter {
    config: InterpreterConfig,
    stack: Stack,
    globals: HashMap<String, Value>,
    ip: u32,
    module: Option<BytecodeModule>,
    state: InterpreterState,
    instructions_executed: u64,
}

impl Interpreter {
    pub fn new(config: InterpreterConfig) -> Self {
        Self {
            stack: Stack::new(config.max_stack_depth),
            globals: HashMap::new(),
            ip: 0,
            module: None,
            state: InterpreterState::Ready,
            instructions_executed: 0,
            config,
        }
    }

    pub fn load_module(&mut self, module: BytecodeModule) {
        self.module = Some(module);
        self.ip = 0;
        self.state = InterpreterState::Ready;
    }

    pub fn run(&mut self) -> AvmResult<ExecutionResult> {
        if self.module.is_none() {
            return Err(AvmError::RuntimeError("No module loaded".to_string()));
        }

        self.state = InterpreterState::Running;
        self.ip = self.module.as_ref().unwrap().entry_point;
        self.instructions_executed = 0;

        while self.state == InterpreterState::Running {
            let instr = self.fetch_instruction()?;
            let should_halt = self.execute_instruction(&instr)?;
            self.instructions_executed += 1;
            if should_halt {
                break;
            }
        }

        self.state = InterpreterState::Finished;
        let value = if self.stack.depth() > 0 {
            self.stack.pop().unwrap_or(Value::Null)
        } else {
            Value::Null
        };

        Ok(ExecutionResult {
            value,
            instructions_executed: self.instructions_executed,
        })
    }

    fn fetch_instruction(&mut self) -> AvmResult<Instruction> {
        let module = self.module.as_ref()
            .ok_or_else(|| AvmError::RuntimeError("No module loaded".to_string()))?;
        let idx = self.ip as usize;
        if idx >= module.instructions.len() {
            return Err(AvmError::RuntimeError(format!("IP out of bounds: {}", self.ip)));
        }
        let instr = module.instructions[idx].clone();
        self.ip += 1;
        Ok(instr)
    }

    fn execute_instruction(&mut self, instr: &Instruction) -> AvmResult<bool> {
        match instr.opcode {
            OpCode::Nop => Ok(false),
            OpCode::Halt => Ok(true),
            OpCode::PushConst => self.exec_push_const(&instr.operand),
            OpCode::PushNull => { self.stack.push(Value::Null)?; Ok(false) }
            OpCode::PushTrue => { self.stack.push(Value::Bool(true))?; Ok(false) }
            OpCode::PushFalse => { self.stack.push(Value::Bool(false))?; Ok(false) }
            OpCode::Pop => { self.stack.pop()?; Ok(false) }
            OpCode::Add => self.exec_binary_op(|a, b| a + b),
            OpCode::Sub => self.exec_binary_op(|a, b| a - b),
            OpCode::Mul => self.exec_binary_op(|a, b| a * b),
            OpCode::Div => self.exec_binary_op(|a, b| a / b),
            OpCode::Eq => self.exec_compare(|a, b| a == b),
            OpCode::Ne => self.exec_compare(|a, b| a != b),
            OpCode::Jump => self.exec_jump(&instr.operand),
            OpCode::JumpIfTrue => self.exec_jump_if(true, &instr.operand),
            OpCode::JumpIfFalse => self.exec_jump_if(false, &instr.operand),
            _ => Err(AvmError::RuntimeError(format!("Unimplemented opcode: {:?}", instr.opcode))),
        }
    }

    fn exec_push_const(&mut self, operand: &Option<Operand>) -> AvmResult<bool> {
        let idx = match operand {
            Some(Operand::U32(idx)) => *idx,
            Some(Operand::U16(idx)) => *idx as u32,
            Some(Operand::U8(idx)) => *idx as u32,
            _ => return Err(AvmError::RuntimeError("Invalid PushConst operand".to_string())),
        };
        let module = self.module.as_ref().unwrap();
        let constant = module.constants.get(idx as usize)
            .ok_or_else(|| AvmError::RuntimeError(format!("Constant index out of bounds: {}", idx)))?;
        let value = self.constant_to_value(constant);
        self.stack.push(value)?;
        Ok(false)
    }

    fn exec_binary_op<F>(&mut self, op: F) -> AvmResult<bool>
    where F: Fn(f64, f64) -> f64 {
        let b = self.stack.pop()?;
        let a = self.stack.pop()?;
        let result = match (a, b) {
            (Value::Int(a), Value::Int(b)) => Value::Int(op(a as f64, b as f64) as i64),
            (Value::Float(a), Value::Float(b)) => Value::Float(op(a, b)),
            (Value::Int(a), Value::Float(b)) => Value::Float(op(a as f64, b)),
            (Value::Float(a), Value::Int(b)) => Value::Float(op(a, b as f64)),
            _ => return Err(AvmError::RuntimeError("Invalid operands".to_string())),
        };
        self.stack.push(result)?;
        Ok(false)
    }

    fn exec_compare<F>(&mut self, op: F) -> AvmResult<bool>
    where F: Fn(&Value, &Value) -> bool {
        let b = self.stack.pop()?;
        let a = self.stack.pop()?;
        self.stack.push(Value::Bool(op(&a, &b)))?;
        Ok(false)
    }

    fn exec_jump(&mut self, operand: &Option<Operand>) -> AvmResult<bool> {
        let offset = match operand {
            Some(Operand::JumpOffset(offset)) => *offset,
            _ => return Err(AvmError::RuntimeError("Invalid Jump operand".to_string())),
        };
        self.ip = offset as u32;
        Ok(false)
    }

    fn exec_jump_if(&mut self, expected: bool, operand: &Option<Operand>) -> AvmResult<bool> {
        let offset = match operand {
            Some(Operand::JumpOffset(offset)) => *offset,
            _ => return Err(AvmError::RuntimeError("Invalid JumpIf operand".to_string())),
        };
        let condition = self.stack.pop()?;
        if condition.is_truthy() == expected {
            self.ip = offset as u32;
        }
        Ok(false)
    }

    fn constant_to_value(&self, constant: &Constant) -> Value {
        match constant {
            Constant::Int(v) => Value::Int(*v),
            Constant::Float(v) => Value::Float(*v),
            Constant::String(v) => Value::String(v.clone()),
            Constant::Bool(v) => Value::Bool(*v),
            Constant::Null => Value::Null,
            _ => Value::Null,
        }
    }

    pub fn state(&self) -> InterpreterState {
        self.state
    }

    pub fn stack_depth(&self) -> usize {
        self.stack.depth()
    }
}

impl Default for Interpreter {
    fn default() -> Self {
        Self::new(InterpreterConfig::default())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_interpreter_creation() {
        let interp = Interpreter::default();
        assert_eq!(interp.state(), InterpreterState::Ready);
    }
}
