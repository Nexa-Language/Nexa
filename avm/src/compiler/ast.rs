//! AST 类型定义

use serde::{Deserialize, Serialize};

/// 程序
#[derive(Debug, Clone, Default)]
pub struct Program {
    pub declarations: Vec<Declaration>,
    pub flows: Vec<FlowDeclaration>,
    pub tests: Vec<TestDeclaration>,
}

/// 声明
#[derive(Debug, Clone)]
pub enum Declaration {
    Tool(ToolDeclaration),
    Protocol(ProtocolDeclaration),
    Agent(AgentDeclaration),
}

/// 工具声明
#[derive(Debug, Clone)]
pub struct ToolDeclaration {
    pub name: String,
    pub description: Option<String>,
    pub parameters: Option<serde_json::Value>,
    pub body: Vec<Statement>,
}

/// 协议声明
#[derive(Debug, Clone)]
pub struct ProtocolDeclaration {
    pub name: String,
    pub schema: Option<serde_json::Value>,
    pub body: Vec<Statement>,
}

/// Agent 声明
#[derive(Debug, Clone)]
pub struct AgentDeclaration {
    pub name: String,
    pub prompt: Option<String>,
    pub role: Option<String>,
    pub model: Option<String>,
    pub tools: Vec<Expression>,
    pub protocol: Option<String>,
    pub memory_scope: Option<String>,
    pub max_history_turns: Option<u32>,
}

/// Flow 声明
#[derive(Debug, Clone)]
pub struct FlowDeclaration {
    pub name: String,
    pub parameters: Vec<Expression>,
    pub body: Vec<Statement>,
}

/// Test 声明
#[derive(Debug, Clone)]
pub struct TestDeclaration {
    pub name: String,
    pub body: Vec<Statement>,
}

/// 语句
#[derive(Debug, Clone)]
pub enum Statement {
    Assignment {
        target: Expression,
        value: Expression,
        is_semantic: bool,
    },
    Expression(Expression),
    TryCatch {
        try_body: Vec<Statement>,
        catch_var: String,
        catch_body: Vec<Statement>,
    },
    Assert {
        condition: Expression,
        message: Option<String>,
    },
    SemanticIf {
        branches: Vec<(Expression, Vec<Statement>)>,
        else_body: Vec<Statement>,
    },
    Loop {
        condition: Expression,
        body: Vec<Statement>,
    },
    Match {
        input: Expression,
        cases: Vec<MatchCase>,
    },
    Return(Option<Expression>),
    Break,
    Continue,
}

/// Match 分支
#[derive(Debug, Clone)]
pub struct MatchCase {
    pub pattern: Pattern,
    pub body: Vec<Statement>,
}

/// 模式
#[derive(Debug, Clone)]
pub enum Pattern {
    Wildcard,
    Literal(Expression),
    Variable(String),
    Constructor { name: String, fields: Vec<Pattern> },
}

/// 表达式
#[derive(Debug, Clone)]
pub enum Expression {
    Null,
    Bool(bool),
    Integer(i64),
    Float(f64),
    String(String),
    Identifier(String),
    List(Vec<Expression>),
    Dict(Vec<(String, Expression)>),
    BinaryOp {
        left: Box<Expression>,
        op: String,
        right: Box<Expression>,
    },
    UnaryOp {
        op: String,
        operand: Box<Expression>,
    },
    Pipeline {
        left: Box<Expression>,
        right: Box<Expression>,
    },
    AgentCall {
        name: String,
        args: Vec<Expression>,
        kwargs: Vec<(String, Expression)>,
    },
    MethodCall {
        object: Box<Expression>,
        method: String,
        args: Vec<Expression>,
        kwargs: Vec<(String, Expression)>,
    },
    Index {
        object: Box<Expression>,
        index: Box<Expression>,
    },
    PropertyAccess {
        object: Box<Expression>,
        property: String,
    },
    JoinCall {
        agents: Vec<Expression>,
        merge_strategy: String,
        merge_agent: Option<String>,
    },
    DagFork(DagForkExpression),
    DagMerge(DagMergeExpression),
    DagBranch(DagBranchExpression),
}

/// DAG 分叉表达式
#[derive(Debug, Clone)]
pub struct DagForkExpression {
    pub input: Box<Expression>,
    pub targets: Vec<Expression>,
}

/// DAG 合流表达式
#[derive(Debug, Clone)]
pub struct DagMergeExpression {
    pub inputs: Vec<Expression>,
    pub merge_strategy: String,
    pub merge_agent: Option<String>,
}

/// DAG 条件分支表达式
#[derive(Debug, Clone)]
pub struct DagBranchExpression {
    pub input: Box<Expression>,
    pub condition: Box<Expression>,
    pub true_branch: Box<Expression>,
    pub false_branch: Option<Box<Expression>>,
}
