# 文档示例验证计划

## 目标
验证官方文档中的所有示例代码是否能在当前编译器中正确解析和编译。

## 验证结果汇总

**测试时间**: 2026-03-23
**总计**: 31 个示例
**通过**: 0 个
**失败**: 31 个
**通过率**: 0.0%

## 发现的问题

### 1. 解析器与代码生成器不匹配
**问题**: `parse()` 返回 Lark Tree 对象，但 `CodeGenerator` 期望字典格式的 AST
**错误**: `'Tree' object has no attribute 'get'`
**影响**: 所有示例

**解决方案**: 需要 AST 转换层将 Lark Tree 转换为字典格式

### 2. 不支持的语法特性

#### 2.1 整数类型属性值
**文档示例**:
```nexa
agent Bot {
    max_tokens: 4096,
    timeout: 30
}
```
**错误**: `No terminal matches '4' in the current parser context`
**原因**: 属性值只支持字符串、标识符、数组，不支持整数

**修复优先级**: 高
**修复方案**: 在词法分析器中添加 INTEGER_LITERAL 支持

#### 2.2 Fallback 语法
**文档示例**:
```nexa
agent Bot {
    model: ["openai/gpt-4", fallback: "deepseek/deepseek-chat"]
}
```
**错误**: `No terminal matches '"' in the current parser context`
**原因**: 数组内不支持 `fallback:` 语法

**修复优先级**: 高
**修复方案**: 扩展数组元素语法支持 `fallback:` 前缀

#### 2.3 print 语句
**文档示例**:
```nexa
flow main {
    print(result)
}
```
**错误**: `No terminal matches 'p' in the current parser context`
**原因**: flow 体不支持 print 语句

**修复优先级**: 中
**修复方案**: 在 flow_body 语法规则中添加 print 语句支持

#### 2.4 带参数的 flow
**文档示例**:
```nexa
flow process_user(user_id: string, action: string) {
    ...
}
```
**错误**: `No terminal matches '(' in the current parser context`
**原因**: flow 不支持参数定义

**修复优先级**: 高
**修复方案**: 扩展 flow 语法支持参数列表

#### 2.5 match intent 语句
**文档示例**:
```nexa
response = match user_input {
    intent("查询天气") => WeatherBot.run(user_input),
    _ => "无法理解"
}
```
**错误**: 不支持 match 语法
**原因**: flow 体不支持 match 表达式

**修复优先级**: 高
**修复方案**: 添加 match_intent 语法规则

#### 2.6 DAG 操作符 (|>>, &>>, ??)
**文档示例**:
```nexa
results = input_data |>> [Researcher, Analyst, Writer]
result = input_data |>> [A, B] &>> Merger
```
**错误**: 不支持这些操作符
**原因**: 词法分析器和语法分析器未定义这些操作符

**修复优先级**: 高
**修复方案**: 
1. 词法分析器添加 |>>, &>>, ?? token
2. 语法分析器添加 DAG 表达式规则

#### 2.7 loop until 循环
**文档示例**:
```nexa
loop {
    draft = Writer.run(draft)
} until ("文章完美")
```
**错误**: 不支持 loop 语法
**原因**: flow 体不支持 loop 语句

**修复优先级**: 中
**修复方案**: 添加 loop_until 语法规则

#### 2.8 semantic_if 语句
**文档示例**:
```nexa
result = semantic_if (text, "是否包含敏感信息") {
    "是" => ...,
    "否" => ...
}
```
**错误**: 不支持 semantic_if 语法
**原因**: flow 体不支持 semantic_if 表达式

**修复优先级**: 中
**修复方案**: 添加 semantic_if 语法规则

#### 2.9 try/catch 异常处理
**文档示例**:
```nexa
try {
    result = Bot.run("你好")
} catch (error) {
    print("发生错误")
}
```
**错误**: 不支持 try/catch 语法
**原因**: flow 体不支持 try/catch 语句

**修复优先级**: 中
**修复方案**: 添加 try_catch 语法规则

#### 2.10 标准库调用语法
**文档示例**:
```nexa
content = std.fs.read("data.txt")
response = std.http.get("https://api.example.com")
```
**错误**: 不支持标准库调用
**原因**: 缺少标准库函数调用的语法支持

**修复优先级**: 高
**修复方案**: 在表达式规则中添加标准库调用语法

#### 2.11 tool 定义语法
**文档示例**:
```nexa
tool Calculator {
    description: "执行数学计算",
    parameters: {
        "expression": "string"
    }
}
```
**错误**: 可能不支持 tool 定义
**原因**: 需要验证 tool 语法是否完整

**修复优先级**: 中
**修复方案**: 验证并完善 tool 定义语法

#### 2.12 result.name 属性访问
**文档示例**:
```nexa
print(result.name)
print(result.age)
```
**错误**: 可能不支持属性访问
**原因**: 需要验证成员访问语法

**修复优先级**: 高
**修复方案**: 验证并完善成员访问语法

## 修复计划

### Phase 1: 核心语法修复 (优先级: 高)

1. **修复 AST 转换层**
   - 创建 `ast_transformer.py` 将 Lark Tree 转换为字典
   - 确保所有现有语法正常工作

2. **添加整数属性值支持**
   - 词法分析器添加 INTEGER_LITERAL
   - 语法分析器属性值支持整数类型

3. **添加 fallback 语法支持**
   - 数组元素支持 `fallback:` 前缀
   - 代码生成器处理 fallback 逻辑

4. **添加 flow 参数支持**
   - flow 定义支持参数列表
   - 函数调用时传递参数

5. **添加 print 语句支持**
   - flow 体支持 print 语句
   - 代码生成器生成 print 调用

6. **添加标准库调用支持**
   - 表达式支持 `std.xxx.method()` 语法
   - 代码生成器生成正确的标准库调用

### Phase 2: 高级语法修复 (优先级: 中)

7. **添加 match intent 支持**
   - match 表达式语法规则
   - intent 模式匹配

8. **添加 DAG 操作符支持**
   - 词法分析器添加 |>>, &>>, ?? 
   - 语法分析器添加 DAG 表达式

9. **添加 loop until 支持**
   - loop 语句语法规则
   - until 条件判断

10. **添加 semantic_if 支持**
    - semantic_if 表达式语法规则
    - 语义条件评估

11. **添加 try/catch 支持**
    - try/catch 语句语法规则
    - 错误处理代码生成

### Phase 3: 验证与测试

12. **运行所有测试**
    - 单元测试
    - 集成测试
    - 文档示例测试

13. **修复发现的问题**

14. **提交代码**

## 下一步

1. 创建 AST 转换器 (`src/ast_transformer.py`)
2. 修复词法分析器添加缺失的 token
3. 修复语法分析器添加缺失的规则
4. 修复代码生成器处理新语法
5. 运行测试验证修复