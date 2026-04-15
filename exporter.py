"""
exporter.py - 多格式导出模块
成员 F：综述论文生成工具系统集成
职责：将生成的 Markdown 综述导出为 .md / .pdf / .docx 格式

Sprint 1 阶段：导出 Markdown 功能完整实现；PDF/Word 导出为框架占位，Sprint 2 完善。
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("exporter")


# ============================================================
# Markdown 导出
# ============================================================

def export_markdown(content: str, output_path: str = "survey.md") -> str:
    """
    将综述内容保存为 Markdown 文件。

    Args:
        content    : Markdown 格式的综述文本
        output_path: 输出文件路径

    Returns:
        str: 实际写入的文件绝对路径
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logger.info(f"Markdown 导出成功：{path.resolve()}")
    return str(path.resolve())


# ============================================================
# PDF 导出
# ============================================================

def export_pdf(content: str, output_path: str = "survey.pdf") -> str:
    """
    将 Markdown 综述内容转换为 PDF 文件。
    优先尝试 pandoc（命令行），fallback 使用 reportlab（纯 Python）。

    Args:
        content    : Markdown 格式综述文本
        output_path: 输出文件路径

    Returns:
        str: 实际写入的文件绝对路径
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 先将内容写入临时 md 文件
    tmp_md = path.with_suffix(".tmp.md")
    tmp_md.write_text(content, encoding="utf-8")

    # 方案 1：尝试 pandoc
    try:
        import subprocess
        result = subprocess.run(
            ["pandoc", str(tmp_md), "-o", str(path), "--pdf-engine=xelatex"],
            capture_output=True, timeout=60
        )
        if result.returncode == 0:
            tmp_md.unlink(missing_ok=True)
            logger.info(f"PDF 导出成功（pandoc）：{path.resolve()}")
            return str(path.resolve())
        else:
            logger.warning(f"pandoc 执行失败：{result.stderr.decode()}")
    except (FileNotFoundError, Exception) as e:
        logger.warning(f"pandoc 不可用：{e}，尝试 reportlab...")

    # 方案 2：reportlab 纯 Python
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        doc = SimpleDocTemplate(str(path), pagesize=A4,
                                leftMargin=2.5*cm, rightMargin=2.5*cm,
                                topMargin=2.5*cm, bottomMargin=2.5*cm)
        styles = getSampleStyleSheet()
        story = []

        for line in content.split("\n"):
            if line.startswith("# "):
                p = Paragraph(line[2:], styles["Title"])
            elif line.startswith("## "):
                p = Paragraph(line[3:], styles["Heading1"])
            elif line.startswith("### "):
                p = Paragraph(line[4:], styles["Heading2"])
            elif line.strip():
                # 移除 Markdown 粗体/斜体标记（简单处理）
                clean = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
                clean = re.sub(r'\*(.+?)\*', r'\1', clean)
                p = Paragraph(clean, styles["Normal"])
            else:
                p = Spacer(1, 0.3*cm)
            story.append(p)

        doc.build(story)
        tmp_md.unlink(missing_ok=True)
        logger.info(f"PDF 导出成功（reportlab）：{path.resolve()}")
        return str(path.resolve())

    except ImportError:
        logger.error("reportlab 未安装，PDF 导出失败。请运行：pip install reportlab")
        tmp_md.unlink(missing_ok=True)
        raise RuntimeError("PDF 导出失败：pandoc 和 reportlab 均不可用。")


# ============================================================
# Word 导出
# ============================================================

def export_docx(content: str, output_path: str = "survey.docx") -> str:
    """
    将 Markdown 综述内容转换为 Word (.docx) 文件。
    使用 python-docx 库实现。

    Args:
        content    : Markdown 格式综述文本
        output_path: 输出文件路径

    Returns:
        str: 实际写入的文件绝对路径
    """
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        raise RuntimeError("python-docx 未安装，请运行：pip install python-docx")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()

    # 设置默认字体
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    for line in content.split("\n"):
        if line.startswith("# "):
            heading = doc.add_heading(line[2:], level=0)
            heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=1)
        elif line.startswith("### "):
            doc.add_heading(line[4:], level=2)
        elif line.startswith("---"):
            doc.add_paragraph("—" * 30)
        elif line.strip():
            # 处理粗体 **text**
            para = doc.add_paragraph()
            parts = re.split(r'(\*\*.+?\*\*)', line)
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    run = para.add_run(part[2:-2])
                    run.bold = True
                else:
                    para.add_run(part)
        else:
            doc.add_paragraph("")

    doc.save(str(path))
    logger.info(f"Word 导出成功：{path.resolve()}")
    return str(path.resolve())


# ============================================================
# 统一导出接口
# ============================================================

def export(content: str, fmt: str = "md", output_dir: str = "./output",
           filename: str = "survey") -> str:
    """
    统一导出接口，根据格式分发到对应导出函数。

    Args:
        content   : Markdown 综述内容
        fmt       : 导出格式，"md" | "pdf" | "docx"
        output_dir: 输出目录
        filename  : 文件名（不含扩展名）

    Returns:
        str: 输出文件的绝对路径
    """
    fmt = fmt.lower().strip(".")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{filename}.{fmt}")

    dispatch = {
        "md":   export_markdown,
        "pdf":  export_pdf,
        "docx": export_docx,
        "word": export_docx,
    }

    if fmt not in dispatch:
        raise ValueError(f"不支持的导出格式：{fmt}。支持格式：md, pdf, docx")

    return dispatch[fmt](content, output_path)


# ============================================================
# 快速测试
# ============================================================

if __name__ == "__main__":
    sample_content = """# 大型语言模型综述

## 1. 引言

大型语言模型（LLM）是近年来人工智能领域的重要突破，以 GPT、LLaMA 等为代表，推动了自然语言处理任务的全面提升。

## 2. 相关工作

**Transformer 架构** 由 Vaswani 等人于 2017 年提出，是现代 LLM 的基础结构。自注意力机制的引入显著提升了模型对长程依赖关系的建模能力。

## 3. 结论

LLM 在多个基准任务上已超越人类平均水平，未来研究方向包括模型压缩、多模态融合和对齐技术。

---
*本综述由综述论文生成工具自动生成*
"""

    # 测试 Markdown 导出
    path_md = export(sample_content, fmt="md", output_dir="./test_output", filename="test_survey")
    print(f"✅ Markdown 导出：{path_md}")

    # 测试 DOCX 导出（如果 python-docx 可用）
    try:
        path_docx = export(sample_content, fmt="docx", output_dir="./test_output", filename="test_survey")
        print(f"✅ Word 导出：{path_docx}")
    except RuntimeError as e:
        print(f"⚠️  Word 导出跳过：{e}")
