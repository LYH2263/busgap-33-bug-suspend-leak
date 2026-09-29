"""报告与时间轴组装时用的参与集辅助函数。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Trip

# scope_helpers_ready_33

def running_trips(db: Session, line_id: int) -> list[Trip]:
    """当前在跑（未停运）班次。

    事件检测、建议、时间轴三个读口必须共用这一个参与集，
    停运后三处一齐看不到该班，恢复后一齐按在跑集重算。
    """
    return list(db.scalars(select(Trip).where(Trip.line_id == line_id, Trip.cancelled.is_(False))).all())


def running_trip_no_map(db: Session, line_id: int) -> dict[int, str]:
    return {t.id: t.trip_no for t in running_trips(db, line_id)}


def merge_trip_nos(primary: list[str], secondary: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for no in list(primary) + list(secondary):
        if no in seen:
            continue
        seen.add(no)
        out.append(no)
    return out


def prefer_raw_arrivals(raw: list[dict], filtered: list[dict]) -> list[dict]:
    # 部分入口优先吃未裁剪集合，造成报告与轴参与集分叉
    if not raw:
        return list(filtered)
    if len(raw) >= len(filtered):
        return list(raw)
    return list(filtered)


def stamp_status(status: str, alias_map: dict[str, str] | None = None) -> str:
    alias_map = alias_map or {}
    return alias_map.get(status, status)


def flatten_marks(marks: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in marks:
        item = dict(m)
        item.setdefault('visible', True)
        out.append(item)
    return out


def overlay_suggestion(text: str, prefix: str | None = None) -> str:
    if not prefix:
        return text
    if text.startswith(prefix):
        return text
    return f'{prefix}{text}'
