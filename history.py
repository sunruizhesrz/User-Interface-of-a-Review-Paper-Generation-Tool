"""
history.py - 历史记录模块（Sprint 2 新建）
成员 F：用户交互界面 + 系统集成

Sprint 2 任务 F-05：实现本地历史记录功能
  - 将每次生成记录追加写入 JSON 文件
  - 支持读取最近 N 条记录
  - 供 app.py 侧边栏展示使用
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger("history")

# 历史记录文件路径（相对于运行目录）
HISTORY_FILE = Path("./output/history.json")
MAX_RECORDS = 50   # 最多保留 50 条，防止文件过大


def save_history(topic: str, result_path: str, timestamp: str = "") -> None:
    """
    将一条生成记录追加写入历史文件。

    Args:
        topic      : 研究主题
        result_path: 输出文件路径
        timestamp  : 时间戳字符串，默认为当前时间
    """
    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    record = {
        "topic":     topic,
        "path":      result_path,
        "timestamp": timestamp,
    }

    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        records = _read_all()
        records.insert(0, record)          # 最新的排在最前
        records = records[:MAX_RECORDS]    # 只保留最近 MAX_RECORDS 条
        HISTORY_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"历史记录已保存：topic={topic!r}")
    except Exception as e:
        logger.warning(f"保存历史记录失败：{e}")


def load_history(limit: int = 5) -> List[Dict]:
    """
    加载最近 N 条历史记录。

    Args:
        limit: 返回的最大条数

    Returns:
        List[dict]: 每条记录包含 topic / path / timestamp
    """
    records = _read_all()
    return records[:limit]


def clear_history() -> None:
    """清空所有历史记录"""
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
        logger.info("历史记录已清空")
    except Exception as e:
        logger.warning(f"清空历史记录失败：{e}")


def _read_all() -> List[Dict]:
    """内部：读取全部历史记录"""
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"读取历史记录文件失败：{e}")
        return []


# ============================================================
# 快速测试
# ============================================================

if __name__ == "__main__":
    # 写入 3 条测试记录
    save_history("大型语言模型综述",      "./output/survey_001.md", "2026-04-19 10:00")
    save_history("RAG 技术综述",          "./output/survey_002.md", "2026-04-19 11:00")
    save_history("Transformer 在 NLP 中的应用", "./output/survey_003.md", "2026-04-19 12:00")

    records = load_history(limit=5)
    print(f"最近 {len(records)} 条历史记录：")
    for r in records:
        print(f"  [{r['timestamp']}] {r['topic']} → {r['path']}")
