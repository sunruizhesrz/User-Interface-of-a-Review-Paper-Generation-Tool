# 综述论文自动生成工具 — 用户交互界面与系统集成模块

> **成员 F 产出 | Sprint 1 | 软件项目管理课程第三次作业**

基于 **LangGraph + RAG** 技术栈的学术综述自动撰写系统的用户界面层与系统集成层。用户只需在 Web 界面输入研究主题，系统将自动完成论文检索、文本解析、知识入库、大纲规划和综述撰写全流程，最终输出结构完整的学术综述文档。

---

## 目录

- [项目简介](#项目简介)
- [文件结构](#文件结构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [界面功能](#界面功能)
- [模块说明](#模块说明)
- [系统流程](#系统流程)
- [版本路线图](#版本路线图)
- [相关文档](#相关文档)

---

## 项目简介

本仓库为综述论文自动生成工具的**成员 F 产出**，负责系统的"门面"与"粘合剂"两个关键角色：

- **用户交互界面（`app.py`）**：基于 Gradio Blocks API 构建的响应式 Web 界面，支持参数输入、实时进度反馈、综述预览和多格式下载。
- **系统集成层（`pipeline.py`）**：串联各成员模块（C→D→B→A→E）的主流程脚本，采用"防御性导入 + Mock 兜底"设计，确保在其他成员模块未就绪时仍可独立运行演示。
- **多格式导出模块（`exporter.py`）**：支持将综述内容导出为 Markdown / PDF / Word 三种格式。

**当前版本（Sprint 1）** 为界面演示版本，核心功能以 Mock 模式运行，后续 Sprint 将逐步接入真实后端模块。

---

## 文件结构

```
User-Interface-of-a-Review-Paper-Generation-Tool/
│
├── app.py              # Gradio Web 界面主程序（成员 F 核心产出）
├── pipeline.py         # 主流程串联脚本（C→D→B→A→E 全链路）
├── exporter.py         # 多格式导出模块（Markdown / PDF / Word）
│
├── 用户操作手册.md      # 完整用户操作文档
├── 作业3_报告.md        # Sprint 1 个人提交报告（设计分析 + 风险矩阵）
├── requirements.txt    # Python 依赖包列表
└── README.md           # 本文件
```

> **说明**：以下文件由其他成员负责，Sprint 1 阶段通过 Mock 函数占位：
> `graph.py`（成员 A）、`rag_engine.py`（成员 B）、`paper_fetcher.py`（成员 C）、
> `pdf_parser.py` / `embedder.py`（成员 D）、`generator.py` / `prompts.py`（成员 E）

---

## 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Web UI | [Gradio](https://gradio.app/) >= 4.x | 快速构建 ML 应用界面，原生支持进度流和 Markdown 渲染 |
| 工作流编排 | [LangGraph](https://github.com/langchain-ai/langgraph) | 基于图的 ReAct 智能体编排框架 |
| 向量数据库 | [ChromaDB](https://www.trychroma.com/) | 本地向量存储与检索 |
| PDF 解析 | [PyMuPDF](https://pymupdf.readthedocs.io/) | 高性能 PDF 文本提取 |
| Embedding | OpenAI / HuggingFace (`all-MiniLM-L6-v2`) | 文本向量化 |
| PDF 导出 | pandoc / [reportlab](https://www.reportlab.com/) | 双重 fallback PDF 生成方案 |
| Word 导出 | [python-docx](https://python-docx.readthedocs.io/) | Word 文档生成 |

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

启动成功后，访问 `http://localhost:7860` 即可打开界面。

### 命令行模式

```bash
# 基础用法
python pipeline.py "大型语言模型"

# 完整参数
python pipeline.py "大型语言模型" --year 2022 --papers 15 --lang 中文 --output my_survey.md
```

---

## 界面功能

### 界面布局

```
┌────────────────────────────────────────────────────────────┐
│           📚 综述论文自动生成工具  (标题栏)                    │
├─────────────────────┬──────────────────────────────────────┤
│   【输入参数区】       │          【输出区】                    │
│                     │                                      │
│  研究主题输入框        │  动态进度条                           │
│  起始年份滑块          │  运行日志（实时状态文字）               │
│  最大文献数量滑块       │                                      │
│  综述语言下拉菜单       │  综述预览（Markdown 渲染）             │
│                     │                                      │
│  [🚀 开始生成综述]     │  [下载MD] [下载PDF] [下载Word]          │
├─────────────────────┴──────────────────────────────────────┤
│  快速示例（点击可自动填入示例参数）                              │
└────────────────────────────────────────────────────────────┘
```

### 主要功能

| 功能 | 描述 |
|------|------|
| 研究主题输入 | 支持中英文自由输入，带 placeholder 示例引导 |
| 参数配置 | 起始年份（2010—2025）、文献数量（5—50）、综述语言（中文/英文/双语） |
| 实时进度反馈 | 动态进度条 + 运行日志，7 步流程逐步展示 |
| 综述预览 | Markdown 格式实时渲染，结构清晰 |
| 多格式导出 | 一键导出 `.md` / `.pdf` / `.docx` |
| 快速示例 | 内置 3 个热门主题示例，一键填充参数 |
| 欢迎弹窗 | 页面加载时展示项目介绍和功能说明 |

---

## 模块说明

### app.py — Web 界面主程序

基于 Gradio Blocks API 构建，核心采用 **线程 + 队列** 架构实现非阻塞实时进度更新：

```python
# 生成器函数：实时推送进度
def run_pipeline_with_progress(topic, year_from, max_papers, language):
    msg_queue = queue.Queue()
    thread = threading.Thread(target=worker)
    thread.start()
    while True:
        item = msg_queue.get()
        if item[0] == "progress":
            yield current_log, progress_html, ""
        elif item[0] == "done":
            yield log, final_progress, final_content
            break
```

当 `pipeline.py` / `exporter.py` 导入失败时，自动切换为内置 Mock 模式，确保界面始终可演示。

### pipeline.py — 主流程串联脚本

串联 C → D → B → A → E 完整数据流，采用**防御性导入**模式：

```
run_pipeline(topic, year_from, max_papers, language)
    │
    ├── [Step 1] search_arxiv()          # 成员 C：检索论文元数据
    ├── [Step 2] download_pdf()          # 成员 C：下载 PDF 全文
    ├── [Step 3] parse_pdf()             # 成员 D：PDF 文本提取
    ├── [Step 4] embed_chunks()          # 成员 D：文本向量化
    ├── [Step 5] add_documents()         # 成员 B：写入 ChromaDB
    ├── [Step 6] run_survey_generation() # 成员 A：LangGraph 编排
    │               ├── retrieve()       # 成员 B：RAG 检索
    │               └── generate_section() # 成员 E：章节生成
    └── 整合 Markdown → 返回结果字典
```

每步均有 `on_progress` 回调，实时向界面推送状态。

### exporter.py — 多格式导出模块

采用**策略模式**，统一 `export()` 接口分发至对应格式处理器：

```python
from exporter import export

# Markdown 导出
export(content, fmt="md", output_dir="./output", filename="survey")

# Word 导出
export(content, fmt="docx", output_dir="./output", filename="survey")

# PDF 导出（pandoc 优先，reportlab 兜底）
export(content, fmt="pdf", output_dir="./output", filename="survey")
```

---

## 系统流程

完整的综述生成系统由 6 个成员模块构成，依赖链为：

```
数据获取 (C) → 数据处理 (D) → 知识入库 (B) → 智能规划 (A) + 内容生成 (E) → 界面集成 (F)
```

成员 F 负责最终的界面呈现和全链路串联，是整个系统的集成出口。

---

## 版本路线图

| 版本 | Sprint | 主要功能 |
|------|--------|---------|
| v0.1（当前） | Sprint 1 | Gradio 界面框架，Mock 模式演示，主流程骨架，多格式导出框架 |
| v0.2 | Sprint 2 | 真实后端接入（C+D+B+A+E），完整导出功能，错误处理完善 |
| v0.3 | Sprint 3 | 性能优化，大纲人机协同确认，历史记录功能 |
| v1.0 | Sprint 4 | 生产环境部署，用户认证，多租户支持 |

---

## 相关文档

- [用户操作手册](./用户操作手册.md) — 完整的安装、启动、使用和排错指南
- [Sprint 1 个人报告](./作业3_报告.md) — 设计方法、技术原理、风险矩阵和验收自检

---

## Sprint 1 验收状态

| 验收条件 | 状态 |
|---------|------|
| Gradio 界面可正常启动 | ✅ 完成 |
| 主题输入框可交互 | ✅ 完成 |
| "开始生成"按钮可点击并触发 Mock 流程 | ✅ 完成 |
| 界面实时显示执行状态（动态进度条 + 日志） | ✅ 完成 |
| 界面显示"完成"状态 | ✅ 完成 |
| `pipeline.py` 可独立命令行运行 | ✅ 完成 |
| `exporter.py` Markdown 导出功能 | ✅ 完成 |

---

*成员 F 产出 | 软件项目管理课程 | Sprint 1 | 2026 年 4 月*
