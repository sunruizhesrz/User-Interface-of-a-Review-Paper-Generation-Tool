"""
app.py - 综述论文生成工具 Gradio Web 界面
成员 F：用户交互界面 + 系统集成
Sprint 2 版本：
  - F-02: 完善界面：年份滑块、文献数量、语言选择、大纲确认面板
  - F-04: 错误处理：所有后端异常友好提示，不崩溃
  - F-05: 历史记录：侧边栏展示最近 5 次生成记录
"""

import gradio as gr
import json
import time
import threading
import queue
from pathlib import Path

# 导入 Sprint 2 真实模块（防御性导入兜底）
try:
    from pipeline import start_generation_phase1, resume_generation_phase2
    from exporter import export
    from history import save_history, load_history
    USE_MOCK = False
except ImportError as e:
    print(f"[WARN] 部分模块未就绪，降级为 Mock 模式：{e}")
    USE_MOCK = True

    # ── Mock 实现（降级兜底）──────────────────────────────
    def start_generation_phase1(topic, year_from, max_papers, language, on_progress=None):
        """Mock：模拟阶段一（检索→解析→大纲生成）"""
        steps = [
            ("search",  "🔍 正在检索论文（arXiv / Semantic Scholar）..."),
            ("download","📥 正在异步下载 PDF..."),
            ("parse",   "📄 正在解析 PDF 并分块向量化..."),
            ("outline", "📝 正在规划综述大纲（LangGraph 中断点）..."),
        ]
        for step_id, msg in steps:
            if on_progress:
                on_progress(step_id, msg)
            time.sleep(0.4)
        mock_outline = {
            "title": f"{topic} 综述",
            "sections": [
                {"id": 1, "title": "引言", "points": ["研究背景", "研究意义", "论文结构"]},
                {"id": 2, "title": "相关工作", "points": ["早期方法", "深度学习方法", "最新进展"]},
                {"id": 3, "title": "核心技术分析", "points": ["方法对比", "性能评估"]},
                {"id": 4, "title": "挑战与展望", "points": ["当前挑战", "未来方向"]},
                {"id": 5, "title": "结论", "points": ["总结"]},
            ]
        }
        return {"status": "outline_ready", "outline": mock_outline, "error": None}

    def resume_generation_phase2(confirmed_outline_json, on_progress=None):
        """Mock：模拟阶段二（逐章生成→引用校验→整合输出）"""
        steps = [
            ("generate", "✍️ 正在逐章生成综述内容..."),
            ("verify",   "🔗 正在校验引用准确性..."),
            ("finalize", "🎉 正在整合最终文稿..."),
        ]
        for step_id, msg in steps:
            if on_progress:
                on_progress(step_id, msg)
            time.sleep(0.5)

        outline = confirmed_outline_json if isinstance(confirmed_outline_json, dict) else json.loads(confirmed_outline_json)
        sections = outline.get("sections", [])
        title = outline.get("title", "综述")

        md_lines = [f"# {title}\n\n---\n\n## 目录\n"]
        for sec in sections:
            md_lines.append(f"- {sec['id']}. {sec['title']}")
        md_lines.append("\n---\n")
        for sec in sections:
            md_lines.append(f"\n## {sec['id']}. {sec['title']}\n")
            for pt in sec.get("points", []):
                md_lines.append(
                    f"\n### {pt}\n\n"
                    f"本节讨论关于 **{pt}** 的核心内容。"
                    f"相关研究表明，该方向近年取得了显著进展 [1][2]。\n"
                )
        md_lines.append("\n---\n\n## 参考文献\n\n[1] Mock Author et al. *Mock Paper Title*, 2023.\n[2] Mock Author B. *Another Paper*, 2022.\n")
        return {"status": "success", "content": "\n".join(md_lines), "error": None}

    def export(content, fmt="md", output_dir="./output", filename="survey"):
        out = Path(output_dir) / f"{filename}.{fmt}"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        return str(out.resolve())

    def save_history(topic, result_path, timestamp):
        pass

    def load_history(limit=5):
        return []


# ============================================================
# 全局状态（线程安全）
# ============================================================
_current_content = {"value": ""}  # 存储最新生成内容供导出使用


# ============================================================
# 阶段一：检索 + 解析 + 大纲生成（生成器，用于流式日志）
# ============================================================
def phase1_with_progress(topic, year_from, max_papers, language):
    """
    生成器：返回 (日志文本, 进度HTML, 大纲JSON字符串, 大纲面板visible, 生成按钮interactive)
    """
    if not topic.strip():
        yield "❌ 请输入研究主题！", _progress_html(0, "❌ 输入错误"), "{}", gr.update(visible=False), gr.update(interactive=True)
        return

    msg_queue = queue.Queue()
    result_holder = {}

    def worker():
        try:
            def cb(step, msg):
                msg_queue.put(("progress", step, msg))
            res = start_generation_phase1(topic, int(year_from), int(max_papers), language, on_progress=cb)
            result_holder["result"] = res
            msg_queue.put(("done", None, None))
        except Exception as e:
            msg_queue.put(("error", None, str(e)))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    logs = []
    step_count = 0
    total_steps = 4

    while True:
        try:
            item = msg_queue.get(timeout=0.5)
        except queue.Empty:
            yield "\n".join(logs), _progress_html(int(step_count / total_steps * 50)), "{}", gr.update(visible=False), gr.update(interactive=False)
            continue

        if item[0] == "progress":
            _, step, msg = item
            step_count += 1
            logs.append(f"[{step.upper()}] {msg}")
            pct = int(step_count / total_steps * 50)
            yield "\n".join(logs), _progress_html(pct, msg[:25]), "{}", gr.update(visible=False), gr.update(interactive=False)

        elif item[0] == "done":
            res = result_holder.get("result", {})
            if res.get("status") == "outline_ready":
                outline_str = json.dumps(res["outline"], ensure_ascii=False, indent=2)
                logs.append("✅ 大纲生成完毕，请在右侧确认或修改大纲后继续。")
                yield "\n".join(logs), _progress_html(50, "等待大纲确认..."), outline_str, gr.update(visible=True), gr.update(interactive=True)
            else:
                err = res.get("error", "未知错误")
                logs.append(f"❌ 阶段一失败：{err}")
                yield "\n".join(logs), _progress_html(0, "❌ 失败"), "{}", gr.update(visible=False), gr.update(interactive=True)
            break

        elif item[0] == "error":
            logs.append(f"❌ 线程异常：{item[2]}")
            yield "\n".join(logs), _progress_html(0, "⚠️ 异常"), "{}", gr.update(visible=False), gr.update(interactive=True)
            break


# ============================================================
# 阶段二：用户确认大纲后继续生成（生成器）
# ============================================================
def phase2_with_progress(outline_text, topic):
    """
    生成器：返回 (日志追加文本, 进度HTML, 综述内容Markdown, 大纲面板visible, 下载按钮interactive)
    """
    try:
        confirmed_outline = json.loads(outline_text)
    except json.JSONDecodeError:
        yield "❌ 大纲格式错误，无法解析 JSON。", _progress_html(50, "❌ 大纲格式错误"), "", gr.update(visible=True), gr.update(interactive=False)
        return

    msg_queue = queue.Queue()
    result_holder = {}

    def worker():
        try:
            def cb(step, msg):
                msg_queue.put(("progress", step, msg))
            res = resume_generation_phase2(confirmed_outline, on_progress=cb)
            result_holder["result"] = res
            msg_queue.put(("done", None, None))
        except Exception as e:
            msg_queue.put(("error", None, str(e)))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    logs = ["[PHASE2] 用户已确认大纲，开始逐章生成..."]
    step_count = 0
    total_steps = 3

    while True:
        try:
            item = msg_queue.get(timeout=0.5)
        except queue.Empty:
            pct = 50 + int(step_count / total_steps * 50)
            yield "\n".join(logs), _progress_html(pct), "", gr.update(visible=True), gr.update(interactive=False)
            continue

        if item[0] == "progress":
            _, step, msg = item
            step_count += 1
            logs.append(f"[{step.upper()}] {msg}")
            pct = 50 + int(step_count / total_steps * 50)
            yield "\n".join(logs), _progress_html(pct, msg[:25]), "", gr.update(visible=True), gr.update(interactive=False)

        elif item[0] == "done":
            res = result_holder.get("result", {})
            if res.get("status") == "success":
                content = res["content"]
                _current_content["value"] = content
                logs.append("✅ 综述生成完成！")
                # 保存历史
                import datetime
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                out_path = Path("./output") / f"survey_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                out_path.parent.mkdir(exist_ok=True)
                out_path.write_text(content, encoding="utf-8")
                save_history(topic, str(out_path), ts)
                yield "\n".join(logs), _progress_html(100, "✅ 完成！"), content, gr.update(visible=False), gr.update(interactive=True)
            else:
                err = res.get("error", "未知错误")
                logs.append(f"❌ 阶段二失败：{err}")
                yield "\n".join(logs), _progress_html(50, "❌ 失败"), "", gr.update(visible=True), gr.update(interactive=True)
            break

        elif item[0] == "error":
            logs.append(f"❌ 线程异常：{item[2]}")
            yield "\n".join(logs), _progress_html(50, "⚠️ 异常"), "", gr.update(visible=True), gr.update(interactive=True)
            break


# ============================================================
# 工具函数
# ============================================================
def _progress_html(pct: int, status: str = "") -> str:
    pct = max(0, min(100, pct))
    color = "#ef4444" if pct == 0 and status.startswith("❌") else "linear-gradient(90deg,#2b9c8c,#5ee0cf)"
    status_label = status if status else f"{pct}%"
    return f"""
<div class="preset-progress">
  <div class="preset-progress-label">
    <span>📊 生成进度</span><span>{status_label}</span>
  </div>
  <div class="preset-progress-bar-bg">
    <div class="preset-progress-bar-fill" style="width:{pct}%;background:{color};"></div>
  </div>
</div>"""


def do_export(fmt: str, content: str):
    """导出综述为指定格式，返回文件路径供 gr.File 下载"""
    if not content or content.strip() == "*生成结果将在此处预览...*":
        gr.Warning("⚠️ 没有可导出的内容，请先生成综述。")
        return None
    try:
        out_path = export(content, fmt=fmt, output_dir="./output", filename="survey")
        gr.Info(f"✅ 导出成功：{Path(out_path).name}")
        return out_path
    except Exception as e:
        gr.Error(f"❌ 导出失败：{e}")
        return None


def get_history_html():
    """生成历史记录 HTML（供侧边栏展示）"""
    records = load_history(limit=5)
    if not records:
        return "<p style='color:#aaa;font-size:0.8rem;'>暂无历史记录</p>"
    items = "".join(
        f"<div class='hist-item'>"
        f"<div class='hist-topic'>📄 {r.get('topic','')[:20]}</div>"
        f"<div class='hist-time'>{r.get('timestamp','')}</div>"
        f"</div>"
        for r in records
    )
    return f"<div class='hist-list'>{items}</div>"


# ============================================================
# CSS
# ============================================================
CUSTOM_CSS = """
body {
    font-family: 'Inter','Segoe UI',system-ui,-apple-system,sans-serif;
    background: linear-gradient(135deg,#e0f2fe 0%,#f0f9ff 50%,#fef9e3 100%);
    min-height: 100vh;
}
.gradio-container {
    background: rgba(255,255,255,0.75)!important;
    backdrop-filter: blur(12px);
    border-radius: 2rem;
    box-shadow: 0 20px 35px rgba(0,0,0,0.05),0 0 0 1px rgba(255,255,255,0.8);
    padding: 1.5rem!important;
}
.gr-column { overflow:visible!important; min-height:500px!important; }
.card,.gr-box,.gr-form,.panel {
    background: rgba(255,255,255,0.85)!important;
    backdrop-filter: blur(4px);
    border-radius: 1.25rem!important;
    border: 1px solid rgba(255,255,255,0.9)!important;
    box-shadow: 0 8px 20px rgba(0,0,0,0.03);
    position: relative!important;
    overflow: visible!important;
}
.main-title {
    text-align:center; font-size:2rem; font-weight:700;
    background: linear-gradient(120deg,#0b7e6b,#2b9c8c);
    -webkit-background-clip:text; background-clip:text; color:transparent;
}
.sub-title {
    text-align:center; color:#2c7a6e!important; font-size:0.9rem;
    margin: 0 auto 1.2em auto; padding-bottom:0.5em;
}
input,textarea,select {
    background:rgba(255,255,255,0.9)!important;
    border:1px solid #cbd5e1!important; border-radius:1rem!important; color:#1e293b!important;
}
.gr-button-primary {
    background:linear-gradient(95deg,#2b9c8c,#1e7a6b)!important;
    border:none!important; border-radius:2rem!important;
    padding:0.65rem 1.5rem!important; font-weight:600!important; color:white!important;
}
.gr-button-primary:hover { transform:translateY(-2px); box-shadow:0 8px 18px rgba(43,156,140,0.3); }
.gr-button-secondary {
    background:rgba(241,245,249,0.9)!important;
    border:1px solid #cbd5e1!important; border-radius:2rem!important;
}
.gr-textbox textarea {
    font-family:'JetBrains Mono',monospace; font-size:0.85rem;
    background:#f8fafc!important; color:#0f172a!important; border-radius:1rem;
}
.preset-progress { margin-bottom:16px; }
.preset-progress-label {
    display:flex; justify-content:space-between;
    font-size:0.8rem; color:#2c7a6e; margin-bottom:6px; font-weight:500;
}
.preset-progress-bar-bg {
    background-color:#e2e8f0; border-radius:20px; height:10px; overflow:hidden;
}
.preset-progress-bar-fill {
    width:0%; background:linear-gradient(90deg,#2b9c8c,#5ee0cf);
    height:100%; border-radius:20px; transition:width 0.3s ease;
}
.gr-dropdown { position:relative!important; z-index:999999!important; }
/* 历史记录 */
.hist-list { display:flex; flex-direction:column; gap:6px; margin-top:8px; }
.hist-item {
    background:rgba(255,255,255,0.85); border-radius:0.8rem;
    padding:8px 12px; border:1px solid #e2e8f0; cursor:pointer;
}
.hist-item:hover { background:rgba(43,156,140,0.08); border-color:#2b9c8c; }
.hist-topic { font-size:0.82rem; font-weight:600; color:#1e293b; }
.hist-time { font-size:0.72rem; color:#94a3b8; margin-top:2px; }
/* 大纲确认面板 */
.outline-panel {
    border:2px solid #2b9c8c!important; border-radius:1.25rem!important;
    background:rgba(43,156,140,0.04)!important; padding:1rem!important;
}
.tech-badge {
    background:rgba(241,245,249,0.9); border-radius:30px; padding:4px 12px;
    font-size:0.75rem; color:#2c7a6e; border:1px solid #cbd5e1;
}
"""

# ============================================================
# Gradio 界面
# ============================================================
with gr.Blocks(
    title="综述论文生成工具 | Sprint 2",
    theme=gr.themes.Soft(),
    css=CUSTOM_CSS,
) as demo:

    # ── 欢迎弹窗（Sprint 2）───────────────────────────────
    gr.HTML("""
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/sweetalert2@11/dist/sweetalert2.min.css">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script>
    window.addEventListener('load', function() {
        Swal.fire({
            title: '📚 综述论文自动生成工具',
            html: `<div style="text-align:left">
              <p><strong>🆕 Sprint 2 更新</strong><br>
              • 大纲确认交互（两阶段生成流程）<br>
              • 完整 PDF / Word 导出<br>
              • 历史记录侧边栏<br>
              • 全链路真实后端对接（防御性降级兜底）</p>
              <p><strong>⚙️ 技术栈</strong><br>
              Gradio · LangGraph · ChromaDB · BM25 + 向量混合检索 · DeepSeek API</p>
            </div>`,
            icon: 'info',
            confirmButtonText: '开始使用',
            confirmButtonColor: '#2b9c8c',
            background: '#ffffff',
            backdrop: 'rgba(0,0,0,0.3)',
            width: '580px',
        });
    });
    </script>
    """)

    gr.HTML("""
    <div class="main-title">📚 综述论文自动生成工具 ✨</div>
    <div class="sub-title">基于 LangGraph + RAG 的学术综述自动撰写系统 | Sprint 2 · 两阶段生成 · 大纲确认</div>
    """)

    with gr.Row():
        # ── 左侧：参数 + 历史记录 ────────────────────────
        with gr.Column(scale=1, elem_classes="card"):
            gr.Markdown("### 🧪 输入参数")
            topic_input = gr.Textbox(
                label="🔍 研究主题",
                placeholder="例如：大型语言模型在自然语言处理中的应用",
                lines=2,
            )
            with gr.Row():
                year_slider = gr.Slider(
                    minimum=2010, maximum=2025, value=2020, step=1,
                    label="📅 起始年份"
                )
                paper_count = gr.Dropdown(
                    choices=[5, 10, 20, 30],
                    value=10,
                    label="📑 文献数量"
                )
            language_select = gr.Dropdown(
                choices=["中文", "English", "中英双语"],
                value="中文",
                label="🌐 综述语言"
            )
            generate_btn = gr.Button("🚀 开始检索与大纲生成", variant="primary", size="lg")

            gr.Markdown("---")
            gr.Markdown("### 📂 历史记录")
            history_html = gr.HTML(value=get_history_html())
            refresh_hist_btn = gr.Button("🔄 刷新历史", size="sm", elem_classes="gr-button-secondary")

        # ── 右侧：进度、大纲确认、结果 ──────────────────
        with gr.Column(scale=2, elem_classes="card"):
            gr.Markdown("### ⚙️ 执行进度")
            preset_progress = gr.HTML(_progress_html(0, "待命中"))
            log_output = gr.Textbox(
                label="📋 运行日志",
                lines=6,
                interactive=False,
                placeholder="点击「开始检索与大纲生成」后，此处将显示执行状态...",
            )

            # 大纲确认面板（初始隐藏）
            with gr.Group(visible=False, elem_classes="outline-panel") as outline_panel:
                gr.Markdown("### 📋 大纲确认（可直接修改 JSON 后点击确认）")
                outline_display = gr.Code(
                    label="系统建议大纲（JSON）",
                    language="json",
                    lines=12,
                    interactive=True,
                )
                confirm_btn = gr.Button("✅ 确认大纲，开始生成综述", variant="primary")

            gr.Markdown("### 📄 综述预览")
            content_output = gr.Markdown(value="*大纲确认后，生成内容将在此处预览...*")

            with gr.Row():
                download_md_btn  = gr.Button("⬇ 下载 Markdown", size="sm", elem_classes="gr-button-secondary")
                download_pdf_btn = gr.Button("⬇ 下载 PDF",      size="sm", elem_classes="gr-button-secondary")
                download_doc_btn = gr.Button("⬇ 下载 Word",     size="sm", elem_classes="gr-button-secondary")
            download_file = gr.File(label="📁 点击下载文件", visible=False)

    # 示例
    gr.Markdown("### 💡 快速示例（点击即可填充）")
    gr.Examples(
        examples=[
            ["大型语言模型（LLM）综述", 2022, 10, "中文"],
            ["Retrieval-Augmented Generation", 2021, 10, "English"],
            ["图神经网络在分子生物学中的应用", 2020, 10, "中英双语"],
        ],
        inputs=[topic_input, year_slider, paper_count, language_select],
        label="✨ 热门主题",
    )

    gr.HTML("""
    <div style="text-align:center;margin-top:1.5rem;">
        <span class="tech-badge">⚙️ Gradio 4.x</span>
        <span class="tech-badge">🕸️ LangGraph</span>
        <span class="tech-badge">🗃️ ChromaDB + BM25</span>
        <span class="tech-badge">📄 PyMuPDF</span>
        <span class="tech-badge">🧠 DeepSeek API</span>
        <br><br>
        <span style="font-size:0.75rem;color:#aaa;">Sprint 2 | 两阶段生成 | 大纲确认 | 完整导出</span>
    </div>
    """)

    # ── 事件绑定 ──────────────────────────────────────────

    # 阶段一：检索 → 解析 → 大纲
    generate_btn.click(
        fn=phase1_with_progress,
        inputs=[topic_input, year_slider, paper_count, language_select],
        outputs=[log_output, preset_progress, outline_display, outline_panel, generate_btn],
        show_progress="hidden",
    )

    # 阶段二：确认大纲 → 生成综述
    confirm_btn.click(
        fn=phase2_with_progress,
        inputs=[outline_display, topic_input],
        outputs=[log_output, preset_progress, content_output, outline_panel, generate_btn],
        show_progress="hidden",
    )

    # 导出按钮
    def _export_and_show(fmt, content):
        path = do_export(fmt, content)
        if path:
            return gr.update(visible=True, value=path)
        return gr.update(visible=False)

    download_md_btn.click(
        fn=lambda c: _export_and_show("md", c),
        inputs=[content_output],
        outputs=[download_file],
    )
    download_pdf_btn.click(
        fn=lambda c: _export_and_show("pdf", c),
        inputs=[content_output],
        outputs=[download_file],
    )
    download_doc_btn.click(
        fn=lambda c: _export_and_show("docx", c),
        inputs=[content_output],
        outputs=[download_file],
    )

    # 刷新历史
    refresh_hist_btn.click(fn=get_history_html, outputs=[history_html])


def launch_app():
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, show_error=True, inbrowser=True)


if __name__ == "__main__":
    launch_app()
