"""
pipeline.py - 综述论文生成工具主流程脚本
成员 F：系统集成模块
职责：串联 C（检索下载）→ D（解析入库）→ B（向量库）→ A（LangGraph 编排）→ E（生成） 全链路

Sprint 1 阶段：
  - 各模块函数调用以 Mock / try-import 方式占位
  - 完整接入待 Sprint 2 各成员产出就绪后对接
"""

import time
import logging
from typing import Optional

# ---- 日志配置 ----
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("pipeline")


# ============================================================
# 模块导入（Sprint 1：try-import + Mock 兜底）
# ============================================================

# 成员 C：论文检索与下载
try:
    from paper_fetcher import search_arxiv, download_pdf
    HAS_C = True
    logger.info("成员 C 模块加载成功。")
except ImportError:
    HAS_C = False
    logger.warning("paper_fetcher.py 未找到，将使用 Mock 数据（成员 C）。")

    def search_arxiv(query: str, max_results: int = 5, year_from: int = 2020):
        """Mock: 返回示例论文元数据列表"""
        logger.info(f"[Mock-C] search_arxiv(query={query!r}, max_results={max_results})")
        return [
            {
                "title": f"Mock Paper {i}: {query}",
                "authors": ["Author A", "Author B"],
                "summary": f"This is a mock abstract for paper {i} about {query}.",
                "published": "2023-01-01",
                "pdf_url": f"https://arxiv.org/pdf/mock_{i:04d}.pdf",
                "arxiv_id": f"mock_{i:04d}",
                "local_path": f"./data/pdfs/mock_{i:04d}.pdf"
            }
            for i in range(1, max_results + 1)
        ]

    def download_pdf(url: str, save_path: str) -> bool:
        logger.info(f"[Mock-C] download_pdf(url={url!r}) -> {save_path!r}")
        return True


# 成员 D：文档解析与向量化
try:
    from pdf_parser import parse_pdf
    from embedder import embed_chunks
    HAS_D = True
    logger.info("成员 D 模块加载成功。")
except ImportError:
    HAS_D = False
    logger.warning("pdf_parser.py / embedder.py 未找到，将使用 Mock 数据（成员 D）。")

    def parse_pdf(pdf_path: str) -> list:
        logger.info(f"[Mock-D] parse_pdf({pdf_path!r})")
        return [
            {"text": f"Mock chunk {i} from {pdf_path}", "metadata": {"source": pdf_path, "chunk_id": i}}
            for i in range(3)
        ]

    def embed_chunks(chunks: list) -> list:
        logger.info(f"[Mock-D] embed_chunks({len(chunks)} chunks)")
        return [
            {**chunk, "embedding": [0.1] * 384}  # 384-dim 占位向量
            for chunk in chunks
        ]


# 成员 B：RAG 引擎
try:
    from rag_engine import add_documents, retrieve
    HAS_B = True
    logger.info("成员 B 模块加载成功。")
except ImportError:
    HAS_B = False
    logger.warning("rag_engine.py 未找到，将使用 Mock 数据（成员 B）。")

    def add_documents(texts: list, embeddings: list, metadata: list) -> bool:
        logger.info(f"[Mock-B] add_documents({len(texts)} docs)")
        return True

    def retrieve(query: str, top_k: int = 3) -> list:
        logger.info(f"[Mock-B] retrieve(query={query!r}, top_k={top_k})")
        return [
            {"content": f"Mock retrieved chunk {i} for '{query}'", "score": 0.9 - i * 0.1}
            for i in range(top_k)
        ]


# 成员 A：LangGraph 编排主入口
try:
    from graph import run_survey_generation as _real_run
    HAS_A = True
    logger.info("成员 A 模块加载成功。")
except ImportError:
    HAS_A = False
    logger.warning("graph.py 未找到，将使用 Mock 流程（成员 A）。")

    def _real_run(user_input: str) -> dict:
        logger.info(f"[Mock-A] run_survey_generation({user_input!r})")
        time.sleep(0.5)
        return {
            "user_query": user_input,
            "outline": ["1. Introduction", "2. Related Work", "3. Methodology", "4. Conclusion"],
            "final_content": {
                "1. Introduction": f"Mock introduction section for: {user_input}",
                "2. Related Work": "Mock related work section.",
                "3. Methodology": "Mock methodology section.",
                "4. Conclusion": "Mock conclusion section.",
            }
        }


# ============================================================
# 主流程函数（供 app.py / CLI 调用）
# ============================================================

def run_pipeline(
    topic: str,
    year_from: int = 2020,
    max_papers: int = 20,
    language: str = "中文",
    on_progress: Optional[callable] = None
) -> dict:
    """
    综述论文生成工具主流程。

    Args:
        topic       : 研究主题
        year_from   : 检索起始年份
        max_papers  : 最大文献数量
        language    : 综述语言
        on_progress : 进度回调函数，签名 (step: str, message: str) -> None

    Returns:
        dict: {
            "status": "success" | "error",
            "content": str,          # 最终 Markdown 综述
            "outline": list[str],    # 大纲章节列表
            "papers": list[dict],    # 已处理的论文元数据
            "error": str | None
        }
    """

    def _progress(step: str, msg: str):
        logger.info(f"[Pipeline] {step}: {msg}")
        if on_progress:
            on_progress(step, msg)

    try:
        # ---- Step 1: 论文检索（成员 C）----
        _progress("search", f"正在检索「{topic}」相关论文（year >= {year_from}，最多 {max_papers} 篇）...")
        papers = search_arxiv(query=topic, max_results=max_papers, year_from=year_from)
        _progress("search", f"检索完成，共获取 {len(papers)} 篇论文元数据。")

        # ---- Step 2: PDF 下载（成员 C）----
        _progress("download", "正在下载 PDF 全文...")
        for paper in papers:
            download_pdf(paper.get("pdf_url", ""), paper.get("local_path", ""))
        _progress("download", f"PDF 下载完成，共 {len(papers)} 篇。")

        # ---- Step 3: PDF 解析 + 向量化（成员 D）----
        _progress("parse", "正在解析 PDF 文档并提取文本块...")
        all_chunks = []
        for paper in papers:
            chunks = parse_pdf(paper.get("local_path", ""))
            for chunk in chunks:
                chunk.setdefault("metadata", {}).update({
                    "paper_title": paper.get("title", ""),
                    "authors": ", ".join(paper.get("authors", [])),
                    "year": paper.get("published", "")[:4]
                })
            all_chunks.extend(chunks)
        _progress("parse", f"文本解析完成，共生成 {len(all_chunks)} 个文本块。")

        _progress("embed", "正在生成文本向量...")
        embedded_chunks = embed_chunks(all_chunks)
        _progress("embed", "向量生成完成。")

        # ---- Step 4: 入库（成员 B）----
        _progress("index", "正在将向量写入知识库（ChromaDB）...")
        texts = [c["text"] for c in embedded_chunks]
        embeddings = [c["embedding"] for c in embedded_chunks]
        metadata = [c.get("metadata", {}) for c in embedded_chunks]
        add_documents(texts=texts, embeddings=embeddings, metadata=metadata)
        _progress("index", "知识库写入完成。")

        # ---- Step 5: LangGraph 编排（成员 A，内部调用 B/E）----
        _progress("generate", "启动 LangGraph 智能体，规划大纲并逐章生成综述...")
        user_input = (
            f"topic={topic}, year_from={year_from}, "
            f"max_papers={max_papers}, language={language}"
        )
        result = _real_run(user_input)
        _progress("generate", "综述生成完成。")

        # ---- Step 6: 整合输出 ----
        _progress("finalize", "正在整合最终文稿...")
        outline = result.get("outline", [])
        final_content_dict = result.get("final_content", {})

        # 将章节字典拼接为完整 Markdown
        md_lines = [f"# {topic} 综述\n"]
        for section in outline:
            md_lines.append(f"\n## {section}\n")
            md_lines.append(final_content_dict.get(section, "（内容待生成）") + "\n")

        full_markdown = "\n".join(md_lines)
        _progress("finalize", "✅ 全流程执行完毕！")

        return {
            "status": "success",
            "content": full_markdown,
            "outline": outline,
            "papers": papers,
            "error": None
        }

    except Exception as e:
        logger.exception("主流程执行异常")
        return {
            "status": "error",
            "content": "",
            "outline": [],
            "papers": [],
            "error": str(e)
        }


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="综述论文生成工具 - 命令行模式")
    parser.add_argument("topic", type=str, help="研究主题")
    parser.add_argument("--year", type=int, default=2020, help="起始年份（默认 2020）")
    parser.add_argument("--papers", type=int, default=10, help="最大文献数量（默认 10）")
    parser.add_argument("--lang", type=str, default="中文", help="综述语言（默认 中文）")
    parser.add_argument("--output", type=str, default="survey_output.md", help="输出文件路径")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  综述论文生成工具  |  Sprint 1")
    print(f"  主题：{args.topic}")
    print(f"  起始年份：{args.year}  |  最大文献：{args.papers}  |  语言：{args.lang}")
    print(f"{'='*60}\n")

    result = run_pipeline(
        topic=args.topic,
        year_from=args.year,
        max_papers=args.papers,
        language=args.lang
    )

    if result["status"] == "success":
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result["content"])
        print(f"\n✅ 综述已保存至：{args.output}")
    else:
        print(f"\n❌ 生成失败：{result['error']}")
