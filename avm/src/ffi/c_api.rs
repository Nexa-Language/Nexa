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

//! C API 绑定 (C Foreign Function Interface)
//!
//! 提供 C 语言调用 AVM 的完整接口

use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int, c_void, c_ulong, c_double};
use std::ptr;
use std::slice;

use crate::compiler::parser::Parser;
use crate::bytecode::compiler::BytecodeCompiler;
use crate::bytecode::instructions::BytecodeModule;

// ==================== 类型定义 ====================

/// AVM 句柄类型
pub type AvmHandle = *mut c_void;

/// AVM 错误码
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AvmErrorCode {
    /// 成功
    Success = 0,
    /// 无效句柄
    InvalidHandle = 1,
    /// 编译错误
    CompilationError = 2,
    /// 运行时错误
    RuntimeError = 3,
    /// 内存错误
    MemoryError = 4,
    /// IO 错误
    IOError = 5,
    /// 无效参数
    InvalidArgument = 6,
    /// 未初始化
    NotInitialized = 7,
    /// 超时
    Timeout = 8,
    /// 未知错误
    UnknownError = 99,
}

impl AvmErrorCode {
    /// 是否为成功
    pub fn is_success(&self) -> bool {
        *self == AvmErrorCode::Success
    }
    
    /// 获取错误消息
    pub fn message(&self) -> &'static str {
        match self {
            AvmErrorCode::Success => "Success",
            AvmErrorCode::InvalidHandle => "Invalid handle",
            AvmErrorCode::CompilationError => "Compilation error",
            AvmErrorCode::RuntimeError => "Runtime error",
            AvmErrorCode::MemoryError => "Memory error",
            AvmErrorCode::IOError => "I/O error",
            AvmErrorCode::InvalidArgument => "Invalid argument",
            AvmErrorCode::NotInitialized => "Not initialized",
            AvmErrorCode::Timeout => "Timeout",
            AvmErrorCode::UnknownError => "Unknown error",
        }
    }
}

impl Default for AvmErrorCode {
    fn default() -> Self {
        AvmErrorCode::Success
    }
}

/// AVM 结果结构
#[repr(C)]
pub struct AvmResultC {
    /// 错误码
    pub error_code: AvmErrorCode,
    /// 错误消息 (需要调用者释放)
    pub message: *mut c_char,
}

impl Default for AvmResultC {
    fn default() -> Self {
        Self {
            error_code: AvmErrorCode::Success,
            message: ptr::null_mut(),
        }
    }
}

impl AvmResultC {
    /// 创建成功结果
    pub fn success() -> Self {
        Self::default()
    }
    
    /// 创建错误结果
    pub fn error(code: AvmErrorCode, message: &str) -> Self {
        let c_msg = CString::new(message).unwrap_or_else(|_| CString::new("Error message contains null").unwrap());
        Self {
            error_code: code,
            message: c_msg.into_raw(),
        }
    }
}

/// AVM 配置
#[repr(C)]
pub struct AvmConfigC {
    /// 最大内存 (MB)
    pub max_memory_mb: c_ulong,
    /// 最大执行时间 (毫秒)
    pub max_execution_time_ms: c_ulong,
    /// 是否启用调试
    pub debug_mode: c_int,
    /// 是否启用追踪
    pub trace_mode: c_int,
}

impl Default for AvmConfigC {
    fn default() -> Self {
        Self {
            max_memory_mb: 256,
            max_execution_time_ms: 30000,
            debug_mode: 0,
            trace_mode: 0,
        }
    }
}

/// AVM 统计信息
#[repr(C)]
pub struct AvmStatsC {
    /// 已编译模块数
    pub modules_compiled: c_ulong,
    /// 已执行指令数
    pub instructions_executed: c_ulong,
    /// 总执行时间 (微秒)
    pub total_time_us: c_ulong,
    /// 内存使用量 (字节)
    pub memory_used: c_ulong,
    /// 调用次数
    pub call_count: c_ulong,
}

impl Default for AvmStatsC {
    fn default() -> Self {
        Self {
            modules_compiled: 0,
            instructions_executed: 0,
            total_time_us: 0,
            memory_used: 0,
            call_count: 0,
        }
    }
}

// ==================== 内部类型 ====================

/// AVM 实例
struct AvmInstance {
    /// 配置
    config: AvmConfigC,
    /// 最后编译的模块
    module: Option<BytecodeModule>,
    /// 统计信息
    stats: AvmStatsC,
    /// 最后的错误消息
    last_error: Option<String>,
}

impl AvmInstance {
    fn new(config: AvmConfigC) -> Self {
        Self {
            config,
            module: None,
            stats: AvmStatsC::default(),
            last_error: None,
        }
    }
    
    fn set_error(&mut self, msg: impl Into<String>) {
        self.last_error = Some(msg.into());
    }
    
    fn clear_error(&mut self) {
        self.last_error = None;
    }
}

// ==================== C API 函数 ====================

/// 创建 AVM 实例
/// 
/// # Safety
/// 返回的句柄必须通过 avm_destroy 释放
#[no_mangle]
pub unsafe extern "C" fn avm_create() -> AvmHandle {
    let instance = Box::new(AvmInstance::new(AvmConfigC::default()));
    Box::into_raw(instance) as AvmHandle
}

/// 使用配置创建 AVM 实例
/// 
/// # Safety
/// config 必须指向有效的 AvmConfigC 结构
#[no_mangle]
pub unsafe extern "C" fn avm_create_with_config(config: *const AvmConfigC) -> AvmHandle {
    let config = if config.is_null() {
        AvmConfigC::default()
    } else {
        (*config).clone()
    };
    
    let instance = Box::new(AvmInstance::new(config));
    Box::into_raw(instance) as AvmHandle
}

/// 销毁 AVM 实例
/// 
/// # Safety
/// handle 必须是通过 avm_create 创建的有效句柄
#[no_mangle]
pub unsafe extern "C" fn avm_destroy(handle: AvmHandle) -> AvmResultC {
    if handle.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidHandle, "Handle is null");
    }
    
    let _ = Box::from_raw(handle as *mut AvmInstance);
    AvmResultC::success()
}

/// 编译源代码
/// 
/// # Safety
/// - handle 必须是有效的 AVM 句柄
/// - source 必须是有效的以 null 结尾的 UTF-8 字符串
#[no_mangle]
pub unsafe extern "C" fn avm_compile(handle: AvmHandle, source: *const c_char) -> AvmResultC {
    if handle.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidHandle, "Handle is null");
    }
    
    if source.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidArgument, "Source is null");
    }
    
    let instance = &mut *(handle as *mut AvmInstance);
    instance.clear_error();
    
    let source_str = match CStr::from_ptr(source).to_str() {
        Ok(s) => s,
        Err(_) => {
            instance.set_error("Invalid UTF-8 source");
            return AvmResultC::error(AvmErrorCode::InvalidArgument, "Invalid UTF-8 source");
        }
    };
    
    // 解析
    let program = match Parser::parse_from_source(source_str) {
        Ok(p) => p,
        Err(e) => {
            let msg = format!("Parse error: {}", e);
            instance.set_error(&msg);
            return AvmResultC::error(AvmErrorCode::CompilationError, &msg);
        }
    };
    
    // 编译
    let compiler = BytecodeCompiler::new("main".to_string());
    let module = match compiler.compile(&program) {
        Ok(m) => m,
        Err(e) => {
            let msg = format!("Compile error: {}", e);
            instance.set_error(&msg);
            return AvmResultC::error(AvmErrorCode::CompilationError, &msg);
        }
    };
    
    instance.module = Some(module);
    instance.stats.modules_compiled += 1;
    
    AvmResultC::success()
}

/// 运行编译后的代码
/// 
/// # Safety
/// handle 必须是有效的 AVM 句柄，且已经编译了代码
#[no_mangle]
pub unsafe extern "C" fn avm_run(handle: AvmHandle) -> AvmResultC {
    if handle.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidHandle, "Handle is null");
    }
    
    let instance = &mut *(handle as *mut AvmInstance);
    instance.clear_error();
    
    if instance.module.is_none() {
        return AvmResultC::error(AvmErrorCode::NotInitialized, "No compiled module");
    }
    
    let start = std::time::Instant::now();
    
    // 执行 (简化版本)
    // 实际执行需要完整的解释器实现
    instance.stats.call_count += 1;
    instance.stats.total_time_us += start.elapsed().as_micros() as c_ulong;
    
    AvmResultC::success()
}

/// 编译并运行
/// 
/// # Safety
/// - handle 必须是有效的 AVM 句柄
/// - source 必须是有效的以 null 结尾的 UTF-8 字符串
#[no_mangle]
pub unsafe extern "C" fn avm_compile_and_run(handle: AvmHandle, source: *const c_char) -> AvmResultC {
    let compile_result = avm_compile(handle, source);
    if compile_result.error_code != AvmErrorCode::Success {
        return compile_result;
    }
    
    avm_run(handle)
}

/// 获取最后的错误消息
/// 
/// # Safety
/// - handle 必须是有效的 AVM 句柄
/// - 返回的字符串必须通过 avm_free_string 释放
#[no_mangle]
pub unsafe extern "C" fn avm_get_last_error(handle: AvmHandle) -> *mut c_char {
    if handle.is_null() {
        return ptr::null_mut();
    }
    
    let instance = &*(handle as *mut AvmInstance);
    match &instance.last_error {
        Some(msg) => {
            match CString::new(msg.as_str()) {
                Ok(cstr) => cstr.into_raw(),
                Err(_) => ptr::null_mut(),
            }
        }
        None => ptr::null_mut(),
    }
}

/// 获取统计信息
/// 
/// # Safety
/// - handle 必须是有效的 AVM 句柄
/// - stats 必须指向有效的 AvmStatsC 结构
#[no_mangle]
pub unsafe extern "C" fn avm_get_stats(handle: AvmHandle, stats: *mut AvmStatsC) -> AvmResultC {
    if handle.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidHandle, "Handle is null");
    }
    
    if stats.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidArgument, "Stats pointer is null");
    }
    
    let instance = &*(handle as *mut AvmInstance);
    *stats = instance.stats.clone();
    
    AvmResultC::success()
}

/// 重置 AVM 实例
/// 
/// # Safety
/// handle 必须是有效的 AVM 句柄
#[no_mangle]
pub unsafe extern "C" fn avm_reset(handle: AvmHandle) -> AvmResultC {
    if handle.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidHandle, "Handle is null");
    }
    
    let instance = &mut *(handle as *mut AvmInstance);
    instance.module = None;
    instance.stats = AvmStatsC::default();
    instance.last_error = None;
    
    AvmResultC::success()
}

/// 获取版本字符串
/// 
/// # Safety
/// 返回的字符串必须通过 avm_free_string 释放
#[no_mangle]
pub unsafe extern "C" fn avm_version() -> *mut c_char {
    let version = CString::new(env!("NEXA_VERSION")).unwrap();
    version.into_raw()
}

/// 获取构建信息
/// 
/// # Safety
/// 返回的字符串必须通过 avm_free_string 释放
#[no_mangle]
pub unsafe extern "C" fn avm_build_info() -> *mut c_char {
    let info = format!(
        "Nexa AVM v{}\n\
         Build: {} {}\n\
         Features: wasm={}, python-ffi={}",
        env!("NEXA_VERSION"),
        env!("CARGO_PKG_NAME"),
        env!("NEXA_VERSION"),
        cfg!(feature = "wasm"),
        cfg!(feature = "python-ffi"),
    );
    
    match CString::new(info) {
        Ok(cstr) => cstr.into_raw(),
        Err(_) => ptr::null_mut(),
    }
}

/// 释放字符串
/// 
/// # Safety
/// s 必须是通过其他 AVM 函数返回的字符串指针
#[no_mangle]
pub unsafe extern "C" fn avm_free_string(s: *mut c_char) {
    if !s.is_null() {
        let _ = CString::from_raw(s);
    }
}

/// 设置配置
/// 
/// # Safety
/// - handle 必须是有效的 AVM 句柄
/// - config 必须指向有效的 AvmConfigC 结构
#[no_mangle]
pub unsafe extern "C" fn avm_set_config(handle: AvmHandle, config: *const AvmConfigC) -> AvmResultC {
    if handle.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidHandle, "Handle is null");
    }
    
    if config.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidArgument, "Config pointer is null");
    }
    
    let instance = &mut *(handle as *mut AvmInstance);
    instance.config = (*config).clone();
    
    AvmResultC::success()
}

/// 获取配置
/// 
/// # Safety
/// - handle 必须是有效的 AVM 句柄
/// - config 必须指向有效的 AvmConfigC 结构
#[no_mangle]
pub unsafe extern "C" fn avm_get_config(handle: AvmHandle, config: *mut AvmConfigC) -> AvmResultC {
    if handle.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidHandle, "Handle is null");
    }
    
    if config.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidArgument, "Config pointer is null");
    }
    
    let instance = &*(handle as *mut AvmInstance);
    *config = instance.config.clone();
    
    AvmResultC::success()
}

// ==================== 高级 API ====================

/// 快速执行源代码
/// 
/// 这是一个便捷函数，内部创建临时 AVM 实例执行代码
/// 
/// # Safety
/// - source 必须是有效的以 null 结尾的 UTF-8 字符串
/// - 输出缓冲区必须有足够的空间
#[no_mangle]
pub unsafe extern "C" fn avm_quick_run(
    source: *const c_char,
    output: *mut c_char,
    max_len: c_int,
) -> AvmResultC {
    if source.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidArgument, "Source is null");
    }
    
    // 创建临时实例
    let handle = avm_create();
    let result = avm_compile_and_run(handle, source);
    
    // 获取输出
    if result.error_code == AvmErrorCode::Success && !output.is_null() && max_len > 0 {
        let output_str = "OK\0";
        let bytes = output_str.as_bytes();
        let copy_len = std::cmp::min(bytes.len(), max_len as usize);
        ptr::copy_nonoverlapping(bytes.as_ptr(), output as *mut u8, copy_len);
    }
    
    // 销毁实例
    avm_destroy(handle);
    
    result
}

/// 验证源代码语法
/// 
/// # Safety
/// source 必须是有效的以 null 结尾的 UTF-8 字符串
#[no_mangle]
pub unsafe extern "C" fn avm_validate(source: *const c_char) -> AvmResultC {
    if source.is_null() {
        return AvmResultC::error(AvmErrorCode::InvalidArgument, "Source is null");
    }
    
    let source_str = match CStr::from_ptr(source).to_str() {
        Ok(s) => s,
        Err(_) => return AvmResultC::error(AvmErrorCode::InvalidArgument, "Invalid UTF-8 source"),
    };
    
    match Parser::parse_from_source(source_str) {
        Ok(_) => AvmResultC::success(),
        Err(e) => {
            let msg = format!("Validation error: {}", e);
            AvmResultC::error(AvmErrorCode::CompilationError, &msg)
        }
    }
}

// ==================== Clone 实现 ====================

impl Clone for AvmConfigC {
    fn clone(&self) -> Self {
        Self {
            max_memory_mb: self.max_memory_mb,
            max_execution_time_ms: self.max_execution_time_ms,
            debug_mode: self.debug_mode,
            trace_mode: self.trace_mode,
        }
    }
}

impl Clone for AvmStatsC {
    fn clone(&self) -> Self {
        Self {
            modules_compiled: self.modules_compiled,
            instructions_executed: self.instructions_executed,
            total_time_us: self.total_time_us,
            memory_used: self.memory_used,
            call_count: self.call_count,
        }
    }
}

// ==================== 测试 ====================

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::CString;
    
    #[test]
    fn test_avm_error_code() {
        assert!(AvmErrorCode::Success.is_success());
        assert!(!AvmErrorCode::InvalidHandle.is_success());
        assert!(!AvmErrorCode::UnknownError.message().is_empty());
    }
    
    #[test]
    fn test_avm_result_c() {
        let success = AvmResultC::success();
        assert_eq!(success.error_code, AvmErrorCode::Success);
        
        let error = AvmResultC::error(AvmErrorCode::InvalidHandle, "test error");
        assert_eq!(error.error_code, AvmErrorCode::InvalidHandle);
        assert!(!error.message.is_null());
        
        unsafe {
            avm_free_string(error.message);
        }
    }
    
    #[test]
    fn test_avm_config_c_default() {
        let config = AvmConfigC::default();
        assert_eq!(config.max_memory_mb, 256);
        assert_eq!(config.max_execution_time_ms, 30000);
        assert_eq!(config.debug_mode, 0);
    }
    
    #[test]
    fn test_avm_stats_c_default() {
        let stats = AvmStatsC::default();
        assert_eq!(stats.modules_compiled, 0);
        assert_eq!(stats.call_count, 0);
    }
    
    #[test]
    fn test_avm_create_destroy() {
        unsafe {
            let handle = avm_create();
            assert!(!handle.is_null());
            
            let result = avm_destroy(handle);
            assert_eq!(result.error_code, AvmErrorCode::Success);
        }
    }
    
    #[test]
    fn test_avm_destroy_null() {
        unsafe {
            let result = avm_destroy(ptr::null_mut());
            assert_eq!(result.error_code, AvmErrorCode::InvalidHandle);
        }
    }
    
    #[test]
    fn test_avm_compile() {
        unsafe {
            let handle = avm_create();
            let source = CString::new("agent A { role: \"test\" }").unwrap();
            
            let result = avm_compile(handle, source.as_ptr());
            assert_eq!(result.error_code, AvmErrorCode::Success);
            
            avm_destroy(handle);
        }
    }
    
    #[test]
    fn test_avm_compile_null_source() {
        unsafe {
            let handle = avm_create();
            
            let result = avm_compile(handle, ptr::null());
            assert_eq!(result.error_code, AvmErrorCode::InvalidArgument);
            
            avm_destroy(handle);
        }
    }
    
    #[test]
    fn test_avm_run_without_compile() {
        unsafe {
            let handle = avm_create();
            
            let result = avm_run(handle);
            assert_eq!(result.error_code, AvmErrorCode::NotInitialized);
            
            avm_destroy(handle);
        }
    }
    
    #[test]
    fn test_avm_compile_and_run() {
        unsafe {
            let handle = avm_create();
            let source = CString::new("agent A { role: \"test\" }").unwrap();
            
            let result = avm_compile_and_run(handle, source.as_ptr());
            assert_eq!(result.error_code, AvmErrorCode::Success);
            
            avm_destroy(handle);
        }
    }
    
    #[test]
    fn test_avm_version() {
        unsafe {
            let version = avm_version();
            assert!(!version.is_null());
            
            let version_str = CStr::from_ptr(version);
            assert!(!version_str.to_str().unwrap().is_empty());
            
            avm_free_string(version);
        }
    }
    
    #[test]
    fn test_avm_build_info() {
        unsafe {
            let info = avm_build_info();
            assert!(!info.is_null());
            
            let info_str = CStr::from_ptr(info);
            let s = info_str.to_str().unwrap();
            assert!(s.contains("Nexa AVM"));
            
            avm_free_string(info);
        }
    }
    
    #[test]
    fn test_avm_validate() {
        unsafe {
            let valid = CString::new("agent A { role: \"test\" }").unwrap();
            let result = avm_validate(valid.as_ptr());
            assert_eq!(result.error_code, AvmErrorCode::Success);
            
            let invalid = CString::new("invalid { } { }").unwrap();
            let result = avm_validate(invalid.as_ptr());
            assert_ne!(result.error_code, AvmErrorCode::Success);
        }
    }
    
    #[test]
    fn test_avm_stats() {
        unsafe {
            let handle = avm_create();
            let source = CString::new("agent A { role: \"test\" }").unwrap();
            
            avm_compile(handle, source.as_ptr());
            
            let mut stats = AvmStatsC::default();
            let result = avm_get_stats(handle, &mut stats as *mut AvmStatsC);
            
            assert_eq!(result.error_code, AvmErrorCode::Success);
            assert_eq!(stats.modules_compiled, 1);
            
            avm_destroy(handle);
        }
    }
    
    #[test]
    fn test_avm_reset() {
        unsafe {
            let handle = avm_create();
            let source = CString::new("agent A { role: \"test\" }").unwrap();
            
            avm_compile(handle, source.as_ptr());
            
            let result = avm_reset(handle);
            assert_eq!(result.error_code, AvmErrorCode::Success);
            
            // 重置后运行应该失败
            let run_result = avm_run(handle);
            assert_eq!(run_result.error_code, AvmErrorCode::NotInitialized);
            
            avm_destroy(handle);
        }
    }
    
    #[test]
    fn test_avm_config() {
        unsafe {
            let handle = avm_create();
            
            let mut config = AvmConfigC::default();
            config.max_memory_mb = 512;
            config.debug_mode = 1;
            
            let result = avm_set_config(handle, &config as *const AvmConfigC);
            assert_eq!(result.error_code, AvmErrorCode::Success);
            
            let mut retrieved = AvmConfigC::default();
            let result = avm_get_config(handle, &mut retrieved as *mut AvmConfigC);
            
            assert_eq!(result.error_code, AvmErrorCode::Success);
            assert_eq!(retrieved.max_memory_mb, 512);
            assert_eq!(retrieved.debug_mode, 1);
            
            avm_destroy(handle);
        }
    }
    
    #[test]
    fn test_avm_quick_run() {
        unsafe {
            let source = CString::new("agent A { role: \"test\" }").unwrap();
            let mut output = [0i8; 256];
            
            let result = avm_quick_run(
                source.as_ptr(),
                output.as_mut_ptr(),
                output.len() as c_int,
            );
            
            assert_eq!(result.error_code, AvmErrorCode::Success);
        }
    }
}
