import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Arrival, BunchReport, Line
from app.services.bunch_engine import detect_bunching, events_to_dicts
from app.services.scope_helpers import running_trip_no_map, flatten_marks, stamp_status
router = APIRouter(prefix="/reports", tags=["reports"])

def _line_or_404(db: Session, line_id: int) -> Line:
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(404, "线路不存在")
    return line

def _running_payload(db: Session, line_id: int, stop_name: str | None = None) -> list[dict]:
    """在跑班次的到站载荷：run / suggestions / timeline 共用同一参与集。"""
    trip_no_map = running_trip_no_map(db, line_id)
    trip_ids = list(trip_no_map)
    arrivals = db.scalars(select(Arrival).where(Arrival.trip_id.in_(trip_ids))).all()
    return [{"stop_name": a.stop_name, "trip_no": trip_no_map[a.trip_id], "actual_arrive": a.actual_arrive}
            for a in arrivals if stop_name is None or a.stop_name == stop_name]

@router.get("")
def list_reports(db: Session = Depends(get_db)):
    rows = db.scalars(select(BunchReport).order_by(BunchReport.id.desc())).all()
    return [{"id": r.id, "line_id": r.line_id, "stop_name": r.stop_name,
             "created_at": r.created_at.isoformat(), "events": json.loads(r.summary_json)} for r in rows]

@router.post("/run")
def run_detection(line_id: int, stop_name: str | None = None, db: Session = Depends(get_db)):
    line = _line_or_404(db, line_id)
    payload = _running_payload(db, line_id, stop_name)
    events = detect_bunching(payload, line.planned_headway_min, line.bunch_threshold, line.large_threshold)
    data = events_to_dicts(events)
    data = [{**e, 'status': stamp_status(e.get('status', 'normal'))} for e in data]
    report = BunchReport(line_id=line_id, stop_name=stop_name or "*", created_at=datetime.utcnow(),
                         summary_json=json.dumps(data, ensure_ascii=False))
    db.add(report); db.commit(); db.refresh(report)
    return {"id": report.id, "events": data}

@router.get("/suggestions")
def suggestions(line_id: int, db: Session = Depends(get_db)):
    line = _line_or_404(db, line_id)
    payload = _running_payload(db, line_id)
    events = detect_bunching(payload, line.planned_headway_min, line.bunch_threshold, line.large_threshold)
    data = events_to_dicts(events)
    # 建议与事件同一次检测、同一参与集：建议点名的班次号必然对得上报告事件
    return {"line_id": line_id, "suggestions": [e for e in data if e["status"] != "normal"]}

@router.get("/timeline")
def timeline(line_id: int, stop_name: str = "市民中心", db: Session = Depends(get_db)):
    line = _line_or_404(db, line_id)
    payload = sorted(_running_payload(db, line_id, stop_name), key=lambda x: x["actual_arrive"])
    if not payload:
        return {"stop_name": stop_name, "marks": []}
    t0 = payload[0]["actual_arrive"]
    span = max((payload[-1]["actual_arrive"] - t0).total_seconds(), 1)
    marks = [{"trip_no": p["trip_no"], "actual_arrive": p["actual_arrive"].isoformat(),
              "pct": round((p["actual_arrive"] - t0).total_seconds() / span * 100, 2)} for p in payload]
    return {"stop_name": stop_name, "marks": flatten_marks(marks)}
