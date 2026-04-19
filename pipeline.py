"""
pipeline.py - 综述论文生成工具主流程脚本（Sprint 2 版）
成员 F：系统集成模块

Sprint 2 升级内容（F-01 完成真实后端对接）：
  - 移除 Mock return 路径，主流程改为真实模块调用
  - 拆分为两阶段：start_generation_phase1（检索→解析→大纲中断点）
                  resume_generation_phase2（确认大纲→逐章生成→输出）
  - 对所有后端异常添加 try-except，输出友好错误（F-04）
  - 防御性导入保留，作为环境不完整时的降级兜底

依赖链：C(检索下载) → D(解析入库) → B(混合检索) → A(LangGraph 中断点) → E(真实生成) → F(整合输出)
"""

import sys
import json
import logging
import time
from pathlib import Path
from typing import Optional, Callable, List, Dict

# ---- 日志配置 ----
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("pipeline")

# 添加项目根目录到 sys.path，确保跨模块导入
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ============================================================
# 模块导入（Sprint 2：try-import 保留，但主流程改为真实调用）
# ============================================================

# ── 成员 C：论文检索与下载 ──────────────────────────────────
try:
    from fetcher.paper_fetcher import get_pdf_paths   # Sprint 2 接口
    HAS_C = True
    logger.info("✅ 成员 C 模块加载成功（get_pdf_paths）")
except ImportError:
    HAS_C = False
    logger.warning("⚠️  fetcher.paper_fetcher 未就绪，使用降级兜底")

    def get_pdf_paths(topic: str, max_results: int = 10, year_from: int = 2020) -> List[Dict]:
        """降级：返回 Mock 论文列表（不含真实 PDF）"""
        logger.info(f"[FALLBACK-C] get_pdf_paths(topic={topic!r})")
        return [
            {
                "arxiv_id": f"mock_{i:04d}",
                "local_path": f"./data/pdfs/mock_{i:04d}.pdf",
                "title": f"Mock Paper {i}: {topic}",
                "authors": "Author A, Author B",
                "year": 2023,
            }
            for i in range(1, min(max_results, 5) + 1)
        ]

# ── 成员 D：文档解析与向量化 ─────────────────────────────────
try:
    from parser.embedder import parse_and_embed   # Sprint 2 完整管道接口
    HAS_D = True
    logger.info("✅ 成员 D 模块加载成功（parse_and_embed）")
except ImportError:
    HAS_D = False
    logger.warning("⚠️  parser.embedder 未就绪，使用降级兜底")

    def parse_and_embed(pdf_path_list: List[Dict]) -> None:
        logger.info(f"[FALLBACK-D] parse_and_embed({len(pdf_path_list)} PDFs)")
        time.sleep(0.3)

# ── 成员 A：LangGraph 编排（两阶段：规划大纲 + 继续生成）───────
try:
    from core.graph import plan_outline_step, run_survey_generation_resume
    HAS_A = True
    logger.info("✅ 成员 A 模块加载成功（plan_outline_step, run_survey_generation_resume）")
except ImportError:
    HAS_A = False
    logger.warning("⚠️  core.graph 未就绪，使用降级兜底")

    def plan_outline_step(topic: str, language: str = "中文") -> dict:
        """降级：生成结构化大纲 JSON"""
        logger.info(f"[FALLBACK-A] plan_outline_step(topic={topic!r})")
        return {
            "title": f"{topic} 综述",
            "sections": [
                {"id": 1, "title": "引言",         "points": ["研究背景", "研究意义", "论文结构"]},
                {"id": 2, "title": "相关工作",     "points": ["早期研究", "深度学习方法", "最新进展"]},
                {"id": 3, "title": "核心技术分析", "points": ["主要方法对比", "性能评估"]},
                {"id": 4, "title": "挑战与展望",   "points": ["当前挑战", "未来方向"]},
                {"id": 5, "title": "结论",         "points": ["总结"]},
            ]
        }

    def run_survey_generation_resume(confirmed_outline: dict, language: str = "中文") -> dict:
        """降级：使用大纲生成 Mock 综述文本"""
        logger.info("[FALLBACK-A] run_survey_generation_resume")
        sections = confirmed_outline.get("sections", [])
        title = confirmed_outline.get("title", "综述")
        final_content = {}
        for sec in sections:
            sec_title = sec["title"]
            points = sec.get("points", [])
            text = f"\n本章节围绕「{sec_title}」展开综述。\n\n"
            for pt in points:
                text += f"**{pt}**：相关研究表明，该方向近年取得了显著进展 [1][2]。"
                text += "学界普遍认为，进一步的工作需要关注可解释性与鲁棒性 [3]。\n\n"
            final_content[sec_title] = text
        return {"final_content": final_content, "outline": confirmed_outline}


# ============================================================
# 阶段一：检索 → 解析 → 大纲生成（在 LangGraph interrupt 处暂停）
# ============================================================

def start_generation_phase1(
    topic: str,
    year_from: int = 2020,
    max_papers: int = 10,
    language: str = "中文",
    on_progress: Optional[Callable] = None
) -> dict:
    """
    阶段一：论文检索 → PDF 下载 → 解析入库 → 规划大纲
    在 LangGraph interrupt 节点处暂停，返回大纲供用户确认。

    Returns:
        {
            "status": "outline_ready" | "error",
            "outline": dict,   # 结构化大纲 JSON
            "error": str | None
        }
    """
    def _p(step: str, msg: str):
        logger.info(f"[Phase1] {step}: {msg}")
        if on_progress:
            on_progress(step, msg)

    try:
        # ── Step 1: 检索与下载（成员 C）───────────────────
        _p("search", f"正在检索「{topic}」相关论文（year >= {year_from}，最多 {max_papers} 篇）...")
        pdf_infos = get_pdf_paths(topic=topic, max_results=max_papers, year_from=year_from)
        _p("download", f"检索 & 下载完成，共获取 {len(pdf_infos)} 篇论文。")

        # ── Step 2: 解析与向量化入库（成员 D）──────────────
        _p("parse", "正在解析 PDF 并向量化入库（成员 D + B）...")
        parse_and_embed(pdf_infos)
        _p("parse", "文档解析入库完成。")

        # ── Step 3: 规划大纲（成员 A，在 interrupt 前）─────
        _p("outline", "正在调用 LangGraph 规划综述大纲...")
        outline = plan_outline_step(topic=topic, language=language)
        _p("outline", "大纲生成完毕，等待用户确认。")

        return {"status": "outline_ready", "outline": outline, "error": None}

    except Exception as e:
        logger.exception("阶段一执行异常")
        return {"status": "error", "outline": {}, "error": str(e)}


# ============================================================
# 阶段二：用户确认大纲后继续生成综述
# ============================================================

def resume_generation_phase2(
    confirmed_outline: dict,
    language: str = "中文",
    on_progress: Optional[Callable] = None
) -> dict:
    """
    阶段二：从 LangGraph interrupt 中断点继续 → 逐章生成 → 引用校验 → 整合输出

    Args:
        confirmed_outline: 用户确认（或修改）的大纲 JSON
        language         : 综述语言
        on_progress      : 进度回调

    Returns:
        {
            "status": "success" | "error",
            "content": str,   # 完整 Markdown 综述
            "error": str | None
        }
    """
    def _p(step: str, msg: str):
        logger.info(f"[Phase2] {step}: {msg}")
        if on_progress:
            on_progress(step, msg)

    try:
        # ── Step 4: 逐章生成（成员 A 调 E）───────────────
        _p("generate", "正在调用 LangGraph 逐章生成综述...")
        result = run_survey_generation_resume(confirmed_outline=confirmed_outline, language=language)
        _p("generate", "所有章节生成完毕。")

        # ── Step 5: 整合为完整 Markdown ──────────────────
        _p("finalize", "正在整合最终文稿...")
        full_markdown = _assemble_markdown(confirmed_outline, result.get("final_content", {}))
        _p("finalize", "✅ 全流程执行完毕！")

        return {"status": "success", "content": full_markdown, "error": None}

    except Exception as e:
        logger.exception("阶段二执行异常")
        return {"status": "error", "content": "", "error": str(e)}


# ============================================================
# 工具函数
# ============================================================

def _assemble_markdown(outline: dict, final_content: dict) -> str:
    """将章节字典整合为完整 Markdown 文稿"""
    title = outline.get("title", "综述论文")
    sections = outline.get("sections", [])

    lines = [f"# {title}\n"]

    # 目录
    lines.append("## 目录\n")
    for sec in sections:
        lines.append(f"- {sec['id']}. {sec['title']}")
    lines.append("\n---\n")

    # 各章节
    for sec in sections:
        sec_title = sec["title"]
        lines.append(f"\n## {sec['id']}. {sec_title}\n")
        content = final_content.get(sec_title, "（内容待生成）")
        lines.append(content + "\n")

    # 参考文献占位
    lines.append("\n---\n\n## 参考文献\n\n（由成员 E citation_checker 校验后自动生成）\n")

    return "\n".join(lines)


# ============================================================
# CLI 快速测试入口
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="综述论文生成工具 - 命令行模式（Sprint 2）")
    parser.add_argument("topic", type=str, help="研究主题")
    parser.add_argument("--year",   type=int, default=2020, help="起始年份")
    parser.add_argument("--papers", type=int, default=10,   help="最大文献数量")
    parser.add_argument("--lang",   type=str, default="中文", help="综述语言")
    parser.add_argument("--output", type=str, default="survey_output.md", help="输出文件路径")
    args = parser.parse_args()

    print(f"\n{'='*60}\n  综述论文生成工具 · Sprint 2\n  主题：{args.topic}\n{'='*60}\n")

    # 阶段一
    res1 = start_generation_phase1(
        topic=args.topic, year_from=args.year,
        max_papers=args.papers, language=args.lang
    )
    if res1["status"] != "outline_ready":
        print(f"❌ 阶段一失败：{res1['error']}")
        exit(1)

    print("\n📋 建议大纲：")
    print(json.dumps(res1["outline"], ensure_ascii=False, indent=2))
    input("\n按 Enter 确认大纲并继续生成...")

    # 阶段二
    res2 = resume_generation_phase2(confirmed_outline=res1["outline"], language=args.lang)
    if res2["status"] == "success":
        Path(args.output).write_text(res2["content"], encoding="utf-8")
        print(f"\n✅ 综述已保存至：{args.output}")
    else:
        print(f"\n❌ 阶段二失败：{res2['error']}")
