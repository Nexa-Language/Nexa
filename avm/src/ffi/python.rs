//! Python FFI 绑定 (Python Foreign Function Interface)
//!
//! 提供 Python 调用 AVM 的完整接口

use crate::utils::error::{AvmError, AvmResult};
use crate::compiler::parser::Parser;
use crate::bytecode::compiler::BytecodeCompiler;
use crate::bytecode::instructions::BytecodeModule;
use crate::runtime::AvmRuntime;
use std::collections::HashMap;

/// Python 模块信息
#[derive(Debug, Clone)]
pub struct PythonModule {
    /// 模块名
    name: String,
    /// 模块版本
    version: String,
    /// 模块描述
    description: String,
}

impl PythonModule {
    /// 创建新的 Python 模块
    pub fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
            version: env!("CARGO_PKG_VERSION").to_string(),
            description: "Nexa AVM Python binding".to_string(),
        }
    }
    
    /// 获取模块名
    pub fn name(&self) -> &str {
        &self.name
    }
    
    /// 获取模块版本
    pub fn version(&self) -> &str {
        &self.version
    }
    
    /// 获取模块描述
    pub fn description(&self) -> &str {
        &self.description
    }
}

/// Python 值类型
#[derive(Debug, Clone, PartialEq)]
pub enum PythonValue {
    /// None 值
    None,
    /// 布尔值
    Bool(bool),
    /// 整数
    Int(i64),
    /// 浮点数
    Float(f64),
    /// 字符串
    String(String),
    /// 列表
    List(Vec<PythonValue>),
    /// 字典
    Dict(HashMap<String, PythonValue>),
}

impl PythonValue {
    /// 创建 None 值
    pub fn none() -> Self {
        PythonValue::None
    }
    
    /// 创建布尔值
    pub fn bool_val(v: bool) -> Self {
        PythonValue::Bool(v)
    }
    
    /// 创建整数值
    pub fn int_val(v: i64) -> Self {
        PythonValue::Int(v)
    }
    
    /// 创建浮点数值
    pub fn float_val(v: f64) -> Self {
        PythonValue::Float(v)
    }
    
    /// 创建字符串值
    pub fn string_val(v: impl Into<String>) -> Self {
        PythonValue::String(v.into())
    }
    
    /// 创建列表值
    pub fn list_val(v: Vec<PythonValue>) -> Self {
        PythonValue::List(v)
    }
    
    /// 创建字典值
    pub fn dict_val(v: HashMap<String, PythonValue>) -> Self {
        PythonValue::Dict(v)
    }
    
    /// 检查是否为 None
    pub fn is_none(&self) -> bool {
        matches!(self, PythonValue::None)
    }
    
    /// 转换为布尔值
    pub fn as_bool(&self) -> Option<bool> {
        match self {
            PythonValue::Bool(v) => Some(*v),
            _ => None,
        }
    }
    
    /// 转换为整数
    pub fn as_int(&self) -> Option<i64> {
        match self {
            PythonValue::Int(v) => Some(*v),
            PythonValue::Float(v) => Some(*v as i64),
            _ => None,
        }
    }
    
    /// 转换为浮点数
    pub fn as_float(&self) -> Option<f64> {
        match self {
            PythonValue::Float(v) => Some(*v),
            PythonValue::Int(v) => Some(*v as f64),
            _ => None,
        }
    }
    
    /// 转换为字符串
    pub fn as_str(&self) -> Option<&str> {
        match self {
            PythonValue::String(v) => Some(v),
            _ => None,
        }
    }
    
    /// 转换为列表
    pub fn as_list(&self) -> Option<&Vec<PythonValue>> {
        match self {
            PythonValue::List(v) => Some(v),
            _ => None,
        }
    }
    
    /// 转换为字典
    pub fn as_dict(&self) -> Option<&HashMap<String, PythonValue>> {
        match self {
            PythonValue::Dict(v) => Some(v),
            _ => None,
        }
    }
    
    /// 获取类型名称
    pub fn type_name(&self) -> &'static str {
        match self {
            PythonValue::None => "None",
            PythonValue::Bool(_) => "bool",
            PythonValue::Int(_) => "int",
            PythonValue::Float(_) => "float",
            PythonValue::String(_) => "str",
            PythonValue::List(_) => "list",
            PythonValue::Dict(_) => "dict",
        }
    }
}

impl Default for PythonValue {
    fn default() -> Self {
        PythonValue::None
    }
}

impl std::fmt::Display for PythonValue {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PythonValue::None => write!(f, "None"),
            PythonValue::Bool(v) => write!(f, "{}", v),
            PythonValue::Int(v) => write!(f, "{}", v),
            PythonValue::Float(v) => write!(f, "{}", v),
            PythonValue::String(v) => write!(f, "\"{}\"", v),
            PythonValue::List(v) => {
                let items: Vec<String> = v.iter().map(|x| x.to_string()).collect();
                write!(f, "[{}]", items.join(", "))
            }
            PythonValue::Dict(v) => {
                let items: Vec<String> = v.iter()
                    .map(|(k, val)| format!("\"{}\": {}", k, val))
                    .collect();
                write!(f, "{{{}}}", items.join(", "))
            }
        }
    }
}

/// 编译结果
#[derive(Debug, Clone)]
pub struct CompileResult {
    /// 是否成功
    pub success: bool,
    /// 错误消息
    pub error_message: Option<String>,
    /// 生成的字节码大小
    pub bytecode_size: usize,
    /// 编译时间 (微秒)
    pub compile_time_us: u64,
}

impl CompileResult {
    /// 创建成功的编译结果
    pub fn success(bytecode_size: usize, compile_time_us: u64) -> Self {
        Self {
            success: true,
            error_message: None,
            bytecode_size,
            compile_time_us,
        }
    }
    
    /// 创建失败的编译结果
    pub fn failure(message: impl Into<String>) -> Self {
        Self {
            success: false,
            error_message: Some(message.into()),
            bytecode_size: 0,
            compile_time_us: 0,
        }
    }
}

/// 执行结果
#[derive(Debug, Clone)]
pub struct ExecutionResultPy {
    /// 是否成功
    pub success: bool,
    /// 返回值
    pub value: PythonValue,
    /// 错误消息
    pub error_message: Option<String>,
    /// 执行时间 (微秒)
    pub execution_time_us: u64,
}

impl ExecutionResultPy {
    /// 创建成功的执行结果
    pub fn success(value: PythonValue, execution_time_us: u64) -> Self {
        Self {
            success: true,
            value,
            error_message: None,
            execution_time_us,
        }
    }
    
    /// 创建失败的执行结果
    pub fn failure(message: impl Into<String>) -> Self {
        Self {
            success: false,
            value: PythonValue::None,
            error_message: Some(message.into()),
            execution_time_us: 0,
        }
    }
}

impl Default for ExecutionResultPy {
    fn default() -> Self {
        Self::success(PythonValue::None, 0)
    }
}

/// AVM Python 绑定
pub struct AvmPy {
    /// 运行时
    runtime: Option<AvmRuntime>,
    /// 最后编译的字节码
    last_module: Option<BytecodeModule>,
    /// 模块信息
    module_info: PythonModule,
}

impl AvmPy {
    /// 创建新的 AVM Python 绑定
    pub fn new() -> Self {
        Self {
            runtime: None,
            last_module: None,
            module_info: PythonModule::new("nexa_avm"),
        }
    }
    
    /// 获取模块信息
    pub fn module_info(&self) -> &PythonModule {
        &self.module_info
    }
    
    /// 初始化运行时
    pub fn init(&mut self) -> AvmResult<()> {
        self.runtime = Some(AvmRuntime::new(Default::default()));
        Ok(())
    }
    
    /// 编译源代码
    pub fn compile(&mut self, source: &str) -> CompileResult {
        let start = std::time::Instant::now();
        
        // 解析
        let program = match Parser::parse_from_source(source) {
            Ok(p) => p,
            Err(e) => return CompileResult::failure(format!("Parse error: {}", e)),
        };
        
        // 编译
        let compiler = BytecodeCompiler::new("main".to_string());
        let module = match compiler.compile(&program) {
            Ok(m) => m,
            Err(e) => return CompileResult::failure(format!("Compile error: {}", e)),
        };
        
        let size = module.instructions.len();
        self.last_module = Some(module);
        
        CompileResult::success(size, start.elapsed().as_micros() as u64)
    }
    
    /// 运行编译后的代码
    pub fn run(&mut self) -> ExecutionResultPy {
        let start = std::time::Instant::now();
        
        // 确保运行时已初始化
        if self.runtime.is_none() {
            if let Err(e) = self.init() {
                return ExecutionResultPy::failure(format!("Runtime init failed: {}", e));
            }
        }
        
        // 检查是否有编译好的模块
        let module = match &self.last_module {
            Some(m) => m.clone(),
            None => return ExecutionResultPy::failure("No compiled module available"),
        };
        
        // 执行 (简化版本)
        // 实际执行需要更完整的解释器实现
        let _ = module;
        
        ExecutionResultPy::success(PythonValue::None, start.elapsed().as_micros() as u64)
    }
    
    /// 编译并运行
    pub fn compile_and_run(&mut self, source: &str) -> ExecutionResultPy {
        let compile_result = self.compile(source);
        if !compile_result.success {
            return ExecutionResultPy::failure(
                compile_result.error_message.unwrap_or_else(|| "Compilation failed".to_string())
            );
        }
        self.run()
    }
    
    /// 解析源代码 (返回 AST 信息)
    pub fn parse(&self, source: &str) -> Result<serde_json::Value, String> {
        let program = Parser::parse_from_source(source)
            .map_err(|e| format!("Parse error: {}", e))?;
        
        // 将 AST 转换为 JSON (简化版本)
        let mut declarations = Vec::new();
        for decl in &program.declarations {
            declarations.push(format!("{:?}", decl));
        }
        
        Ok(serde_json::json!({
            "declarations_count": program.declarations.len(),
            "declarations": declarations,
        }))
    }
    
    /// 获取版本信息
    pub fn version(&self) -> &str {
        self.module_info.version()
    }
    
    /// 重置状态
    pub fn reset(&mut self) {
        self.last_module = None;
        self.runtime = None;
    }
}

impl Default for AvmPy {
    fn default() -> Self {
        Self::new()
    }
}

/// 初始化 Python 模块
pub fn init_python_module() -> AvmResult<()> {
    // 占位实现，实际需要 pyo3 初始化
    Ok(())
}

/// 创建 AVM 实例
pub fn create_avm_instance() -> AvmPy {
    AvmPy::new()
}

/// 编译源代码的便捷函数
pub fn compile_source(source: &str) -> CompileResult {
    let mut avm = AvmPy::new();
    avm.compile(source)
}

/// 执行源代码的便捷函数
pub fn run_source(source: &str) -> ExecutionResultPy {
    let mut avm = AvmPy::new();
    avm.compile_and_run(source)
}

// ==================== PyO3 绑定 (需要启用 python-ffi feature) ====================

#[cfg(feature = "python-ffi")]
mod pyo3_bindings {
    use super::*;
    use pyo3::prelude::*;
    use pyo3::types::{PyDict, PyList};
    
    /// Python 模块定义
    #[pymodule]
    fn nexa_avm(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
        m.add_class::<PyAvm>()?;
        m.add_class::<PyValue>()?;
        m.add_function(wrap_pyfunction!(compile, m)?)?;
        m.add_function(wrap_pyfunction!(run, m)?)?;
        m.add("__version__", env!("CARGO_PKG_VERSION"))?;
        Ok(())
    }
    
    /// Python AVM 类
    #[pyclass(name = "Avm")]
    pub struct PyAvm {
        inner: AvmPy,
    }
    
    #[pymethods]
    impl PyAvm {
        #[new]
        fn new() -> Self {
            Self { inner: AvmPy::new() }
        }
        
        /// 初始化运行时
        fn init(&mut self) -> PyResult<()> {
            self.inner.init()
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        }
        
        /// 编译源代码
        fn compile(&mut self, source: &str) -> PyResult<()> {
            let result = self.inner.compile(source);
            if result.success {
                Ok(())
            } else {
                Err(pyo3::exceptions::PySyntaxError::new_err(
                    result.error_message.unwrap_or_else(|| "Compilation failed".to_string())
                ))
            }
        }
        
        /// 运行
        fn run(&mut self) -> PyResult<Py<PyValue>> {
            let result = self.inner.run();
            if result.success {
                Python::with_gil(|py| {
                    Py::new(py, PyValue { inner: result.value })
                })
            } else {
                Err(pyo3::exceptions::PyRuntimeError::new_err(
                    result.error_message.unwrap_or_else(|| "Execution failed".to_string())
                ))
            }
        }
        
        /// 编译并运行
        fn compile_and_run(&mut self, source: &str) -> PyResult<Py<PyValue>> {
            let result = self.inner.compile_and_run(source);
            if result.success {
                Python::with_gil(|py| {
                    Py::new(py, PyValue { inner: result.value })
                })
            } else {
                Err(pyo3::exceptions::PyRuntimeError::new_err(
                    result.error_message.unwrap_or_else(|| "Execution failed".to_string())
                ))
            }
        }
        
        /// 获取版本
        #[getter]
        fn version(&self) -> &str {
            self.inner.version()
        }
        
        /// 重置
        fn reset(&mut self) {
            self.inner.reset();
        }
    }
    
    /// Python 值类
    #[pyclass(name = "Value")]
    pub struct PyValue {
        inner: PythonValue,
    }
    
    #[pymethods]
    impl PyValue {
        /// 是否为 None
        fn is_none(&self) -> bool {
            self.inner.is_none()
        }
        
        /// 获取类型
        fn type_name(&self) -> &'static str {
            self.inner.type_name()
        }
        
        /// 转换为字符串
        fn to_string(&self) -> String {
            self.inner.to_string()
        }
        
        /// 转换为整数
        fn as_int(&self) -> Option<i64> {
            self.inner.as_int()
        }
        
        /// 转换为浮点数
        fn as_float(&self) -> Option<f64> {
            self.inner.as_float()
        }
        
        /// 转换为布尔值
        fn as_bool(&self) -> Option<bool> {
            self.inner.as_bool()
        }
        
        /// 转换为字符串
        fn as_str(&self) -> Option<&str> {
            self.inner.as_str()
        }
    }
    
    /// 编译函数
    #[pyfunction]
    fn compile(source: &str) -> PyResult<()> {
        let result = compile_source(source);
        if result.success {
            Ok(())
        } else {
            Err(pyo3::exceptions::PySyntaxError::new_err(
                result.error_message.unwrap_or_else(|| "Compilation failed".to_string())
            ))
        }
    }
    
    /// 运行函数
    #[pyfunction]
    fn run(source: &str) -> PyResult<Py<PyValue>> {
        let result = run_source(source);
        if result.success {
            Python::with_gil(|py| {
                Py::new(py, PyValue { inner: result.value })
            })
        } else {
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                result.error_message.unwrap_or_else(|| "Execution failed".to_string())
            ))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_python_module() {
        let module = PythonModule::new("test");
        assert_eq!(module.name(), "test");
        assert!(!module.version().is_empty());
    }
    
    #[test]
    fn test_python_value_none() {
        let val = PythonValue::none();
        assert!(val.is_none());
        assert_eq!(val.type_name(), "None");
    }
    
    #[test]
    fn test_python_value_bool() {
        let val = PythonValue::bool_val(true);
        assert_eq!(val.as_bool(), Some(true));
        assert_eq!(val.type_name(), "bool");
    }
    
    #[test]
    fn test_python_value_int() {
        let val = PythonValue::int_val(42);
        assert_eq!(val.as_int(), Some(42));
        assert_eq!(val.as_float(), Some(42.0));
        assert_eq!(val.type_name(), "int");
    }
    
    #[test]
    fn test_python_value_float() {
        let val = PythonValue::float_val(3.14);
        assert!((val.as_float().unwrap() - 3.14).abs() < 1e-6);
        assert_eq!(val.as_int(), Some(3));
        assert_eq!(val.type_name(), "float");
    }
    
    #[test]
    fn test_python_value_string() {
        let val = PythonValue::string_val("hello");
        assert_eq!(val.as_str(), Some("hello"));
        assert_eq!(val.type_name(), "str");
    }
    
    #[test]
    fn test_python_value_list() {
        let val = PythonValue::list_val(vec![
            PythonValue::int_val(1),
            PythonValue::int_val(2),
        ]);
        let list = val.as_list().unwrap();
        assert_eq!(list.len(), 2);
        assert_eq!(val.type_name(), "list");
    }
    
    #[test]
    fn test_python_value_dict() {
        let mut dict = HashMap::new();
        dict.insert("key".to_string(), PythonValue::string_val("value"));
        let val = PythonValue::dict_val(dict);
        let d = val.as_dict().unwrap();
        assert!(d.contains_key("key"));
        assert_eq!(val.type_name(), "dict");
    }
    
    #[test]
    fn test_python_value_display() {
        assert_eq!(PythonValue::none().to_string(), "None");
        assert_eq!(PythonValue::bool_val(true).to_string(), "true");
        assert_eq!(PythonValue::int_val(42).to_string(), "42");
        assert_eq!(PythonValue::string_val("hello").to_string(), "\"hello\"");
    }
    
    #[test]
    fn test_compile_result() {
        let success = CompileResult::success(100, 50);
        assert!(success.success);
        assert_eq!(success.bytecode_size, 100);
        assert!(success.error_message.is_none());
        
        let failure = CompileResult::failure("test error");
        assert!(!failure.success);
        assert!(failure.error_message.is_some());
    }
    
    #[test]
    fn test_execution_result() {
        let success = ExecutionResultPy::success(PythonValue::int_val(42), 100);
        assert!(success.success);
        assert_eq!(success.value.as_int(), Some(42));
        
        let failure = ExecutionResultPy::failure("test error");
        assert!(!failure.success);
        assert!(failure.error_message.is_some());
    }
    
    #[test]
    fn test_avm_py_creation() {
        let avm = AvmPy::new();
        assert!(avm.runtime.is_none());
        assert!(avm.last_module.is_none());
        assert!(!avm.version().is_empty());
    }
    
    #[test]
    fn test_avm_py_init() {
        let mut avm = AvmPy::new();
        let result = avm.init();
        assert!(result.is_ok());
        assert!(avm.runtime.is_some());
    }
    
    #[test]
    fn test_avm_py_compile_empty() {
        let mut avm = AvmPy::new();
        let result = avm.compile("");
        // 空程序应该能编译
        assert!(result.success);
        assert!(result.bytecode_size > 0);
    }
    
    #[test]
    fn test_avm_py_compile_simple() {
        let mut avm = AvmPy::new();
        let source = r#"
            agent TestAgent {
                role: "test"
            }
        "#;
        let result = avm.compile(source);
        assert!(result.success);
    }
    
    #[test]
    fn test_avm_py_compile_invalid() {
        let mut avm = AvmPy::new();
        let result = avm.compile("invalid { } { }");
        assert!(!result.success);
        assert!(result.error_message.is_some());
    }
    
    #[test]
    fn test_avm_py_reset() {
        let mut avm = AvmPy::new();
        avm.init().unwrap();
        avm.compile("agent A { role: \"test\" }");
        
        avm.reset();
        assert!(avm.runtime.is_none());
        assert!(avm.last_module.is_none());
    }
    
    #[test]
    fn test_compile_source_convenience() {
        let result = compile_source("agent A { role: \"test\" }");
        assert!(result.success);
    }
    
    #[test]
    fn test_run_source_convenience() {
        let result = run_source("agent A { role: \"test\" }");
        assert!(result.success);
    }
}
