# Nexa Website v2 Redesign Plan

## 改动清单

### ① 全局命名统一
- 所有 "Agent-Native Programming Language" → "Harness Native Agent Language"
- 所有 "agent-native" → "harness-native" (在描述性文字中)
- 涉及: `site/index.html`, `site/blog/*.html`, `README.md`, `README_EN.md`

### ② 架构图修复
- 5 个框用 `flex-wrap: nowrap` + `min-width` 防止换行
- 每个框加 SVG 图标 (📄→🔍→🌳→🛡️→⚡)
- 框内加小示意图 (CSS 伪元素或内联 SVG)

### ③ 论文按钮
- 顶栏 Paper 链接 → `https://doi.org/10.5281/zenodo.19994263`
- Hero 区或 CTA 区加一个 Paper 按钮

### ④ 顶栏重构
```
[Logo] Home ▾  Blog  Paper  GitHub  Docs  Nexa⁺
         ├─ Features
         ├─ Code  
         └─ Architecture
```
- Home 下拉: Features / Code / Architecture (锚点)
- Docs → https://docs.nexa-lang.com/en/
- Nexa⁺ 右上角小字，hover 展开生态面板

### ⑤ Nexa⁺ 下拉面板
- 全宽下拉面板，玻璃态背景
- 6 个产品卡片: Docs / SkCC / evobench / epicontext / Org / Author
- 每个卡片: 图标 + 名称 + 简短描述 + 外链

### ⑥ 底栏扩展
- 4 列布局: Product / Ecosystem / Resources / Contact
- Product: Home, Features, Architecture, Blog
- Ecosystem: Docs, SkCC, evobench, epicontext
- Resources: GitHub, Paper, Org, Author
- Contact: nexa-lang@proton.me + copyright

### ⑦ Blog 重构
- 主体: Twitter 风格卡片列表 (大卡片，左头像右内容)
- 顶部: 搜索框 + 排序下拉 (Newest / Oldest)
- 右侧或底部: 迷你时间线 (保留但缩小)
- 每个卡片可点击进入详情

### ⑧ Hero 重构
- 左右分栏 (flex row)
- 左 (50%): Logo + Badge + 标题 + 副标题 + CTA 按钮 + pip install 行
- 右 (50%): 代码块 (深色终端风格) + 3 条彩色标注线指向关键语法
  - 标注1 → `autoloop` "Harness E: 编译期验证退出条件"
  - 标注2 → `context_policy` "Harness C: 自动上下文管理"
  - 标注3 → `try_agent` "Harness L: AI 原生错误自愈"
- 代码块下方: `pip install nexa` 复制框

## 实施顺序
1. CSS 大改 (顶栏下拉、Nexa⁺面板、Hero 左右布局、架构图、底栏、Blog 卡片)
2. JS 增强 (下拉交互、搜索排序)
3. index.html 重写 Hero + 架构图 + 底栏
4. blog/index.html 重写为 Twitter 卡片风格
5. 全局命名替换