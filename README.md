# 综述论文自动生成工具 — 用户交互界面与系统集成模块

基于 **LangGraph + RAG** 技术栈的学术综述自动撰写系统的用户界面层与系统集成层。用户通过 Web 界面输入研究主题，系统自动完成论文检索、文本解析、知识入库、大纲规划和逐章综述撰写，最终输出结构完整的学术综述文档，并支持 Markdown / PDF / Word 三格式导出。

---

## 目录

- [项目简介](#项目简介)
- [Sprint 2 新增功能](#sprint-2-新增功能)
- [文件结构](#文件结构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [界面功能](#界面功能)
- [模块说明](#模块说明)
- [系统流程](#系统流程)
- [版本路线图](#版本路线图)
- [相关文档](#相关文档)
- [Sprint 2 验收状态](#sprint-2-验收状态)

---

## 项目简介

本仓库为综述论文自动生成工具的**成员 F 产出**，负责系统的"门面"与"粘合剂"两个关键角色：

- **用户交互界面（`app.py`）**：基于 Gradio Blocks API 构建的响应式 Web 界面，Sprint 2 升级为**两阶段生成架构**，支持大纲人机确认、实时进度反馈、综述预览、多格式下载和历史记录侧边栏。
- **系统集成层（`pipeline.py`）**：串联各成员模块（C→D→B→A→E）的主流程脚本，Sprint 2 重构为两阶段函数，与 LangGraph interrupt 节点配合；采用"防御性导入 + Mock 兜底"设计，确保在其他成员模块未就绪时仍可独立运行演示。
- **多格式导出模块（`exporter.py`）**：Sprint 2 实现真实的 PDF（reportlab + 中文字体自动注册）和 Word（python-docx）导出。
- **历史记录模块（`history.py`）**：Sprint 2 新增，持久化保存最近 50 条生成记录，供侧边栏展示最近 5 条。

**当前版本（Sprint 2）** 已完成全链路真实后端接入与联调，具备大纲确认交互和完整导出功能。

---

## Sprint 2 新增功能

相较于 Sprint 1（界面演示版本），Sprint 2 完成了以下升级：

| 功能点 | Sprint 1 | Sprint 2 |
|--------|---------|---------|
| 生成流程 | 单一 `run_pipeline()` Mock 演示 | 两阶段架构（检索+大纲 / 确认+逐章生成） |
| 大纲确认 | 无 | 可编辑 JSON 大纲面板，人机协同确认 |
| PDF 导出 | 框架占位 | reportlab 真实导出，支持中文字体 |
| Word 导出 | 框架占位 | python-docx，支持标题层级、粗斜体 |
| 历史记录 | 无 | 侧边栏展示最近 5 条，持久化 JSON 存储 |
| 全链路联调 | 未进行 | 接口对齐会议，解决 4 个集成问题 |

---

## 文件结构

```
成员F产出/
│
├── app.py              # Gradio Web 界面主程序（两阶段生成 + 大纲确认）
├── pipeline.py         # 主流程串联脚本（两阶段：start_phase1 / resume_phase2）
├── exporter.py         # 多格式导出模块（Markdown / PDF / Word，中文字体支持）
├── history.py          # 历史记录模块（持久化 JSON，最多 50 条）
│
├── output/             # 生成产物目录（.md / .pdf / .docx + history.json）
└── README.md           # 本文件
```

> **说明**：以下文件由其他成员负责，Sprint 2 阶段已完成真实接口联调，Mock 兜底保留：
> `graph.py`（成员 A）、`rag_engine.py`（成员 B）、`paper_fetcher.py`（成员 C）、
> `pdf_parser.py` / `embedder.py`（成员 D）、`generator.py` / `prompts.py`（成员 E）

---

## 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Web UI | [Gradio](https://gradio.app/) >= 4.x | Blocks API，原生支持生成器流式进度 |
| 工作流编排 | [LangGraph](https://github.com/langchain-ai/langgraph) >= 0.2 | 基于图的 ReAct 智能体编排，支持 interrupt 中断点 |
| 向量数据库 | [ChromaDB](https://www.trychroma.com/) | 本地向量存储与混合检索（BM25 + 向量） |
| PDF 解析 | [PyMuPDF](https://pymupdf.readthedocs.io/) | 高性能 PDF 文本提取 |
| Embedding | OpenAI / HuggingFace (`all-MiniLM-L6-v2`) | 文本向量化 |
| LLM 生成 | [DeepSeek API](https://platform.deepseek.com/) | 章节内容生成 |
| PDF 导出 | pandoc（优先）/ [reportlab](https://www.reportlab.com/)（fallback） | 双重方案，自动注册系统中文字体 |
| Word 导出 | [python-docx](https://python-docx.readthedocs.io/) >= 1.1 | 标题层级、粗体、斜体、首行缩进 |
| 数据校验 | [pydantic](https://docs.pydantic.dev/) >= 2.0 | 跨模块数据结构校验 |

---

## 快速开始

### 环境要求

- Python >= 3.10
- 内存建议 8GB 以上
- 网络需可访问 arXiv / Semantic Scholar（部分功能需代理）

### 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows PowerShell

# 安装依赖
pip install -r requirements.txt
```

### 启动 Web 界面

```bash
python app.py
```

启动成功后，浏览器将自动打开 `http://localhost:7860`。

### 命令行模式（阶段一）

```bash
# 仅执行检索 + 大纲生成（阶段一）
python pipeline.py "大型语言模型" --year 2022 --papers 15 --lang 中文
```

---

## 界面功能

### 界面布局

```
┌────────────────────────────────────────────────────────────────┐
│           📚 综述论文自动生成工具  (标题栏)                        │
├──────────────────────┬─────────────────────────────────────────┤
│   【左侧：输入 + 历史】  │        【右侧：进度 + 输出】               │
│                      │                                         │
│  研究主题输入框          │  动态进度条（0 → 50% → 100%）            │
│  起始年份滑块            │  运行日志（实时流式状态）                  │
│  文献数量下拉            │                                         │
│  综述语言 Radio 选择     │  ┌─ 大纲确认面板（阶段一完成后出现）─┐      │
│                      │  │  可编辑 JSON 大纲                  │      │
│  [🚀 开始检索与大纲生成]  │  │  [✅ 确认大纲，开始生成综述]      │      │
│                      │  └────────────────────────────────────┘      │
│  ── 历史记录 ──        │  综述预览（Markdown 渲染）               │
│  📄 最近生成主题 1       │                                         │
│  📄 最近生成主题 2       │  [⬇ 下载MD] [⬇ 下载PDF] [⬇ 下载Word]   │
│  [刷新历史]             │                                         │
├──────────────────────┴─────────────────────────────────────────┤
│  💡 快速示例（点击即可填充参数）                                     │
└────────────────────────────────────────────────────────────────┘
```

### 主要功能

| 功能 | 描述 |
|------|------|
| 研究主题输入 | 支持中英文自由输入，带 placeholder 示例引导 |
| 参数配置 | 起始年份（2010—2025）、文献数量（5/10/20/30）、综述语言（中文/English/中英双语） |
| 两阶段生成 | 阶段一：检索+解析+大纲；大纲确认后进入阶段二：逐章生成 |
| 大纲确认面板 | 展示结构化 JSON 大纲，支持用户直接编辑后确认，保障结构控制权 |
| 实时进度反馈 | 动态进度条（线程+队列非阻塞）+ 逐步滚动运行日志 |
| 综述预览 | Markdown 格式实时渲染，结构清晰 |
| 多格式导出 | 一键导出 `.md` / `.pdf` / `.docx`，PDF 支持中文，Word 含标题层级 |
| 历史记录侧边栏 | 展示最近 5 条生成记录，可手动刷新 |
| 快速示例 | 内置 3 个热门主题示例，一键填充参数 |
| 欢迎弹窗 | 页面加载时展示 Sprint 2 更新说明 |
| 友好错误处理 | 所有异常通过 `gr.Error/Warning` 提示，界面不崩溃 |

---

## 模块说明

### app.py — Web 界面主程序

基于 Gradio Blocks API 构建，Sprint 2 核心采用**两阶段生成器架构**，线程+队列实现非阻塞流式进度：

```python
# 阶段一：检索 → 解析 → 大纲生成
def phase1_with_progress(topic, year_from, max_papers, language):
    """生成器：实时推送进度；阶段一完毕后使大纲面板可见"""
    msg_queue = queue.Queue()
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    while True:
        item = msg_queue.get(timeout=0.5)
        if item[0] == "progress":
            yield logs, progress_html, "{}", gr.update(visible=False), ...
        elif item[0] == "done":
            yield logs, progress_html, outline_json, gr.update(visible=True), ...
            break

# 阶段二：用户确认大纲 → 逐章生成
def phase2_with_progress(outline_text, topic):
    """生成器：从大纲 JSON 解析并继续逐章生成，输出完整 Markdown"""
```

当 `pipeline.py` / `exporter.py` / `history.py` 导入失败时，自动切换内置 Mock 模式，界面始终可演示。

### pipeline.py — 主流程串联脚本

Sprint 2 重构为两阶段函数，与 LangGraph interrupt 节点配合，采用**防御性导入**模式：

```
start_generation_phase1(topic, year_from, max_papers, language, on_progress)
    ├── [Step 1-2] get_pdf_paths()       # 成员 C：检索 + 异步下载
    ├── [Step 3-4] parse_and_embed()     # 成员 D：解析 + 向量化
    └── [Step 5]   plan_outline_step()   # 成员 A：LangGraph 至 interrupt 节点
             │ 返回 outline JSON（暂停，等待用户确认）
             ▼
resume_generation_phase2(confirmed_outline, on_progress)
    ├── run_survey_generation_resume()   # 成员 A：从中断点继续
    │       ├── retrieve()              # 成员 B：BM25 + 向量混合检索
    │       └── generate_section()     # 成员 E：DeepSeek 真实生成
    └── _assemble_markdown()            # 整合为完整文稿
```

每步均有 `on_progress` 回调，实时向界面推送状态进度。

### exporter.py — 多格式导出模块

采用**策略模式**，统一 `export()` 接口分发至对应格式处理器：

```python
from exporter import export

# Markdown 导出
export(content, fmt="md",   output_dir="./output", filename="survey")
# Word 导出（标题层级 + 粗体/斜体 + 首行缩进）
export(content, fmt="docx", output_dir="./output", filename="survey")
# PDF 导出（pandoc 优先，reportlab 兜底，中文字体自动注册）
export(content, fmt="pdf",  output_dir="./output", filename="survey")
```

**PDF 中文字体处理**：自动检测系统字体（Windows `msyh.ttc`/`simsun.ttc`，macOS `PingFang.ttc`），通过 `TTFont` 注册到 reportlab，所有样式指定该字体名。

**Word 内联 Markdown 处理**：正则解析 `**粗体**`、`*斜体*`、`` `代码` ``，转为 python-docx run 格式。

### history.py — 历史记录模块

```python
# 持久化写入（最新排最前，超出 MAX_RECORDS=50 自动截断）
save_history(topic, result_path, timestamp)

# 加载最近 N 条供侧边栏展示（默认 limit=5）
records = load_history(limit=5)
```

历史数据保存在 `./output/history.json`，格式为 JSON 数组，每条包含 `topic`、`path`、`timestamp` 三个字段。

---

## 系统流程

完整的综述生成系统由 6 个成员模块构成，Sprint 2 已实现全链路联调：

```
数据获取 (C) → 数据处理 (D) → 知识入库 (B) → 智能规划 (A) + 内容生成 (E) → 界面集成 (F)
```

成员 F 负责最终的界面呈现和全链路串联，是整个系统的集成出口；Sprint 2 中还主导了跨成员接口对齐会议，解决了 4 个集成问题。

---

## 版本路线图

| 版本 | Sprint | 主要功能 |
|------|--------|---------|
| v0.1 | Sprint 1 | Gradio 界面框架，Mock 模式演示，主流程骨架，多格式导出框架 |
| v0.2（当前） | Sprint 2 | 两阶段生成架构，大纲确认交互，真实 PDF/Word 导出，历史记录，全链路联调 |
| v0.3 | Sprint 3 | 引用悬浮预览，多主题对比生成，增量更新已有综述 |
| v1.0 | Sprint 4 | LaTeX 导出，生产环境部署，用户认证，多租户支持 |
