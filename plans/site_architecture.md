# Nexa Language — 官方网站架构规划

## 1. 审美方向

**参考**: Google DeepMind、Apple、Tesla、Stripe、Vercel 等顶级科技公司主页

**核心设计语言**: "深空科技感" (Deep Space Tech)

| 维度 | 设计决策 |
|------|---------|
| **主色调** | 深空黑 `#0a0a1a` → 深蓝 `#0d1117`，渐变过渡 |
| **强调色** | 电光紫 `#6c5ce7` → 霓虹蓝 `#00d4ff`，用于 CTA 和交互 |
| **文字色** | 纯白 `#ffffff` 主标题，`#a0a0b8` 正文，`#6c5ce7` 链接 |
| **卡片** | 玻璃态 (glassmorphism): `rgba(255,255,255,0.03)` + `backdrop-filter: blur(20px)` + 1px 半透明边框 |
| **字体** | Inter (正文) + JetBrains Mono (代码) + Space Grotesk (标题) |
| **动效** | Canvas 粒子星场背景 + GSAP ScrollTrigger 滚动揭示 + 微交互 hover 发光 |
| **氛围** | 科技感、未来感、但不冰冷——有温暖的紫色光晕 |

## 2. 目录结构

```
site/
├── .github/workflows/deploy.yml    # GitHub Actions → GitHub Pages
├── CNAME                            # www.nexa-lang.com
├── index.html                       # 进站主页
├── blog/
│   ├── index.html                   # Blog 列表 (Twitter 时间线风格)
│   ├── 2026-01-conception.html      # 1月: 概念提出
│   ├── 2026-02-implementation.html  # 2月: 开始实现
│   ├── 2026-03-opensource.html      # 3月: 正式开源
│   ├── 2026-04-ecosystem.html       # 4月: 生态扩展
│   └── 2026-05-harness.html         # 5月: Harness Native v2.0
├── css/
│   └── style.css                    # 全局样式 (单一文件，~800行)
├── js/
│   └── main.js                      # 全局脚本 (粒子 + 滚动 + 导航)
└── assets/
    └── (复用 docs/img/ 中的 logo)
```

## 3. 页面设计

### 3.1 进站主页 (index.html)

**Hero 区** (全屏，首屏):
- Canvas 粒子星场背景 (150+ 粒子，缓慢漂移 + 鼠标交互)
- 中央: Nexa Logo (SVG) + "The Dawn of Agent-Native Programming" 标语
- 副标题: "Write flows, not glue code. The first Harness Native Programming Language."
- CTA 按钮: "Get Started" → GitHub / "Read Docs" → 文档
- 向下滚动指示器 (脉冲箭头)

**特性区** (滚动揭示):
- 6 张玻璃态卡片，3x2 网格
- 每张卡片: 图标 + 标题 + 描述
- 内容: Agent-Native Syntax / Harness Built-in / DAG Orchestration / Type Safety / 1500+ Tests / AVM Runtime

**代码演示区**:
- 左右分栏: 左侧 Nexa 代码 (语法高亮)，右侧等价 Python 代码
- 自动切换动画展示不同场景 (Hello World → Pipeline → Agent Loop)

**架构图区**:
- 简化的三层架构图 (Language Frontend → Compiler → Runtime)
- 使用 CSS 动画展示数据流

**CTA 区**:
- 大标题 "Ready to Build the Future of Agents?"
- GitHub Star 按钮 + "pip install nexa" 命令复制

**Footer**:
- Logo + 链接 (GitHub / Docs / Blog / License)
- "Made with ❤️ by the Nexa Team" 

### 3.2 Blog 列表页 (blog/index.html)

**Twitter 风格时间线**:
- 左侧竖线 + 时间节点圆点
- 每篇 Blog 卡片: 日期、标题、摘要、标签
- 点击进入详情页
- 顶部: "Nexa Blog" 标题 + "Changelog & Updates" 副标题

### 3.3 Blog 详情页 (5篇)

| 文件 | 日期 | 标题 | 内容要点 |
|------|------|------|---------|
| `2026-01-conception.html` | 2026.01.15 | The Birth of Nexa — Why the World Needs an Agent-Native Language | 痛点分析、LangChain 局限、设计哲学 |
| `2026-02-implementation.html` | 2026.02.20 | From Zero to MVP — Building the First Transpiler | Lark Parser、AST Transformer、Code Generator |
| `2026-03-opensource.html` | 2026.03.10 | Nexa Goes Open Source — v0.9-alpha Release | AGPL-3.0、GitHub 开源、社区反馈 |
| `2026-04-ecosystem.html` | 2026.04.23 | v1.3.7 Milestone — 16 Features, 1500+ Tests | 特性总览、类型系统、DbC、并发 |
| `2026-05-harness.html` | 2026.05.06 | Introducing Harness Native — The v2.0 Vision | Harness 六元组、语言原语、编译器验证 |

## 4. 技术实现

### 4.1 纯静态方案 (无框架依赖)

- **HTML**: 语义化 HTML5，单文件每页
- **CSS**: 单一 `style.css`，CSS Variables + CSS Grid/Flexbox + `@keyframes`
- **JS**: 单一 `main.js`，Vanilla JS (无 jQuery)
  - Canvas 粒子系统 (~150行)
  - Intersection Observer 滚动揭示
  - 平滑导航 + 移动端汉堡菜单
- **代码高亮**: Prism.js (CDN，仅代码演示区加载)
- **字体**: Google Fonts (Inter + JetBrains Mono + Space Grotesk)

### 4.2 GitHub Actions 部署

```yaml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
    paths:
      - 'site/**'
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./site
          cname: www.nexa-lang.com
```

### 4.3 性能目标

- Lighthouse Score: 95+ (Performance/Accessibility/Best Practices/SEO)
- 首屏加载: <1.5s (纯静态，无框架)
- 粒子系统: 60fps (requestAnimationFrame)
- 移动端: 完全响应式，粒子降级为 CSS 渐变

## 5. 实施步骤

1. 创建 `site/` 目录结构
2. 编写 `.github/workflows/deploy.yml`
3. 编写 `CNAME` 文件
4. 编写 `css/style.css` (全局样式系统)
5. 编写 `js/main.js` (粒子 + 滚动 + 导航)
6. 编写 `index.html` (主页)
7. 编写 `blog/index.html` (Blog 列表)
8. 编写 5 篇 Blog 详情页
9. 本地预览验证
10. 推送到 GitHub，触发 Actions 部署