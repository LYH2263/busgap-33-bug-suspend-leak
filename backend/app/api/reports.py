import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import BunchReport, Line
from app.services.bunch_engine import detect_bunching, events_to_dicts
from app.services.scope_helpers import active_arrival_payload, active_trips
router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("")
def list_reports(db: Session = Depends(get_db)):
    rows = db.scalars(select(BunchReport).order_by(BunchReport.id.desc())).all()
    return [{"id": r.id, "line_id": r.line_id, "stop_name": r.stop_name,
             "created_at": r.created_at.isoformat(), "events": json.loads(r.summary_json)} for r in rows]

def _detect_active(db: Session, line: Line, stop_name: str | None = None) -> list[dict]:
    """对当前在跑班次统一做间隔检测：报告、建议、轴共用同一参与集。"""
    trips = active_trips(db, line.id)
    payload = active_arrival_payload(db, trips, stop_name)
    events = detect_bunching(payload, line.planned_headway_min, line.bunch_threshold, line.large_threshold)
    return events_to_dicts(events)

@router.post("/run")
def run_detection(line_id: int, stop_name: str | None = None, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line: raise HTTPException(404, "线路不存在")
    data = _detect_active(db, line, stop_name)
    report = BunchReport(line_id=line_id, stop_name=stop_name or "*", created_at=datetime.utcnow(),
                         summary_json=json.dumps(data, ensure_ascii=False))
    db.add(report); db.commit(); db.refresh(report)
    return {"id": report.id, "events": data}

@router.get("/suggestions")
def suggestions(line_id: int, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line: raise HTTPException(404, "线路不存在")
    data = _detect_active(db, line)
    return {"line_id": line_id, "suggestions": [e for e in data if e["status"] != "normal"]}

@router.get("/timeline")
def timeline(line_id: int, stop_name: str = "市民中心", db: Session = Depends(get_db)):
    trips = active_trips(db, line_id)
    arrivals = sorted(active_arrival_payload(db, trips, stop_name), key=lambda a: a["actual_arrive"])
    if not arrivals: return {"stop_name": stop_name, "marks": []}
    t0 = arrivals[0]["actual_arrive"]
    span = max((arrivals[-1]["actual_arrive"] - t0).total_seconds(), 1)
    marks = [{"trip_no": a["trip_no"], "actual_arrive": a["actual_arrive"].isoformat(),
              "pct": round((a["actual_arrive"] - t0).total_seconds() / span * 100, 2)} for a in arrivals]
    return {"stop_name": stop_name, "marks": marks}
