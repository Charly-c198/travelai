"""一次性数据迁移：给向量库中"有坐标的真景点"回填英文名 name_en。

设计原则：
- name_en 存在 = "可验证的真地点"（照片/查询的唯一信任来源）。
- 真实地标 → 补英文名（sqlite spots 表优先，其次手工表）。
- 旅行贴士/攻略碎片（防坑指南：、健康关怀：等）→ 不补 name_en，
  后端 `draft_itinerary.spots` 会用"必须有 name_en"过滤掉它们，不再混入行程/图鉴。

运行：python scripts/backfill_spot_name_en.py （在 backend 目录下，用 venv python）
幂等：重复运行只影响仍缺 name_en 的条目。
"""
import sys
import sqlite3
from pathlib import Path

import chromadb
from chromadb.config import Settings

BACKEND = Path(__file__).resolve().parent.parent
VECTOR_PATH = BACKEND / "data" / "vectorstore"
SQLITE_DB = BACKEND / "travelai.db"
COLLECTION = "travel_spots"

# 手工覆盖：真实地标的中英对照（仅覆盖少数确有此景的；贴士碎片不在此表）
MANUAL: dict[str, str] = {
    "拙政园": "Humble Administrator's Garden Suzhou",
    "平江路": "Pingjiang Road Suzhou",
    "大鹏所城": "Dapeng Fortress Shenzhen",
}


def sqlite_name_en(name: str) -> str | None:
    try:
        db = sqlite3.connect(str(SQLITE_DB))
        row = db.execute("SELECT name_en FROM spots WHERE name=?", (name,)).fetchone()
        db.close()
        return row[0] if row and row[0] else None
    except Exception:
        return None


def main() -> int:
    client = chromadb.PersistentClient(path=str(VECTOR_PATH))
    col = client.get_collection(COLLECTION)
    data = col.get(include=["metadatas"])
    ids = data["ids"]
    metas = data["metadatas"] or []

    updated_ids: list[str] = []
    updated_metas: list[dict] = []
    filled, skipped = 0, 0

    for i, m in enumerate(metas):
        if not m:
            continue
        # 只处理"有坐标的真景点"里缺 name_en 的
        if m.get("latitude") is None or m.get("longitude") is None:
            continue
        if (m.get("name_en") or "").strip():
            continue
        name = (m.get("name") or "").strip()
        if not name:
            continue
        en = sqlite_name_en(name) or MANUAL.get(name)
        if not en:
            skipped += 1
            print(f"  [跳过·贴士碎片] {name}")
            continue
        new_meta = dict(m)
        new_meta["name_en"] = en
        updated_ids.append(ids[i])
        updated_metas.append(new_meta)
        filled += 1
        print(f"  [回填] {name} -> {en}")

    if updated_ids:
        col.update(ids=updated_ids, metadatas=updated_metas)
    print(f"完成：回填 {filled} 条，跳过(无英文名的碎片) {skipped} 条。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
