//! 字节码指令集 (Bytecode Instructions)
//!
//! 定义 AVM 虚拟机的所有字节码指令

use serde::{Deserialize, Serialize};

/// 字节码指令 OpCode
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum OpCode {
    // ==================== 控制流指令 ====================
    /// 无操作
    Nop = 0x00,
    /// 停止执行
    Halt = 0x01,
    /// 无条件跳转
    Jump = 0x02,
    /// 条件为真跳转
    JumpIfTrue = 0x03,
    /// 条件为假跳转
    JumpIfFalse = 0x04,
    /// 调用函数/Agent
    Call = 0x05,
    /// 返回
    Return = 0x06,
    /// 尾调用优化
    TailCall = 0x07,

    // ==================== 栈操作指令 ====================
    /// 压入常量
    PushConst = 0x10,
    /// 压入空值
    PushNull = 0x11,
    /// 压入布尔值 true
    PushTrue = 0x12,
    /// 压入布尔值 false
    PushFalse = 0x13,
    /// 弹出栈顶
    Pop = 0x14,
    /// 复制栈顶
    Dup = 0x15,
    /// 交换栈顶两个元素
    Swap = 0x16,

    // ==================== 变量操作指令 ====================
    /// 加载局部变量
    LoadLocal = 0x20,
    /// 存储局部变量
    StoreLocal = 0x21,
    /// 加载全局变量
    LoadGlobal = 0x22,
    /// 存储全局变量
    StoreGlobal = 0x23,
    /// 加载 Agent 上下文
    LoadContext = 0x24,
    /// 存储 Agent 上下文
    StoreContext = 0x25,

    // ==================== 算术运算指令 ====================
    /// 加法
    Add = 0x30,
    /// 减法
    Sub = 0x31,
    /// 乘法
    Mul = 0x32,
    /// 除法
    Div = 0x33,
    /// 取模
    Mod = 0x34,
    /// 幂运算
    Pow = 0x35,
    /// 负号
    Neg = 0x36,

    // ==================== 比较运算指令 ====================
    /// 相等比较
    Eq = 0x40,
    /// 不等比较
    Ne = 0x41,
    /// 小于
    Lt = 0x42,
    /// 小于等于
    Le = 0x43,
    /// 大于
    Gt = 0x44,
    /// 大于等于
    Ge = 0x45,
    /// 语义相似度比较 (Nexa 特有)
    SemanticEq = 0x46,
    /// 语义匹配
    SemanticMatch = 0x47,

    // ==================== 逻辑运算指令 ====================
    /// 逻辑与
    And = 0x50,
    /// 逻辑或
    Or = 0x51,
    /// 逻辑非
    Not = 0x52,

    // ==================== 字符串操作指令 ====================
    /// 字符串拼接
    Concat = 0x60,
    /// 字符串格式化
    Format = 0x61,
    /// 字符串插值
    Interpolate = 0x62,

    // ==================== 集合操作指令 ====================
    /// 创建列表
    MakeList = 0x70,
    /// 创建字典
    MakeDict = 0x71,
    /// 创建元组
    MakeTuple = 0x72,
    /// 索引访问
    Index = 0x73,
    /// 属性访问
    GetAttr = 0x74,
    /// 设置属性
    SetAttr = 0x75,
    /// 列表追加
    ListAppend = 0x76,
    /// 字典插入
    DictInsert = 0x77,

    // ==================== Agent 操作指令 ====================
    /// 创建 Agent 实例
    CreateAgent = 0x80,
    /// 调用 Agent
    CallAgent = 0x81,
    /// Agent 管道操作
    PipeAgent = 0x82,
    /// Agent 并行分叉 (DAG)
    ForkAgent = 0x83,
    /// Agent 合流 (DAG)
    MergeAgent = 0x84,
    /// Agent 条件分支 (DAG)
    BranchAgent = 0x85,
    /// 获取 Agent 回复
    AgentReply = 0x86,
    /// 加入多 Agent
    JoinAgents = 0x87,

    // ==================== Tool 操作指令 ====================
    /// 注册工具
    RegisterTool = 0x90,
    /// 调用工具
    CallTool = 0x91,
    /// 加载 MCP 工具
    LoadMcp = 0x92,
    /// 工具权限检查
    CheckToolPerm = 0x93,

    // ==================== LLM 操作指令 ====================
    /// LLM 调用
    LlmCall = 0xA0,
    /// LLM 流式调用
    LlmStream = 0xA1,
    /// LLM 带工具调用
    LlmWithTools = 0xA2,
    /// 缓存查找
    CacheLookup = 0xA3,
    /// 缓存写入
    CacheStore = 0xA4,

    // ==================== Protocol 操作指令 ====================
    /// 加载协议
    LoadProtocol = 0xB0,
    /// 验证协议
    ValidateProtocol = 0xB1,
    /// 应用协议约束
    ApplyProtocol = 0xB2,

    // ==================== 异常处理指令 ====================
    /// 抛出异常
    Throw = 0xC0,
    /// 捕获异常设置
    CatchSetup = 0xC1,
    /// 捕获异常清理
    CatchCleanup = 0xC2,
    /// 断言
    Assert = 0xC3,

    // ==================== 内存管理指令 ====================
    /// 分配内存
    Alloc = 0xD0,
    /// 释放内存
    Free = 0xD1,
    /// 垃圾回收触发
    GcTrigger = 0xD2,

    // ==================== 调试指令 ====================
    /// 断点
    Breakpoint = 0xE0,
    /// 打印调试信息
    Debug = 0xE1,
    /// 追踪开始
    TraceStart = 0xE2,
    /// 追踪结束
    TraceEnd = 0xE3,

    // ==================== WASM 沙盒指令 ====================
    /// WASM 模块加载
    WasmLoad = 0xF0,
    /// WASM 函数调用
    WasmCall = 0xF1,
    /// WASM 内存访问
    WasmMemAccess = 0xF2,
    /// WASM 沙盒检查
    WasmSandboxCheck = 0xF3,
}

/// 字节码指令
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Instruction {
    /// 操作码
    pub opcode: OpCode,
    /// 操作数 (可选)
    pub operand: Option<Operand>,
    /// 源码位置 (用于调试)
    pub source_location: Option<SourceLocation>,
}

/// 操作数类型
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum Operand {
    /// 无操作数
    None,
    /// 8位无符号整数
    U8(u8),
    /// 16位无符号整数
    U16(u16),
    /// 32位无符号整数
    U32(u32),
    /// 64位无符号整数
    U64(u64),
    /// 32位有符号整数
    I32(i32),
    /// 64位有符号整数
    I64(i64),
    /// 浮点数
    F64(f64),
    /// 字符串索引
    StringIdx(u32),
    /// 跳转偏移
    JumpOffset(i32),
    /// 函数索引
    Function(u32),
    /// Agent 索引
    Agent(u32),
    /// Tool 索引
    Tool(u32),
    /// 协议索引
    Protocol(u32),
    /// 参数数量
    ArgCount(u8),
    /// 多个操作数
    Multi(Vec<Operand>),
}

/// 源码位置
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SourceLocation {
    pub line: u32,
    pub column: u32,
    pub file: Option<String>,
}

/// 常量池条目
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum Constant {
    Int(i64),
    Float(f64),
    String(String),
    Bool(bool),
    Null,
    List(Vec<Constant>),
    Dict(std::collections::HashMap<String, Constant>),
    /// JSON 值
    Json(serde_json::Value),
    /// 整数数组
    Integer(i64),
}

/// 字节码模块 (编译单元)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BytecodeModule {
    /// 模块名称
    pub name: String,
    /// 版本号
    pub version: u32,
    /// 常量池
    pub constants: Vec<Constant>,
    /// 符号表 (变量名、函数名等)
    pub symbols: Vec<String>,
    /// 指令序列
    pub instructions: Vec<Instruction>,
    /// 入口点索引
    pub entry_point: u32,
    /// 元数据
    pub metadata: BytecodeMetadata,
}

/// 字节码元数据
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BytecodeMetadata {
    /// 编译时间戳
    pub compile_time: u64,
    /// 源文件路径
    pub source_file: Option<String>,
    /// 编译器版本
    pub compiler_version: String,
    /// 是否启用调试信息
    pub debug_info: bool,
    /// 优化级别
    pub optimization_level: u8,
}

impl BytecodeModule {
    /// 创建新的字节码模块
    pub fn new(name: String) -> Self {
        Self {
            name,
            version: 1,
            constants: Vec::new(),
            symbols: Vec::new(),
            instructions: Vec::new(),
            entry_point: 0,
            metadata: BytecodeMetadata::default(),
        }
    }

    /// 添加常量并返回索引
    pub fn add_constant(&mut self, constant: Constant) -> u32 {
        let index = self.constants.len() as u32;
        self.constants.push(constant);
        index
    }

    /// 添加符号并返回索引
    pub fn add_symbol(&mut self, symbol: String) -> u32 {
        // 检查是否已存在
        if let Some(pos) = self.symbols.iter().position(|s| s == &symbol) {
            return pos as u32;
        }
        let index = self.symbols.len() as u32;
        self.symbols.push(symbol);
        index
    }

    /// 发射指令
    pub fn emit(&mut self, opcode: OpCode, operand: Option<Operand>, location: Option<SourceLocation>) {
        self.instructions.push(Instruction {
            opcode,
            operand,
            source_location: location,
        });
    }

    /// 获取当前指令偏移 (用于跳转目标计算)
    pub fn current_offset(&self) -> u32 {
        self.instructions.len() as u32
    }

    /// 序列化为字节数组
    pub fn to_bytes(&self) -> Result<Vec<u8>, String> {
        // 使用 bincode 或自定义序列化
        // 简单实现: JSON 序列化
        serde_json::to_vec(self).map_err(|e| format!("Serialization error: {}", e))
    }

    /// 从字节数组反序列化
    pub fn from_bytes(data: &[u8]) -> Result<Self, String> {
        serde_json::from_slice(data).map_err(|e| format!("Deserialization error: {}", e))
    }
}

impl Default for BytecodeMetadata {
    fn default() -> Self {
        Self {
            compile_time: 0,
            source_file: None,
            compiler_version: "0.1.0".to_string(),
            debug_info: false,
            optimization_level: 0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_opcode_values() {
        assert_eq!(OpCode::Nop as u8, 0x00);
        assert_eq!(OpCode::Halt as u8, 0x01);
        assert_eq!(OpCode::PushConst as u8, 0x10);
        assert_eq!(OpCode::CallAgent as u8, 0x81);
    }

    #[test]
    fn test_bytecode_module() {
        let mut module = BytecodeModule::new("test".to_string());
        
        let const_idx = module.add_constant(Constant::String("hello".to_string()));
        assert_eq!(const_idx, 0);
        
        let sym_idx = module.add_symbol("agent1".to_string());
        assert_eq!(sym_idx, 0);
        
        module.emit(OpCode::PushConst, Some(Operand::U32(0)), None);
        module.emit(OpCode::Halt, None, None);
        
        assert_eq!(module.instructions.len(), 2);
    }

    #[test]
    fn test_serialization() {
        let mut module = BytecodeModule::new("test".to_string());
        module.add_constant(Constant::Int(42));
        module.emit(OpCode::PushConst, Some(Operand::U32(0)), None);
        
        let bytes = module.to_bytes().unwrap();
        let restored = BytecodeModule::from_bytes(&bytes).unwrap();
        
        assert_eq!(restored.name, "test");
        assert_eq!(restored.constants.len(), 1);
    }
}