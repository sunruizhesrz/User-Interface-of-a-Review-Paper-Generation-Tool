"""
app.py - 综述论文生成工具 Gradio Web 界面
集成 pipeline.py + exporter.py，动态进度条，真实流程，加载时弹出欢迎弹窗
下拉框溢出问题已修复
"""

import gradio as gr
import time
import threading
import queue
from pathlib import Path

# 导入真实模块
try:
    from pipeline import run_pipeline
    from exporter import export
    USE_MOCK = False
except ImportError as e:
    print(f"导入真实模块失败：{e}，将使用 Mock 模式。")
    USE_MOCK = True
    # Mock 模式：手动模拟步骤
    STEPS = [
        ("search", "🔍 正在检索论文（调用 arXiv / Semantic Scholar）..."),
        ("parse",  "📄 正在解析 PDF 并提取文本块..."),
        ("index",  "🧠 正在向量化并写入知识库（ChromaDB）..."),
        ("plan",   "📝 正在规划综述大纲..."),
        ("generate", "✍️ 正在逐章生成综述内容..."),
        ("verify",  "✅ 正在校验引用准确性..."),
        ("finalize", "🎉 正在整合输出，生成最终文稿..."),
    ]

    def mock_run_pipeline(topic, year_from, max_papers, language, on_progress=None):
        import random
        total = len(STEPS)
        for idx, (step_id, msg) in enumerate(STEPS):
            if on_progress:
                on_progress(step_id, msg)
            time.sleep(random.uniform(0.4, 0.8))
        final_content = f"# {topic} 综述（Mock）\n\n这是 Mock 生成的综述内容。\n\n---\n*Mock 模式*"
        return {
            "status": "success",
            "content": final_content,
            "outline": ["Introduction", "Conclusion"],
            "papers": [],
            "error": None
        }

    def mock_export(content, fmt, output_dir, filename):
        output_path = Path(output_dir) / f"{filename}.{fmt}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return str(output_path)


# ============================================================
# 生成器函数：使用线程 + 队列实现动态进度条
# ============================================================

def run_pipeline_with_progress(topic, year_from, max_papers, language):
    """
    生成器：实时返回 (日志文本, 进度条HTML, 最终内容)
    """
    if not topic.strip():
        error_log = "❌ 请输入研究主题！"
        error_progress = """
        <div class="preset-progress">
            <div class="preset-progress-label">
                <span>📊 生成进度</span>
                <span>❌ 输入错误</span>
            </div>
            <div class="preset-progress-bar-bg">
                <div class="preset-progress-bar-fill" style="width: 0%; background: #ef4444;"></div>
            </div>
        </div>
        """
        yield error_log, error_progress, ""
        return

    msg_queue = queue.Queue()
    result_holder = {}

    def worker():
        try:
            def progress_callback(step: str, msg: str):
                msg_queue.put(("progress", step, msg))

            if USE_MOCK:
                res = mock_run_pipeline(topic, year_from, max_papers, language, on_progress=progress_callback)
            else:
                res = run_pipeline(
                    topic=topic,
                    year_from=year_from,
                    max_papers=max_papers,
                    language=language,
                    on_progress=progress_callback
                )
            result_holder["result"] = res
            msg_queue.put(("done", None, None))
        except Exception as e:
            msg_queue.put(("error", None, str(e)))

    thread = threading.Thread(target=worker)
    thread.start()

    log_messages = []
    total_steps = 7
    current_step = 0

    while True:
        try:
            item = msg_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        if item[0] == "progress":
            _, step, msg = item
            log_messages.append(f"[{step.upper()}] {msg}")
            current_log = "\n".join(log_messages)

            current_step += 1
            percent = min(int(current_step / total_steps * 100), 100) if total_steps > 0 else 0
            status_text = msg[:20]

            progress_html = f"""
            <div class="preset-progress">
                <div class="preset-progress-label">
                    <span>📊 生成进度</span>
                    <span>{percent}% - {status_text}</span>
                </div>
                <div class="preset-progress-bar-bg">
                    <div class="preset-progress-bar-fill" style="width: {percent}%;"></div>
                </div>
            </div>
            """
            yield current_log, progress_html, ""

        elif item[0] == "done":
            result = result_holder.get("result")
            if result and result["status"] == "success":
                final_content = result["content"]
                final_progress = """
                <div class="preset-progress">
                    <div class="preset-progress-label">
                        <span>📊 生成进度</span>
                        <span>100% - ✅ 完成！</span>
                    </div>
                    <div class="preset-progress-bar-bg">
                        <div class="preset-progress-bar-fill" style="width: 100%;"></div>
                    </div>
                </div>
                """
                log_messages.append("✅ 综述生成完成！")
                yield "\n".join(log_messages), final_progress, final_content
            else:
                error_msg = result.get("error", "未知错误") if result else "进程异常"
                error_progress = f"""
                <div class="preset-progress">
                    <div class="preset-progress-label">
                        <span>📊 生成进度</span>
                        <span>❌ 失败</span>
                    </div>
                    <div class="preset-progress-bar-bg">
                        <div class="preset-progress-bar-fill" style="width: 0%; background: #ef4444;"></div>
                    </div>
                </div>
                """
                log_messages.append(f"❌ 生成失败：{error_msg}")
                yield "\n".join(log_messages), error_progress, ""
            break

        elif item[0] == "error":
            _, _, err_str = item
            error_progress = f"""
            <div class="preset-progress">
                <div class="preset-progress-label">
                    <span>📊 生成进度</span>
                    <span>⚠️ 异常</span>
                </div>
                <div class="preset-progress-bar-bg">
                    <div class="preset-progress-bar-fill" style="width: 0%; background: #ef4444;"></div>
                </div>
            </div>
            """
            log_messages.append(f"❌ 线程异常：{err_str}")
            yield "\n".join(log_messages), error_progress, ""
            break


# ============================================================
# 修复后的 CSS（解决下拉框乱跑）
# ============================================================
CUSTOM_CSS = """
/* 全局 */
body {
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #fef9e3 100%);
    min-height: 100vh;
    margin: 0;
    padding: 0;
}

.gradio-container {
    background: rgba(255, 255, 255, 0.75) !important;
    backdrop-filter: blur(12px);
    border-radius: 2rem;
    box-shadow: 0 20px 35px rgba(0, 0, 0, 0.05), 0 0 0 1px rgba(255,255,255,0.8);
    padding: 1.5rem !important;
}

/* 左侧卡片高度足够，防止下拉框向上弹 */
.gr-column {
    overflow: visible !important;
    min-height: 500px !important;
}

.card, .gr-box, .gr-form, .panel {
    background: rgba(255, 255, 255, 0.85) !important;
    backdrop-filter: blur(4px);
    border-radius: 1.25rem !important;
    border: 1px solid rgba(255,255,255,0.9) !important;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.03);
    transition: all 0.25s ease;
    position: relative !important;
    overflow: visible !important;
}

/* 标题 */
.main-title {
    text-align: center;
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(120deg, #0b7e6b, #2b9c8c);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    letter-spacing: -0.01em;
    margin-bottom: 0.2em;
    animation: titleGlow 2s ease-in-out infinite alternate;
}
@keyframes titleGlow {
    0% { text-shadow: 0 0 2px rgba(43,156,140,0.2); }
    100% { text-shadow: 0 0 12px rgba(43,156,140,0.4); }
}

.sub-title {
    text-align: center;
    color: #2c7a6e !important;
    font-size: 0.9rem;
    border-bottom: 1px dashed rgba(11,126,107,0.3);
    display: inline-block;
    width: auto;
    margin: 0 auto 1.2em auto;
    padding-bottom: 0.5em;
}

/* 输入框 */
input, textarea, select {
    background: rgba(255, 255, 255, 0.9) !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 1rem !important;
    color: #1e293b !important;
}
input:focus, textarea:focus, select:focus {
    border-color: #2b9c8c !important;
    box-shadow: 0 0 0 3px rgba(43,156,140,0.2) !important;
    outline: none;
}

/* 按钮 */
.gr-button-primary {
    background: linear-gradient(95deg, #2b9c8c, #1e7a6b) !important;
    border: none !important;
    border-radius: 2rem !important;
    padding: 0.65rem 1.5rem !important;
    font-weight: 600 !important;
    color: white !important;
}
.gr-button-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 18px rgba(43,156,140,0.3);
}
.gr-button-secondary {
    background: rgba(241,245,249,0.9) !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 2rem !important;
}

/* 日志 */
.gr-textbox textarea {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    background: #f8fafc !important;
    color: #0f172a !important;
    border-radius: 1rem;
}

/* 进度条 */
.preset-progress {
    margin-bottom: 16px;
}
.preset-progress-label {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: #2c7a6e;
    margin-bottom: 6px;
    font-weight: 500;
}
.preset-progress-bar-bg {
    background-color: #e2e8f0;
    border-radius: 20px;
    height: 10px;
    overflow: hidden;
}
.preset-progress-bar-fill {
    width: 0%;
    background: linear-gradient(90deg, #2b9c8c, #5ee0cf);
    height: 100%;
    border-radius: 20px;
    transition: width 0.3s ease;
}

.gr-dropdown {
    position: relative !important;
    z-index: 999999 !important;
}

ul.options.svelte-y6qw75 {
    position: relative !important;
    bottom: auto !important;
    top: 100% !important;
    left: 0 !important;
    margin-top: 4px !important;
    z-index: 999999 !important;
    background: white !important;
    border-radius: 0.8rem !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
}

/* 底部标签 */
.tech-badge {
    background: rgba(241,245,249,0.9);
    border-radius: 30px;
    padding: 4px 12px;
    font-size: 0.75rem;
    color: #2c7a6e;
    border: 1px solid #cbd5e1;
}
"""

# ============================================================
# 界面
# ============================================================
with gr.Blocks(
    title="综述论文生成工具 | 智能学术助手",
    theme=gr.themes.Soft(),
    css=CUSTOM_CSS,
) as demo:
    gr.HTML("""
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/sweetalert2@11/dist/sweetalert2.min.css">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script>
    window.addEventListener('load', function() {
        Swal.fire({
            title: '📚 欢迎使用综述论文自动生成工具',
            html: `
                <div style="text-align: left;">
                    <p><strong>✨ 项目简介</strong><br>
                    基于 <strong>LangGraph + RAG</strong> 的学术综述自动撰写系统，自动完成文献检索、知识入库、大纲规划、内容生成全流程。</p>
                    <p><strong>🚀 核心功能</strong><br>
                    • 智能论文检索（arXiv / Semantic Scholar）<br>
                    • PDF 解析与向量化存储<br>
                    • ReAct 智能体规划综述大纲<br>
                    • RAG 增强生成，引用可溯源<br>
                    • 支持导出 Markdown / PDF / Word</p>
                    <p><strong>⚙️ 技术栈</strong><br>
                    Gradio · LangGraph · ChromaDB · PyMuPDF · OpenAI / HuggingFace Embedding</p>
                    <p><strong>📌 当前版本</strong><br>
                    Sprint 1 演示版（界面就绪，后端逐步接入中）</p>
                </div>
            `,
            icon: 'info',
            confirmButtonText: '开始使用',
            confirmButtonColor: '#2b9c8c',
            background: '#ffffff',
            backdrop: 'rgba(0,0,0,0.3)',
            width: '600px',
        });
    });
    </script>
    """)

    gr.HTML("""
    <div class="main-title">
        📚 综述论文自动生成工具 ✨
    </div>
    <div class="sub-title">
        基于 LangGraph + RAG 的学术综述自动撰写系统 | 动态进度条 | 真实流程
    </div>
    """)

    with gr.Row():
        with gr.Column(scale=1, elem_classes="card"):
            gr.Markdown("### 🧪 输入参数")
            topic_input = gr.Textbox(
                label="🔍 研究主题",
                placeholder="例如：大型语言模型在自然语言处理中的应用",
                lines=2,
                info="输入任何你感兴趣的学术领域"
            )
            with gr.Row():
                year_slider = gr.Slider(
                    minimum=2010, maximum=2025, value=2020, step=1,
                    label="📅 起始年份", info="仅检索该年份之后发表的论文"
                )
                paper_count = gr.Slider(
                    minimum=5, maximum=50, value=20, step=5,
                    label="📑 最大文献数量", info="检索并处理的论文数量上限"
                )
            language_select = gr.Dropdown(
                choices=["中文", "English", "中英双语"],
                value="中文",
                label="🌐 综述语言",
                info="生成综述的语言格式"
            )
            generate_btn = gr.Button("🚀 开始生成综述", variant="primary", size="lg")

        with gr.Column(scale=2, elem_classes="card"):
            gr.Markdown("### ⚙️ 执行进度")
            preset_progress = gr.HTML("""
            <div class="preset-progress">
                <div class="preset-progress-label">
                    <span>📊 生成进度</span>
                    <span>待命中</span>
                </div>
                <div class="preset-progress-bar-bg">
                    <div class="preset-progress-bar-fill" style="width: 0%;"></div>
                </div>
            </div>
            """)
            log_output = gr.Textbox(
                label="📋 运行日志",
                lines=8,
                interactive=False,
                placeholder="点击「开始生成综述」后，此处将显示各步骤执行状态..."
            )
            gr.Markdown("### 📄 综述预览")
            content_output = gr.Markdown(
                value="*生成结果将在此处预览...*",
                label="综述内容（Markdown 格式）"
            )
            with gr.Row():
                download_md = gr.Button("⬇ 下载 Markdown", size="sm", elem_classes="gr-button-secondary")
                download_pdf = gr.Button("⬇ 下载 PDF", size="sm", elem_classes="gr-button-secondary")
                download_docx = gr.Button("⬇ 下载 Word", size="sm", elem_classes="gr-button-secondary")

    gr.Markdown("### 💡 快速示例（点击即可填充）")
    gr.Examples(
        examples=[
            ["大型语言模型（LLM）综述", 2022, 20, "中文"],
            ["Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", 2021, 15, "English"],
            ["图神经网络在分子生物学中的应用", 2020, 30, "中英双语"],
        ],
        inputs=[topic_input, year_slider, paper_count, language_select],
        label="✨ 试试这些热门主题"
    )

    gr.HTML("""
    <div style="text-align: center; margin-top: 1.5rem;">
        <span class="tech-badge">⚙️ Gradio</span>
        <span class="tech-badge">🕸️ LangGraph</span>
        <span class="tech-badge">🗃️ ChromaDB</span>
        <span class="tech-badge">📄 PyMuPDF</span>
        <span class="tech-badge">🧠 OpenAI / HF Embedding</span>
        <br><br>
        <span style="font-size:0.75rem; color:#aaa;">✨ 动态进度条 | 实时日志 | 一键生成综述 ✨</span>
    </div>
    """)

    # 生成事件
    def on_generate(topic, year_from, max_papers, language):
        yield from run_pipeline_with_progress(topic, year_from, max_papers, language)

    generate_btn.click(
        fn=on_generate,
        inputs=[topic_input, year_slider, paper_count, language_select],
        outputs=[log_output, preset_progress, content_output],
        show_progress="full"
    )

    # 导出
    def do_export(fmt, content_markdown):
        if not content_markdown or content_markdown == "*生成结果将在此处预览...*":
            gr.Info("⚠️ 没有可导出的内容，请先生成综述。")
            return
        try:
            if USE_MOCK:
                out_path = mock_export(content_markdown, fmt, "./output", f"survey_{fmt}")
            else:
                out_path = export(content_markdown, fmt=fmt, output_dir="./output", filename="survey")
            gr.Info(f"✅ 导出成功：{out_path}")
        except Exception as e:
            gr.Error(f"❌ 导出失败：{str(e)}")

    download_md.click(lambda c: do_export("md", c), inputs=[content_output])
    download_pdf.click(lambda c: do_export("pdf", c), inputs=[content_output])
    download_docx.click(lambda c: do_export("docx", c), inputs=[content_output])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, show_error=True, inbrowser=True)