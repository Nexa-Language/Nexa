/*
# ========================================================================
Copyright (C) 2026 Nexa-Language
This file is part of Nexa Project.

Nexa is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

Nexa is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
========================================================================
*/

//! AVM 解释器
//!
//! Design by Contract (契约式编程) 集成说明:
//! - 契约检查在 AST 级别执行（而非字节码级别）
//! - 当 AVM 运行时处理 Agent 调用时，先检查 requires，后检查 ensures
//! - ContractViolation 错误通过 AvmError::RuntimeError 传播
//! - requires 失败 → 跳过执行或抛 ContractViolation
//! - ensures 失败 → 触发 retry/fallback 或抛 ContractViolation

use crate::bytecode::{BytecodeModule, Instruction, OpCode, Operand, Constant};
use crate::utils::error::{AvmError, AvmResult};
use crate::runtime::contracts::{check_requires, check_ensures, capture_old_values};
use crate::runtime::result_types::{NexaResult, NexaOption, ErrorPropagation, OtherwiseHandlerCtx, PropagationResult, propagate_or_else};
use crate::compiler::ast::{ContractSpec, Statement, OtherwiseHandler};
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
    
    // ==================== Design by Contract (契约式编程) ====================
    
    /// 检查 Agent 的前置契约 (requires)
    ///
    /// 在 Agent 执行前调用。如果 requires 失败，返回 AvmError。
    /// 语义契约在 AVM 端暂时默认通过（需要 LLM 客户端异步评估）。
    pub fn check_agent_requires(
        &mut self,
        contracts: &ContractSpec,
        context: &HashMap<String, Value>,
    ) -> AvmResult<()> {
        check_requires(contracts, context)
    }
    
    /// 检查 Agent 的后置契约 (ensures)
    ///
    /// 在 Agent 执行后调用。如果 ensures 失败，返回 AvmError。
    /// 语义契约在 AVM 端暂时默认通过。
    pub fn check_agent_ensures(
        &mut self,
        contracts: &ContractSpec,
        context: &HashMap<String, Value>,
        result: &Value,
        old_values: &HashMap<String, Value>,
    ) -> AvmResult<()> {
        check_ensures(contracts, context, result, old_values)
    }
    
    /// 捕获 old() 值（用于后置条件比较）
    ///
    /// 在 Agent 执行前调用，记录入口时的变量值。
    pub fn capture_contract_old_values(
        &self,
        contracts: &ContractSpec,
        context: &HashMap<String, Value>,
    ) -> HashMap<String, Value> {
        capture_old_values(contracts, context)
    }

    // ==================== v1.2: Error Propagation (? 操作符 + otherwise) ====================
    
    /// 执行 ? 操作符赋值语句 — TryAssignment
    ///
    /// x = expr? → 对 expr 结果执行 unwrap
    /// - NexaResult::Ok → 返回值赋给 target
    /// - NexaResult::Err → 触发 ErrorPropagation (early-return)
    /// - NexaOption::Some → 返回值赋给 target
    /// - NexaOption::None → 触发 ErrorPropagation (early-return)
    pub fn exec_try_assignment(
        &mut self,
        target: &str,
        expression_value: &Value,
    ) -> AvmResult<PropagationResult> {
        // 将值包装为 NexaResult 并执行 propagate_or_else
        let result = if self.is_nexa_result(expression_value) {
            // 已经是 NexaResult，直接使用
            self.value_to_nexa_result(expression_value)
        } else {
            // 普通值 → 包装为 NexaResult::Ok
            NexaResult::Ok(expression_value.clone())
        };
        
        let propagation = propagate_or_else(&result, None);
        
        match propagation {
            PropagationResult::Ok(value) => {
                // 成功 → 赋值给 target
                self.globals.insert(target.to_string(), value.clone());
                Ok(PropagationResult::Ok(value))
            }
            PropagationResult::Propagate(error) => {
                // 失败 → ErrorPropagation
                Err(AvmError::RuntimeError(format!("Error propagation: {}", error.error)))
            }
            PropagationResult::Fallback(value) => {
                // 不应到达这里（? 操作符没有 otherwise handler）
                self.globals.insert(target.to_string(), value.clone());
                Ok(PropagationResult::Fallback(value))
            }
        }
    }
    
    /// 执行 otherwise 内联错误处理赋值语句 — OtherwiseAssignment
    ///
    /// x = expr otherwise handler → 对 expr 结果执行 unwrap_or_else
    /// - NexaResult::Ok → 返回值赋给 target
    /// - NexaResult::Err → 执行 handler 作为 fallback
    pub fn exec_otherwise_assignment(
        &mut self,
        target: &str,
        expression_value: &Value,
        handler: &OtherwiseHandler,
    ) -> AvmResult<Value> {
        // 将值包装为 NexaResult
        let result = if self.is_nexa_result(expression_value) {
            self.value_to_nexa_result(expression_value)
        } else {
            NexaResult::Ok(expression_value.clone())
        };
        
        if result.is_ok() {
            // 成功 → 返回值
            let value = match result {
                NexaResult::Ok(v) => v,
                NexaResult::Err(_) => Value::Null,
            };
            self.globals.insert(target.to_string(), value.clone());
            return Ok(value);
        }
        
        // 失败 → 执行 handler
        let fallback_value = self.exec_otherwise_handler(handler, &result)?;
        self.globals.insert(target.to_string(), fallback_value.clone());
        Ok(fallback_value)
    }
    
    /// 执行 otherwise handler
    ///
    /// handler 可以是:
    /// - OtherwiseHandler::AgentCall → Agent.run_result() 作为 fallback
    /// - OtherwiseHandler::Value → 直接返回值
    /// - OtherwiseHandler::Variable → 返回变量值
    /// - OtherwiseHandler::Block → 执行代码块
    fn exec_otherwise_handler(
        &mut self,
        handler: &OtherwiseHandler,
        result: &NexaResult,
    ) -> AvmResult<Value> {
        match handler {
            OtherwiseHandler::AgentCall { agent_name, args } => {
                // Agent fallback: 在 AVM 中简化为字符串标记
                // 实际 Agent 调用需要异步运行时支持
                Ok(Value::String(format!("fallback:{}", agent_name)))
            }
            OtherwiseHandler::Value(value_str) => {
                Ok(Value::String(value_str.clone()))
            }
            OtherwiseHandler::Variable(var_name) => {
                // 从全局变量中获取值
                self.globals.get(var_name)
                    .cloned()
                    .ok_or_else(|| AvmError::RuntimeError(format!("Variable '{}' not found for otherwise handler", var_name)))
            }
            OtherwiseHandler::Block(statements) => {
                // 执行代码块中的语句
                // 简化处理：返回最后一个语句的结果
                let mut last_value = Value::Null;
                for stmt in statements {
                    // 这里需要 AST 级别的语句执行
                    // 当前简化为返回 Null
                    // 完整实现需要递归执行每条语句
                }
                Ok(last_value)
            }
        }
    }
    
    /// 检查值是否是 NexaResult
    ///
    /// 在 AVM 中，NexaResult 以特殊的字典形式存储：
    /// {"_nexa_result": true, "is_ok": true/false, "value": ..., "error": ...}
    fn is_nexa_result(&self, value: &Value) -> bool {
        // 简化判断：当前 AVM Value 不直接支持 NexaResult 类型标记
        // 后续可以通过 Value 扩展或特殊标记来区分
        false
    }
    
    /// 将 Value 转换为 NexaResult
    ///
    /// 如果值已经是 NexaResult 标记形式，则解析
    /// 否则包装为 NexaResult::Ok
    fn value_to_nexa_result(&self, value: &Value) -> NexaResult {
        NexaResult::Ok(value.clone())
    }
    
    /// 执行 AST 级别的语句（支持 ? 和 otherwise）
    ///
    /// 当 AVM 需要直接执行 AST 而非字节码时使用此方法。
    /// 主要用于 TryAssignment、OtherwiseAssignment、TryExpression
    pub fn exec_ast_statement(&mut self, stmt: &Statement) -> AvmResult<Option<Value>> {
        match stmt {
            Statement::TryAssignment { target, expression } => {
                // 评估表达式
                let value = self.eval_ast_expression(expression)?;
                let result = self.exec_try_assignment(target, &value)?;
                match result {
                    PropagationResult::Ok(v) => Ok(Some(v)),
                    PropagationResult::Propagate(e) => {
                        Err(AvmError::RuntimeError(format!("Error propagation: {}", e.error)))
                    }
                    PropagationResult::Fallback(v) => Ok(Some(v)),
                }
            }
            Statement::OtherwiseAssignment { target, expression, handler } => {
                // 评估表达式
                let value = self.eval_ast_expression(expression)?;
                let result = self.exec_otherwise_assignment(target, &value, handler)?;
                Ok(Some(result))
            }
            Statement::TryExpression(expression) => {
                // 评估表达式
                let value = self.eval_ast_expression(expression)?;
                let nexa_result = NexaResult::Ok(value);
                let propagation = propagate_or_else(&nexa_result, None);
                match propagation {
                    PropagationResult::Ok(v) => Ok(Some(v)),
                    PropagationResult::Propagate(e) => {
                        Err(AvmError::RuntimeError(format!("Error propagation: {}", e.error)))
                    }
                    PropagationResult::Fallback(v) => Ok(Some(v)),
                }
            }
            _ => Err(AvmError::RuntimeError(format!("Unsupported AST statement type for direct execution")))
        }
    }
    
    /// 评估 AST 表达式（简化版）
    ///
    /// 在完整实现中，这应该递归评估 AST Expression。
    /// 当前简化版只处理基本表达式类型。
    fn eval_ast_expression(&self, expr: &crate::compiler::ast::Expression) -> AvmResult<Value> {
        use crate::compiler::ast::Expression;
        match expr {
            Expression::String(s) => Ok(Value::String(s.clone())),
            Expression::Integer(n) => Ok(Value::Int(*n)),
            Expression::Float(f) => Ok(Value::Float(*f)),
            Expression::Bool(b) => Ok(Value::Bool(*b)),
            Expression::Null => Ok(Value::Null),
            Expression::Identifier(name) => {
                self.globals.get(name)
                    .cloned()
                    .ok_or_else(|| AvmError::RuntimeError(format!("Variable '{}' not found", name)))
            }
            Expression::TryOp { expression } => {
                // ? 操作符：评估内部表达式，然后 unwrap
                let value = self.eval_ast_expression(expression)?;
                let result = NexaResult::Ok(value);
                match result.unwrap() {
                    Ok(v) => Ok(v),
                    Err(e) => Err(AvmError::RuntimeError(format!("Error propagation: {}", e.error))),
                }
            }
            _ => Ok(Value::Null), // 其他表达式类型暂不支持
        }
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
