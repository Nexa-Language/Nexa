//! 执行栈 (Execution Stack)

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// AVM 运行时值
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    String(String),
    List(Vec<Value>),
    Dict(HashMap<String, Value>),
    AgentRef(String),
    ToolRef(String),
    Future(u64),
}

impl Value {
    pub fn is_truthy(&self) -> bool {
        match self {
            Value::Null => false,
            Value::Bool(b) => *b,
            Value::Int(i) => *i != 0,
            Value::Float(f) => *f != 0.0,
            Value::String(s) => !s.is_empty(),
            Value::List(l) => !l.is_empty(),
            Value::Dict(d) => !d.is_empty(),
            _ => true,
        }
    }

    pub fn to_string(&self) -> String {
        match self {
            Value::Null => "null".to_string(),
            Value::Bool(b) => b.to_string(),
            Value::Int(i) => i.to_string(),
            Value::Float(f) => f.to_string(),
            Value::String(s) => s.clone(),
            Value::List(l) => {
                let items: Vec<String> = l.iter().map(|v| v.to_string()).collect();
                format!("[{}]", items.join(", "))
            }
            Value::Dict(d) => {
                let items: Vec<String> = d.iter()
                    .map(|(k, v)| format!("{}: {}", k, v.to_string()))
                    .collect();
                format!("{{{}}}", items.join(", "))
            }
            Value::AgentRef(name) => format!("<Agent: {}>", name),
            Value::ToolRef(name) => format!("<Tool: {}>", name),
            Value::Future(id) => format!("<Future: {}>", id),
        }
    }
}

impl Default for Value {
    fn default() -> Self {
        Value::Null
    }
}

impl std::fmt::Display for Value {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.to_string())
    }
}

/// 调用帧
#[derive(Debug, Clone)]
pub struct CallFrame {
    pub name: String,
    pub return_address: u32,
    pub local_base: usize,
    pub arg_count: u8,
}

impl CallFrame {
    pub fn new(name: String, return_address: u32, local_base: usize, arg_count: u8) -> Self {
        Self { name, return_address, local_base, arg_count }
    }
}

/// 执行栈
#[derive(Debug)]
pub struct Stack {
    pub values: Vec<Value>,
    frames: Vec<CallFrame>,
    max_depth: usize,
}

impl Stack {
    pub fn new(max_depth: usize) -> Self {
        Self {
            values: Vec::with_capacity(256),
            frames: Vec::with_capacity(16),
            max_depth,
        }
    }

    pub fn push(&mut self, value: Value) -> Result<(), StackError> {
        if self.values.len() >= self.max_depth {
            return Err(StackError::StackOverflow);
        }
        self.values.push(value);
        Ok(())
    }

    pub fn pop(&mut self) -> Result<Value, StackError> {
        self.values.pop().ok_or(StackError::StackUnderflow)
    }

    pub fn peek(&self) -> Result<&Value, StackError> {
        self.values.last().ok_or(StackError::StackUnderflow)
    }

    pub fn depth(&self) -> usize {
        self.values.len()
    }

    pub fn dup(&mut self) -> Result<(), StackError> {
        let value = self.peek()?.clone();
        self.push(value)
    }

    pub fn swap(&mut self) -> Result<(), StackError> {
        let len = self.values.len();
        if len < 2 {
            return Err(StackError::StackUnderflow);
        }
        self.values.swap(len - 1, len - 2);
        Ok(())
    }

    pub fn push_frame(&mut self, frame: CallFrame) {
        self.frames.push(frame);
    }

    pub fn pop_frame(&mut self) -> Option<CallFrame> {
        self.frames.pop()
    }

    pub fn current_frame(&self) -> Option<&CallFrame> {
        self.frames.last()
    }

    pub fn local_base(&self) -> usize {
        self.frames.last().map(|f| f.local_base).unwrap_or(0)
    }

    pub fn clear(&mut self) {
        self.values.clear();
    }

    pub fn reset(&mut self) {
        self.values.clear();
        self.frames.clear();
    }
}

impl Default for Stack {
    fn default() -> Self {
        Self::new(1024)
    }
}

#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum StackError {
    #[error("Stack overflow")]
    StackOverflow,
    #[error("Stack underflow")]
    StackUnderflow,
    #[error("Invalid local variable access")]
    InvalidLocalAccess,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_value_truthy() {
        assert!(!Value::Null.is_truthy());
        assert!(Value::Bool(true).is_truthy());
        assert!(!Value::Bool(false).is_truthy());
        assert!(Value::Int(42).is_truthy());
    }

    #[test]
    fn test_stack_operations() {
        let mut stack = Stack::new(100);
        stack.push(Value::Int(1)).unwrap();
        stack.push(Value::Int(2)).unwrap();
        assert_eq!(stack.depth(), 2);
        assert_eq!(stack.pop().unwrap(), Value::Int(2));
    }
}
