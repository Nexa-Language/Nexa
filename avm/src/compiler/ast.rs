//! AST 类型定义
//!
//! v1.1: 渐进式类型系统 (Gradual Type System) 支持
//! - TypeExpr 类型表达式节点
//! - ProtocolDeclaration 扩展为完整类型约束
//! - FlowDeclaration 新增返回类型和参数类型
//! - AgentDeclaration 新增输入输出类型信息

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
    /// v1.1: 语义类型声明 (type Name = base_type @ "constraint")
    TypeAlias(TypeAliasDeclaration),
    /// P1-3: 后台任务声明 (job Name on queue { perform(...) { ... } })
    Job(JobDeclaration),
}

/// 工具声明
#[derive(Debug, Clone)]
pub struct ToolDeclaration {
    pub name: String,
    pub description: Option<String>,
    pub parameters: Option<serde_json::Value>,
    pub body: Vec<Statement>,
}

/// 协议声明 — v1.1: 扩展为完整类型约束
#[derive(Debug, Clone)]
pub struct ProtocolDeclaration {
    pub name: String,
    /// 字段名 → 类型表达式 (v1.1: 从简单字符串标注扩展为类型表达式)
    pub fields: Vec<(String, TypeExpr)>,
    /// 原始 schema (向后兼容)
    pub schema: Option<serde_json::Value>,
    pub body: Vec<Statement>,
}

/// v1.1: 语义类型别名声明
#[derive(Debug, Clone)]
pub struct TypeAliasDeclaration {
    pub name: String,
    pub definition: TypeExpr,
    /// 语义约束 (如 "must be a valid email address")
    pub constraint: Option<String>,
}

/// 契约条款 (Design by Contract)
#[derive(Debug, Clone)]
pub struct ContractClause {
    /// 确定性表达式（如 "amount > 0"）
    pub expression: Option<String>,
    /// 语义条件文本（如 "input contains financial data"）
    pub condition_text: Option<String>,
    /// 是否为语义契约（自然语言条件）
    pub is_semantic: bool,
    /// 契约类型: "requires" 或 "ensures"
    pub clause_type: String,
    /// 附加说明/错误消息
    pub message: Option<String>,
}

/// 契约规格
#[derive(Debug, Clone, Default)]
pub struct ContractSpec {
    pub requires: Vec<ContractClause>,
    pub ensures: Vec<ContractClause>,
}

/// Agent 声明 — v1.1: 新增输入输出类型信息
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
    /// Design by Contract: 契约规格
    pub contracts: Option<ContractSpec>,
    /// v1.1: 输入类型 (通过 protocol + requires 推断)
    pub input_type: Option<TypeExpr>,
    /// v1.1: 输出类型 (通过 protocol + ensures 推断)
    pub output_type: Option<TypeExpr>,
}

/// Flow 声明 — v1.1: 新增返回类型和参数类型
#[derive(Debug, Clone)]
pub struct FlowDeclaration {
    pub name: String,
    /// v1.1: 参数列表 (name, type_expr)
    pub parameters: Vec<(String, TypeExpr)>,
    /// v1.1: 返回类型
    pub return_type: Option<TypeExpr>,
    pub body: Vec<Statement>,
    /// Design by Contract: 契约规格
    pub contracts: Option<ContractSpec>,
}

/// Test 声明
#[derive(Debug, Clone)]
pub struct TestDeclaration {
    pub name: String,
    pub body: Vec<Statement>,
}

/// P1-3: 后台任务声明 (Background Job System)
///
/// 对应 Nexa 语法: `job SendEmail on emails { perform(user_id) { ... } }`
#[derive(Debug, Clone)]
pub struct JobDeclaration {
    /// Job 名称 (如 "SendEmail")
    pub name: String,
    /// 队列名 (如 "emails", "payments")
    pub queue: String,
    /// Inline 选项 (如 retry: 2, timeout: 120)
    pub options: Vec<JobOption>,
    /// 配置项 (如 retry: 5, timeout: 60s, unique: args for 1h)
    pub config: Vec<JobOption>,
    /// perform 声明参数列表
    pub perform_params: Vec<String>,
    /// perform 声明体
    pub perform_body: Vec<Statement>,
    /// on_failure 回调 (可选)
    pub on_failure: Option<OnFailureDeclaration>,
}

/// P1-3: Job 选项 (inline 或 body 内配置项)
#[derive(Debug, Clone)]
pub struct JobOption {
    /// 配置键 (如 "retry", "timeout", "priority", "unique", "backoff")
    pub key: String,
    /// 配置值
    pub value: JobOptionValue,
}

/// P1-3: Job 选项值
#[derive(Debug, Clone)]
pub enum JobOptionValue {
    Int(i64),
    Float(f64),
    String(String),
    Identifier(String),
}

/// P1-3: on_failure 回调声明
#[derive(Debug, Clone)]
pub struct OnFailureDeclaration {
    /// error 参数名
    pub error_param: String,
    /// attempt 参数名
    pub attempt_param: String,
    /// 回调体
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
    /// v1.2: ? 操作符赋值 — x = expr? (错误传播，失败时 early-return)
    TryAssignment {
        target: String,
        expression: Expression,
    },
    /// v1.2: otherwise 内联错误处理赋值 — x = expr otherwise handler
    OtherwiseAssignment {
        target: String,
        expression: Expression,
        handler: OtherwiseHandler,
    },
    /// v1.2: ? 操作符表达式 — expr? (错误传播，无赋值)
    TryExpression(Expression),
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

/// v1.2: otherwise handler — Agent fallback、值 fallback、变量 fallback、代码块 fallback
///
/// Nexa 独有特性：otherwise 可以指定另一个 Agent 作为 fallback
/// - OtherwiseAgentHandler: Agent.run_result() 作为 fallback
/// - OtherwiseValueHandler: 字符串/值作为默认值
/// - OtherwiseVarHandler: 变量引用作为默认值
/// - OtherwiseBlockHandler: 代码块（lambda）作为 fallback
#[derive(Debug, Clone)]
pub enum OtherwiseHandler {
    /// Agent 调用作为 fallback（Nexa 独有）
    AgentCall {
        agent_name: String,
        args: Vec<Expression>,
    },
    /// 值作为默认 fallback
    Value(String),
    /// 变量引用作为 fallback
    Variable(String),
    /// 代码块作为 fallback
    Block(Vec<Statement>),
}

/// 表达式
#[derive(Debug, Clone)]
pub enum Expression {
    /// v1.2: TryOp — ? 操作符表达式（错误传播）
    /// 对 NexaResult/NexaOption 执行 unwrap，失败则触发 ErrorPropagation
    TryOp {
        expression: Box<Expression>,
    },
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

// ============================================================
// v1.1: 渐进式类型系统 — TypeExpr (类型表达式)
// ============================================================

/// 类型表达式 — 表示 Nexa 类型标注
///
/// 支持:
/// - 基本类型: str, int, float, bool, unit
/// - 泛型类型: list[T], dict[K, V], Option[T], Result[T, E]
/// - 联合类型: str | int
/// - 可选类型: T? (= Option[T])
/// - 类型别名: 自定义类型名
/// - 函数类型: (T1, T2) -> T3
/// - 语义类型: str @ "constraint"
#[derive(Debug, Clone, PartialEq)]
pub enum TypeExpr {
    /// 基本类型: str, int, float, bool, unit
    Primitive {
        name: String,
    },
    /// 泛型类型: list[T], dict[K, V], Option[T], Result[T, E]
    Generic {
        name: String,
        type_params: Vec<TypeExpr>,
    },
    /// 联合类型: str | int | float
    Union {
        types: Vec<TypeExpr>,
    },
    /// 可选类型: T? (= Option[T])
    Option {
        inner: Box<TypeExpr>,
    },
    /// Result 类型: Result[T, E]
    Result {
        ok_type: Box<TypeExpr>,
        err_type: Box<TypeExpr>,
    },
    /// 类型别名: 自定义类型名引用
    Alias {
        name: String,
        /// 如果已解析，指向实际类型
        resolved: Option<Box<TypeExpr>>,
    },
    /// 函数类型: (T1, T2) -> T3
    Func {
        param_types: Vec<TypeExpr>,
        return_type: Box<TypeExpr>,
    },
    /// 语义类型: str @ "constraint" (兼容已有的 type 语义声明)
    Semantic {
        base: Box<TypeExpr>,
        constraint: String,
    },
    /// Any 类型 — 未知/未标注
    Any,
}

impl TypeExpr {
    /// 将类型表达式转换为字符串表示
    pub fn to_type_str(&self) -> String {
        match self {
            TypeExpr::Primitive { name } => name.clone(),
            TypeExpr::Generic { name, type_params } => {
                let params = type_params.iter()
                    .map(|t| t.to_type_str())
                    .collect::<Vec<_>>()
                    .join(", ");
                format!("{}[{}]", name, params)
            }
            TypeExpr::Union { types } => {
                types.iter()
                    .map(|t| t.to_type_str())
                    .collect::<Vec<_>>()
                    .join(" | ")
            }
            TypeExpr::Option { inner } => format!("{}?", inner.to_type_str()),
            TypeExpr::Result { ok_type, err_type } => {
                format!("Result[{}, {}]", ok_type.to_type_str(), err_type.to_type_str())
            }
            TypeExpr::Alias { name, resolved } => {
                if let Some(r) = resolved {
                    r.to_type_str()
                } else {
                    name.clone()
                }
            }
            TypeExpr::Func { param_types, return_type } => {
                let params = param_types.iter()
                    .map(|t| t.to_type_str())
                    .collect::<Vec<_>>()
                    .join(", ");
                format!("({}) -> {}", params, return_type.to_type_str())
            }
            TypeExpr::Semantic { base, constraint } => {
                format!("{} @ \"{}\"", base.to_type_str(), constraint)
            }
            TypeExpr::Any => "Any".to_string(),
        }
    }
    
    /// 判断是否为基本类型
    pub fn is_primitive(&self) -> bool {
        matches!(self, TypeExpr::Primitive { .. })
    }
    
    /// 判断是否为 Any 类型
    pub fn is_any(&self) -> bool {
        matches!(self, TypeExpr::Any)
    }
    
    /// 判断是否为 Option 类型
    pub fn is_option(&self) -> bool {
        matches!(self, TypeExpr::Option { .. })
    }
}

/// v1.1: 类型检查模式 (NEXA_TYPE_MODE)
#[derive(Debug, Clone, PartialEq)]
pub enum TypeMode {
    /// 类型不匹配=运行时错误，程序终止
    Strict,
    /// 类型不匹配=日志警告并继续（默认）
    Warn,
    /// 类型不匹配=静默忽略
    Forgiving,
}

impl Default for TypeMode {
    fn default() -> Self {
        TypeMode::Warn
    }
}

/// v1.1: Lint 类型检查模式 (NEXA_LINT_MODE)
#[derive(Debug, Clone, PartialEq)]
pub enum LintMode {
    /// 只检查有类型标注的代码（默认）
    Default,
    /// 对缺失类型标注发出警告
    Warn,
    /// 缺失类型标注=lint错误（非零退出码）
    Strict,
}

impl Default for LintMode {
    fn default() -> Self {
        LintMode::Default
    }
}

/// v1.1: 类型违反 (与 ContractViolation 区分)
#[derive(Debug, Clone)]
pub struct TypeViolation {
    pub message: String,
    pub expected_type: Option<TypeExpr>,
    pub actual_type: Option<TypeExpr>,
    pub context: Option<String>,
}

/// v1.1: 类型检查结果
#[derive(Debug, Clone)]
pub struct TypeCheckResult {
    pub passed: bool,
    pub violations: Vec<TypeViolation>,
    pub warnings: Vec<TypeViolation>,
}
