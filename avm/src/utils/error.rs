//! 错误类型定义

use thiserror::Error;
use crate::vm::stack::StackError;

/// AVM 错误类型
#[derive(Debug, Error)]
pub enum AvmError {
    #[error("Lexical error: {0}")]
    LexicalError(String),

    #[error("Parse error: {0}")]
    ParseError(String),

    #[error("Compilation error: {0}")]
    CompilationError(String),

    #[error("Type error: {0}")]
    TypeError(String),

    #[error("Runtime error: {0}")]
    RuntimeError(String),

    #[error("Stack overflow")]
    StackOverflow,

    #[error("Stack underflow")]
    StackUnderflow,

    #[error("Agent not found: {0}")]
    AgentNotFound(String),

    #[error("Agent execution failed: {0}")]
    AgentExecutionFailed(String),

    #[error("Tool not found: {0}")]
    ToolNotFound(String),

    #[error("Tool error: {0}")]
    ToolError(String),

    #[error("LLM error: {0}")]
    LlmError(String),

    #[error("Protocol not found: {0}")]
    ProtocolNotFound(String),

    #[error("WASM error: {0}")]
    WasmError(String),

    #[error("WASM sandbox violation: {0}")]
    WasmSandboxViolation(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Internal error: {0}")]
    InternalError(String),

    #[error("Not implemented: {0}")]
    NotImplemented(String),

    /// v1.1: 渐进式类型系统类型检查错误
    #[error("Type check error: {0}")]
    TypeCheck(String),
}

impl From<StackError> for AvmError {
    fn from(err: StackError) -> Self {
        match err {
            StackError::StackOverflow => AvmError::StackOverflow,
            StackError::StackUnderflow => AvmError::StackUnderflow,
            StackError::InvalidLocalAccess => AvmError::RuntimeError("Invalid local variable access".to_string()),
        }
    }
}

/// AVM 结果类型
pub type AvmResult<T> = Result<T, AvmError>;
