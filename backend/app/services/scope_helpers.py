"""报告、时间轴、建议组装时共用的参与集辅助函数。

所有检测入口（/reports/run、/reports/suggestions、/reports/timeline）
都必须以同一批“当前在跑（未停运）”班次为参与集，
停运/恢复后三处一起重算，禁止任何入口回退去吃未裁剪集合。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Arrival, Trip


def active_trips(db: Session, line_id: int) -> list[Trip]:
    """该线路当前在跑（未停运）的班次，按计划发车排序。"""
    return list(
        db.scalars(
            select(Trip)
            .where(Trip.line_id == line_id, Trip.cancelled.is_(False))
            .order_by(Trip.planned_depart, Trip.id)
        ).all()
    )


def active_arrival_payload(
    db: Session, trips: list[Trip], stop_name: str | None = None
) -> list[dict]:
    """给定在跑班次的实际到站记录，供间隔检测/建议共用。

    返回的 trip_no 一定来自在跑班次，保证建议点名的班次
    都能在同一参与集产出的报告事件里对得上。
    """
    trip_ids = [t.id for t in trips]
    if not trip_ids:
        return []
    trip_no_map = {t.id: t.trip_no for t in trips}
    stmt = select(Arrival).where(Arrival.trip_id.in_(trip_ids))
    if stop_name is not None:
        stmt = stmt.where(Arrival.stop_name == stop_name)
    arrivals = db.scalars(stmt).all()
    return [
        {
            "stop_name": a.stop_name,
            "trip_no": trip_no_map[a.trip_id],
            "actual_arrive": a.actual_arrive,
        }
        for a in arrivals
    ]
