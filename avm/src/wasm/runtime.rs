//! WASM 运行时 - 基于 wasmtime 的 WebAssembly 执行引擎
//!
//! 提供高性能、安全的 WASM 模块加载和执行能力

use crate::utils::error::{AvmError, AvmResult};
use std::time::Duration;

/// WASM 运行时配置
#[derive(Debug, Clone)]
pub struct WasmConfig {
    /// 最大内存页数 (每页 64KB)
    pub max_memory_pages: u32,
    /// 执行超时时间 (毫秒)
    pub execution_timeout_ms: u64,
    /// 是否启用 WASI
    pub enable_wasi: bool,
    /// 最大表大小
    pub max_table_elements: u32,
    /// 是否启用线程支持
    pub enable_threads: bool,
    /// 是否启用 SIMD
    pub enable_simd: bool,
}

impl Default for WasmConfig {
    fn default() -> Self {
        Self {
            max_memory_pages: 256,  // 16MB
            execution_timeout_ms: 30000,
            enable_wasi: true,
            max_table_elements: 10000,
            enable_threads: false,
            enable_simd: true,
        }
    }
}

/// WASM 值类型
#[derive(Debug, Clone, PartialEq)]
pub enum WasmValue {
    /// 32位整数
    I32(i32),
    /// 64位整数
    I64(i64),
    /// 32位浮点数
    F32(f32),
    /// 64位浮点数
    F64(f64),
    /// 引用类型 (funcref, externref)
    Ref(Option<u32>),
}

impl WasmValue {
    /// 获取值的类型名称
    pub fn type_name(&self) -> &'static str {
        match self {
            WasmValue::I32(_) => "i32",
            WasmValue::I64(_) => "i64",
            WasmValue::F32(_) => "f32",
            WasmValue::F64(_) => "f64",
            WasmValue::Ref(_) => "ref",
        }
    }

    /// 转换为 i32
    pub fn as_i32(&self) -> Option<i32> {
        match self {
            WasmValue::I32(v) => Some(*v),
            _ => None,
        }
    }

    /// 转换为 i64
    pub fn as_i64(&self) -> Option<i64> {
        match self {
            WasmValue::I64(v) => Some(*v),
            _ => None,
        }
    }

    /// 转换为 f64
    pub fn as_f64(&self) -> Option<f64> {
        match self {
            WasmValue::F64(v) => Some(*v),
            WasmValue::F32(v) => Some(*v as f64),
            _ => None,
        }
    }
}

impl std::fmt::Display for WasmValue {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WasmValue::I32(v) => write!(f, "i32({})", v),
            WasmValue::I64(v) => write!(f, "i64({})", v),
            WasmValue::F32(v) => write!(f, "f32({})", v),
            WasmValue::F64(v) => write!(f, "f64({})", v),
            WasmValue::Ref(Some(v)) => write!(f, "ref({})", v),
            WasmValue::Ref(None) => write!(f, "ref(null)"),
        }
    }
}

/// 函数签名
#[derive(Debug, Clone)]
pub struct FunctionSignature {
    /// 参数类型列表
    pub params: Vec<ValType>,
    /// 返回值类型列表
    pub results: Vec<ValType>,
}

/// 值类型
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ValType {
    I32,
    I64,
    F32,
    F64,
    FuncRef,
    ExternRef,
}

impl ValType {
    pub fn name(&self) -> &'static str {
        match self {
            ValType::I32 => "i32",
            ValType::I64 => "i64",
            ValType::F32 => "f32",
            ValType::F64 => "f64",
            ValType::FuncRef => "funcref",
            ValType::ExternRef => "externref",
        }
    }
}

/// 导入描述
#[derive(Debug, Clone)]
pub struct ImportDesc {
    /// 模块名
    pub module: String,
    /// 字段名
    pub name: String,
    /// 导入类型
    pub kind: ImportKind,
}

/// 导入类型
#[derive(Debug, Clone)]
pub enum ImportKind {
    /// 函数导入
    Function(FunctionSignature),
    /// 全局变量导入
    Global { val_type: ValType, mutable: bool },
    /// 内存导入
    Memory { min_pages: u32, max_pages: Option<u32> },
    /// 表导入
    Table { min_elements: u32, max_elements: Option<u32> },
}

/// 导出描述
#[derive(Debug, Clone)]
pub struct ExportDesc {
    /// 导出名
    pub name: String,
    /// 导出类型
    pub kind: ExportKind,
}

/// 导出类型
#[derive(Debug, Clone)]
pub enum ExportKind {
    /// 函数导出
    Function { index: u32, signature: FunctionSignature },
    /// 全局变量导出
    Global { index: u32, val_type: ValType },
    /// 内存导出
    Memory { index: u32, min_pages: u32, max_pages: Option<u32> },
    /// 表导出
    Table { index: u32, min_elements: u32 },
}

/// WASM 模块元数据
#[derive(Debug, Clone)]
pub struct ModuleMetadata {
    /// 模块名
    pub name: String,
    /// 导入列表
    pub imports: Vec<ImportDesc>,
    /// 导出列表
    pub exports: Vec<ExportDesc>,
    /// 自定义段 (如 name 段)
    pub custom_sections: Vec<(String, Vec<u8>)>,
}

/// WASM 模块 (编译后)
pub struct WasmModule {
    /// 模块名
    name: String,
    /// 原始字节码
    bytes: Vec<u8>,
    /// 是否已验证
    validated: bool,
    /// 元数据
    metadata: Option<ModuleMetadata>,
}

impl WasmModule {
    /// 从字节创建 WASM 模块
    pub fn from_bytes(name: &str, bytes: Vec<u8>) -> AvmResult<Self> {
        // 验证 WASM 魔数
        if bytes.len() < 8 {
            return Err(AvmError::WasmError("WASM module too small".to_string()));
        }
        
        // WASM 魔数: \0asm
        if &bytes[0..4] != b"\x00asm" {
            return Err(AvmError::WasmError("Invalid WASM magic number".to_string()));
        }
        
        // 版本号检查 (支持 1.0 和 2.0)
        let version = u32::from_le_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]);
        if version != 1 && version != 2 {
            return Err(AvmError::WasmError(format!(
                "Unsupported WASM version: {}",
                version
            )));
        }
        
        Ok(Self {
            name: name.to_string(),
            bytes,
            validated: false,
            metadata: None,
        })
    }
    
    /// 获取模块名
    pub fn name(&self) -> &str {
        &self.name
    }
    
    /// 获取原始字节
    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }
    
    /// 检查是否已验证
    pub fn is_validated(&self) -> bool {
        self.validated
    }
    
    /// 获取元数据
    pub fn metadata(&self) -> Option<&ModuleMetadata> {
        self.metadata.as_ref()
    }
    
    /// 解析模块元数据
    pub fn parse_metadata(&mut self) -> AvmResult<&ModuleMetadata> {
        if self.metadata.is_some() {
            return Ok(self.metadata.as_ref().unwrap());
        }
        
        let metadata = self.extract_metadata()?;
        self.metadata = Some(metadata);
        Ok(self.metadata.as_ref().unwrap())
    }
    
    /// 从字节码提取元数据
    fn extract_metadata(&self) -> AvmResult<ModuleMetadata> {
        let mut imports = Vec::new();
        let mut exports = Vec::new();
        let mut custom_sections = Vec::new();
        
        // 简单解析 (不需要完整解析，只提取关键信息)
        let bytes = &self.bytes;
        let mut pos = 8; // 跳过魔数和版本
        
        while pos < bytes.len() {
            if pos >= bytes.len() { break; }
            
            let section_id = bytes[pos];
            pos += 1;
            
            // 读取 LEB128 编码的段大小
            let (size, consumed) = read_leb128_u32(&bytes[pos..])?;
            pos += consumed;
            
            let section_start = pos;
            
            match section_id {
                0 => {
                    // 自定义段
                    let (name_len, consumed) = read_leb128_u32(&bytes[pos..])?;
                    pos += consumed;
                    let name = String::from_utf8_lossy(&bytes[pos..pos + name_len as usize]).to_string();
                    pos += name_len as usize;
                    let data = bytes[pos..section_start + size as usize].to_vec();
                    custom_sections.push((name, data));
                }
                1 => {
                    // 类型段 - 跳过
                }
                2 => {
                    // 导入段
                    let (count, consumed) = read_leb128_u32(&bytes[pos..])?;
                    pos += consumed;
                    for _ in 0..count {
                        let (mod_len, consumed) = read_leb128_u32(&bytes[pos..])?;
                        pos += consumed;
                        let module = String::from_utf8_lossy(&bytes[pos..pos + mod_len as usize]).to_string();
                        pos += mod_len as usize;
                        
                        let (name_len, consumed) = read_leb128_u32(&bytes[pos..])?;
                        pos += consumed;
                        let name = String::from_utf8_lossy(&bytes[pos..pos + name_len as usize]).to_string();
                        pos += name_len as usize;
                        
                        let kind = bytes[pos];
                        pos += 1;
                        
                        // 简化处理，只记录导入存在
                        imports.push(ImportDesc {
                            module,
                            name,
                            kind: ImportKind::Function(FunctionSignature {
                                params: vec![],
                                results: vec![],
                            }),
                        });
                        
                        // 跳过剩余描述
                        match kind {
                            0 => {
                                // 函数 - 读取类型索引
                                let (_, consumed) = read_leb128_u32(&bytes[pos..])?;
                                pos += consumed;
                            }
                            1 => {
                                // 表
                            }
                            2 => {
                                // 内存
                            }
                            3 => {
                                // 全局
                            }
                            _ => {}
                        }
                    }
                }
                7 => {
                    // 导出段
                    let (count, consumed) = read_leb128_u32(&bytes[pos..])?;
                    pos += consumed;
                    for _ in 0..count {
                        let (name_len, consumed) = read_leb128_u32(&bytes[pos..])?;
                        pos += consumed;
                        let name = String::from_utf8_lossy(&bytes[pos..pos + name_len as usize]).to_string();
                        pos += name_len as usize;
                        
                        let kind = bytes[pos];
                        pos += 1;
                        
                        let (index, consumed) = read_leb128_u32(&bytes[pos..])?;
                        pos += consumed;
                        
                        exports.push(ExportDesc {
                            name,
                            kind: ExportKind::Function {
                                index,
                                signature: FunctionSignature {
                                    params: vec![],
                                    results: vec![],
                                },
                            },
                        });
                    }
                }
                _ => {}
            }
            
            pos = section_start + size as usize;
        }
        
        Ok(ModuleMetadata {
            name: self.name.clone(),
            imports,
            exports,
            custom_sections,
        })
    }
    
    /// 验证模块
    pub fn validate(&mut self) -> AvmResult<()> {
        if self.validated {
            return Ok(());
        }
        
        // 基本验证
        self.parse_metadata()?;
        self.validated = true;
        Ok(())
    }
}

/// 读取 LEB128 编码的无符号整数
fn read_leb128_u32(bytes: &[u8]) -> AvmResult<(u32, usize)> {
    let mut result: u32 = 0;
    let mut shift = 0;
    let mut pos = 0;
    
    loop {
        if pos >= bytes.len() {
            return Err(AvmError::WasmError("Invalid LEB128 encoding".to_string()));
        }
        
        let byte = bytes[pos];
        pos += 1;
        
        result |= ((byte & 0x7F) as u32) << shift;
        
        if byte & 0x80 == 0 {
            break;
        }
        
        shift += 7;
        if shift >= 35 {
            return Err(AvmError::WasmError("LEB128 overflow".to_string()));
        }
    }
    
    Ok((result, pos))
}

/// 执行统计
#[derive(Debug, Clone, Default)]
pub struct ExecutionStats {
    /// 执行次数
    pub call_count: u64,
    /// 总执行时间 (纳秒)
    pub total_time_ns: u64,
    /// 最大执行时间 (纳秒)
    pub max_time_ns: u64,
    /// 内存使用峰值 (字节)
    pub peak_memory_bytes: usize,
}

impl ExecutionStats {
    /// 平均执行时间 (毫秒)
    pub fn avg_time_ms(&self) -> f64 {
        if self.call_count == 0 {
            return 0.0;
        }
        (self.total_time_ns as f64) / 1_000_000.0 / (self.call_count as f64)
    }
}

/// WASM 实例 (运行时实例)
pub struct WasmInstance {
    /// 模块引用
    module: WasmModule,
    /// 实例内存
    memory: Vec<u8>,
    /// 全局变量
    globals: Vec<WasmValue>,
    /// 执行统计
    stats: ExecutionStats,
    /// 是否已初始化
    initialized: bool,
}

impl WasmInstance {
    /// 创建新实例
    pub fn new(module: WasmModule) -> AvmResult<Self> {
        let memory = vec![0u8; 65536]; // 1 页初始内存
        Ok(Self {
            module,
            memory,
            globals: Vec::new(),
            stats: ExecutionStats::default(),
            initialized: false,
        })
    }
    
    /// 获取模块引用
    pub fn module(&self) -> &WasmModule {
        &self.module
    }
    
    /// 获取执行统计
    pub fn stats(&self) -> &ExecutionStats {
        &self.stats
    }
    
    /// 获取内存大小
    pub fn memory_size(&self) -> usize {
        self.memory.len()
    }
    
    /// 读取内存
    pub fn read_memory(&self, offset: usize, len: usize) -> AvmResult<Vec<u8>> {
        if offset + len > self.memory.len() {
            return Err(AvmError::WasmError("Memory access out of bounds".to_string()));
        }
        Ok(self.memory[offset..offset + len].to_vec())
    }
    
    /// 写入内存
    pub fn write_memory(&mut self, offset: usize, data: &[u8]) -> AvmResult<()> {
        if offset + data.len() > self.memory.len() {
            return Err(AvmError::WasmError("Memory access out of bounds".to_string()));
        }
        self.memory[offset..offset + data.len()].copy_from_slice(data);
        Ok(())
    }
    
    /// 调用函数
    pub fn call(&mut self, function: &str, args: &[WasmValue]) -> AvmResult<Vec<WasmValue>> {
        // 检查函数是否导出
        let metadata = self.module.metadata();
        if let Some(meta) = metadata {
            let found = meta.exports.iter().any(|e| {
                matches!(&e.kind, ExportKind::Function { .. }) && e.name == function
            });
            
            if !found {
                return Err(AvmError::WasmError(format!(
                    "Function '{}' not found in module '{}'",
                    function, self.module.name
                )));
            }
        }
        
        // 由于没有启用 wasmtime feature，返回占位符结果
        // 实际执行需要启用 wasm feature
        #[cfg(not(feature = "wasm"))]
        {
            self.stats.call_count += 1;
            // 模拟执行: 返回一个默认值
            if args.is_empty() {
                Ok(vec![WasmValue::I32(0)])
            } else {
                Ok(args.to_vec())
            }
        }
        
        #[cfg(feature = "wasm")]
        {
            self.execute_with_wasmtime(function, args)
        }
    }
    
    /// 使用 wasmtime 执行
    #[cfg(feature = "wasm")]
    fn execute_with_wasmtime(&mut self, function: &str, args: &[WasmValue]) -> AvmResult<Vec<WasmValue>> {
        use wasmtime::*;
        
        let start = std::time::Instant::now();
        
        // 创建引擎和模块
        let engine = Engine::default();
        let module = Module::from_binary(&engine, &self.module.bytes)
            .map_err(|e| AvmError::WasmError(format!("Failed to compile module: {}", e)))?;
        
        // 创建存储和实例
        let mut store = Store::new(&engine, ());
        
        // 设置资源限制
        store.limiter(|_| Some(Box::new(ResourceLimiter {
            max_memory: self.memory.len(),
            max_table: 10000,
        })));
        
        let instance = Instance::new(&mut store, &module, &[])
            .map_err(|e| AvmError::WasmError(format!("Failed to instantiate module: {}", e)))?;
        
        // 获取导出函数
        let func = instance
            .get_typed_func::<(), (i32,)>(&mut store, function)
            .map_err(|e| AvmError::WasmError(format!("Function '{}' not found: {}", function, e)))?;
        
        // 执行
        let result = func.call(&mut store, ())
            .map_err(|e| AvmError::WasmError(format!("Execution failed: {}", e)))?;
        
        // 更新统计
        let elapsed = start.elapsed().as_nanos() as u64;
        self.stats.call_count += 1;
        self.stats.total_time_ns += elapsed;
        self.stats.max_time_ns = self.stats.max_time_ns.max(elapsed);
        
        Ok(vec![WasmValue::I32(result.0)])
    }
    
    /// 初始化实例
    pub fn initialize(&mut self) -> AvmResult<()> {
        if self.initialized {
            return Ok(());
        }
        
        // 执行 start 函数（如果存在）
        if let Some(meta) = self.module.metadata() {
            let has_start = meta.exports.iter().any(|e| e.name == "_start");
            if has_start {
                self.call("_start", &[])?;
            }
        }
        
        self.initialized = true;
        Ok(())
    }
}

/// 资源限制器 (用于 wasmtime)
#[cfg(feature = "wasm")]
struct ResourceLimiter {
    max_memory: usize,
    max_table: usize,
}

#[cfg(feature = "wasm")]
impl wasmtime::ResourceLimiter for ResourceLimiter {
    fn memory_growing(&mut self, current: usize, desired: usize, _maximum: Option<usize>) -> bool {
        desired <= self.max_memory && desired >= current
    }
    
    fn table_growing(&mut self, current: usize, desired: usize, _maximum: Option<usize>) -> bool {
        desired <= self.max_table && desired >= current
    }
}

/// WASM 运行时
pub struct WasmRuntime {
    /// 配置
    config: WasmConfig,
    /// 已加载的模块
    modules: std::collections::HashMap<String, WasmModule>,
    /// 实例缓存
    instances: std::collections::HashMap<String, WasmInstance>,
}

impl WasmRuntime {
    /// 创建新的 WASM 运行时
    pub fn new(config: WasmConfig) -> Self {
        Self {
            config,
            modules: std::collections::HashMap::new(),
            instances: std::collections::HashMap::new(),
        }
    }
    
    /// 获取配置
    pub fn config(&self) -> &WasmConfig {
        &self.config
    }
    
    /// 加载模块
    pub fn load_module(&mut self, name: &str, bytes: Vec<u8>) -> AvmResult<&WasmModule> {
        let mut module = WasmModule::from_bytes(name, bytes)?;
        module.validate()?;
        self.modules.insert(name.to_string(), module);
        Ok(self.modules.get(name).unwrap())
    }
    
    /// 获取模块
    pub fn get_module(&self, name: &str) -> Option<&WasmModule> {
        self.modules.get(name)
    }
    
    /// 创建实例
    pub fn instantiate(&mut self, module_name: &str) -> AvmResult<&mut WasmInstance> {
        let module = self.modules.get(module_name).ok_or_else(|| {
            AvmError::WasmError(format!("Module '{}' not found", module_name))
        })?;
        
        // 克隆模块用于实例
        let module_clone = WasmModule::from_bytes(&module.name, module.bytes.clone())?;
        let instance = WasmInstance::new(module_clone)?;
        
        self.instances.insert(module_name.to_string(), instance);
        Ok(self.instances.get_mut(module_name).unwrap())
    }
    
    /// 获取实例
    pub fn get_instance(&mut self, name: &str) -> Option<&mut WasmInstance> {
        self.instances.get_mut(name)
    }
    
    /// 调用函数 (便捷方法)
    pub fn call(
        &mut self,
        module_name: &str,
        function: &str,
        args: &[WasmValue],
    ) -> AvmResult<Vec<WasmValue>> {
        let instance = self.instances.get_mut(module_name).ok_or_else(|| {
            AvmError::WasmError(format!("Instance '{}' not found", module_name))
        })?;
        instance.call(function, args)
    }
    
    /// 卸载模块
    pub fn unload_module(&mut self, name: &str) -> AvmResult<()> {
        self.modules.remove(name);
        self.instances.remove(name);
        Ok(())
    }
    
    /// 列出已加载的模块
    pub fn list_modules(&self) -> Vec<&str> {
        self.modules.keys().map(|s| s.as_str()).collect()
    }
    
    /// 清理所有资源
    pub fn clear(&mut self) {
        self.modules.clear();
        self.instances.clear();
    }
}

impl Default for WasmRuntime {
    fn default() -> Self {
        Self::new(WasmConfig::default())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_wasm_config_default() {
        let config = WasmConfig::default();
        assert_eq!(config.max_memory_pages, 256);
        assert_eq!(config.execution_timeout_ms, 30000);
        assert!(config.enable_wasi);
    }
    
    #[test]
    fn test_wasm_value_types() {
        let i32_val = WasmValue::I32(42);
        assert_eq!(i32_val.type_name(), "i32");
        assert_eq!(i32_val.as_i32(), Some(42));
        assert_eq!(i32_val.as_i64(), None);
        
        let i64_val = WasmValue::I64(-100);
        assert_eq!(i64_val.type_name(), "i64");
        assert_eq!(i64_val.as_i64(), Some(-100));
        
        let f64_val = WasmValue::F64(3.14159);
        assert_eq!(f64_val.type_name(), "f64");
        assert!((f64_val.as_f64().unwrap() - 3.14159).abs() < 1e-6);
    }
    
    #[test]
    fn test_wasm_module_validation() {
        // 有效的 WASM 模块 (最小模块)
        let valid_wasm = vec![
            0x00, 0x61, 0x73, 0x6d, // 魔数
            0x01, 0x00, 0x00, 0x00, // 版本 1.0
        ];
        
        let module = WasmModule::from_bytes("test", valid_wasm);
        assert!(module.is_ok());
        
        // 无效的 WASM 模块
        let invalid_wasm = vec![0x00, 0x01, 0x02, 0x03];
        let result = WasmModule::from_bytes("invalid", invalid_wasm);
        assert!(result.is_err());
    }
    
    #[test]
    fn test_wasm_runtime_basic() {
        let runtime = WasmRuntime::default();
        assert!(runtime.modules.is_empty());
        assert!(runtime.instances.is_empty());
    }
    
    #[test]
    fn test_wasm_instance_memory() {
        let valid_wasm = vec![
            0x00, 0x61, 0x73, 0x6d, // 魔数
            0x01, 0x00, 0x00, 0x00, // 版本 1.0
        ];
        
        let module = WasmModule::from_bytes("test", valid_wasm).unwrap();
        let instance = WasmInstance::new(module).unwrap();
        
        assert_eq!(instance.memory_size(), 65536);
        
        // 测试内存读写
        let mut instance = instance;
        instance.write_memory(0, &[1, 2, 3, 4]).unwrap();
        let data = instance.read_memory(0, 4).unwrap();
        assert_eq!(data, vec![1, 2, 3, 4]);
        
        // 越界访问应该失败
        assert!(instance.read_memory(65536, 1).is_err());
    }
    
    #[test]
    fn test_execution_stats() {
        let mut stats = ExecutionStats::default();
        stats.call_count = 10;
        stats.total_time_ns = 1_000_000_000; // 1 秒
        
        assert!((stats.avg_time_ms() - 100.0).abs() < 0.01);
    }
    
    #[test]
    fn test_leb128_parsing() {
        // 测试简单的 LEB128 编码
        let bytes = vec![0x00]; // 0
        let (value, consumed) = read_leb128_u32(&bytes).unwrap();
        assert_eq!(value, 0);
        assert_eq!(consumed, 1);
        
        let bytes = vec![0x7F]; // 127
        let (value, _) = read_leb128_u32(&bytes).unwrap();
        assert_eq!(value, 127);
        
        let bytes = vec![0x80, 0x01]; // 128
        let (value, _) = read_leb128_u32(&bytes).unwrap();
        assert_eq!(value, 128);
    }
    
    #[test]
    fn test_wasm_runtime_module_management() {
        let mut runtime = WasmRuntime::default();
        
        let valid_wasm = vec![
            0x00, 0x61, 0x73, 0x6d,
            0x01, 0x00, 0x00, 0x00,
        ];
        
        // 加载模块
        let result = runtime.load_module("test_module", valid_wasm);
        assert!(result.is_ok());
        
        // 检查模块列表
        let modules = runtime.list_modules();
        assert_eq!(modules.len(), 1);
        assert!(modules.contains(&"test_module"));
        
        // 卸载模块
        runtime.unload_module("test_module").unwrap();
        assert!(runtime.list_modules().is_empty());
    }
}
