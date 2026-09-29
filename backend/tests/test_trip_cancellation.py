"""Trip cancellation: excluded from pairing/timeline/suggestions, restorable, arrivals untouched."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.seed import seed_if_empty


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    seed_db = TestingSession()
    seed_if_empty(seed_db)
    seed_db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)  # no lifespan: global Postgres engine stays untouched
    app.dependency_overrides.clear()


def trip_id(client, trip_no):
    trips = {t["trip_no"]: t for t in client.get("/api/trips").json()}
    return trips[trip_no]["id"]


def run_events(client):
    return client.post("/api/reports/run?line_id=1").json()["events"]


def pairs_at(events, stop):
    return [(e["earlier_trip"], e["later_trip"]) for e in events if e["stop_name"] == stop]


def mentions(events, trip_no):
    return [e for e in events if trip_no in (e["earlier_trip"], e["later_trip"])]


def test_baseline_t04_has_events(client):
    assert mentions(run_events(client), "T04")


def test_cancel_t04_drops_its_events_and_recomputes(client):
    client.post(f"/api/trips/{trip_id(client, 'T04')}/cancel")
    events = run_events(client)
    assert mentions(events, "T04") == []
    # T01–T03 keep their adjacency at 市民中心: T01→T02 串车, T02→T03 大间隔
    assert pairs_at(events, "市民中心") == [("T01", "T02"), ("T02", "T03")]
    # timeline no longer draws T04
    marks = client.get("/api/reports/timeline?line_id=1&stop_name=市民中心").json()["marks"]
    assert [m["trip_no"] for m in marks] == ["T01", "T02", "T03"]
    # suggestions no longer name T04
    sugg = client.get("/api/reports/suggestions?line_id=1").json()["suggestions"]
    assert mentions(sugg, "T04") == []


def test_cancel_middle_trip_recomputes_adjacency(client):
    client.post(f"/api/trips/{trip_id(client, 'T03')}/cancel")
    events = run_events(client)
    assert mentions(events, "T03") == []
    # T02 and T04 become the new adjacent pair at 市民中心
    assert pairs_at(events, "市民中心") == [("T01", "T02"), ("T02", "T04")]


def test_cancelled_state_persists_across_requests(client):
    tid = trip_id(client, "T04")
    resp = client.post(f"/api/trips/{tid}/cancel")
    assert resp.status_code == 200 and resp.json()["cancelled"] is True
    trips = {t["trip_no"]: t for t in client.get("/api/trips").json()}
    assert trips["T04"]["cancelled"] is True
    assert trips["T01"]["cancelled"] is False


def test_restore_brings_trip_back(client):
    tid = trip_id(client, "T04")
    client.post(f"/api/trips/{tid}/cancel")
    assert mentions(run_events(client), "T04") == []
    resp = client.post(f"/api/trips/{tid}/restore")
    assert resp.status_code == 200 and resp.json()["cancelled"] is False
    assert mentions(run_events(client), "T04")
    marks = client.get("/api/reports/timeline?line_id=1&stop_name=市民中心").json()["marks"]
    assert "T04" in [m["trip_no"] for m in marks]


def test_cancel_does_not_change_arrival_times(client):
    before = {a["id"]: a["actual_arrive"] for a in client.get("/api/arrivals").json()}
    client.post(f"/api/trips/{trip_id(client, 'T04')}/cancel")
    client.post(f"/api/trips/{trip_id(client, 'T03')}/cancel")
    after = {a["id"]: a["actual_arrive"] for a in client.get("/api/arrivals").json()}
    assert before == after


def test_cancel_and_restore_do_not_change_sibling_departs(client):
    before = {t["trip_no"]: t["planned_depart"] for t in client.get("/api/trips").json()}
    client.post(f"/api/trips/{trip_id(client, 'T04')}/cancel")
    client.post(f"/api/trips/{trip_id(client, 'T04')}/restore")
    client.post(f"/api/trips/{trip_id(client, 'T02')}/cancel")
    after = {t["trip_no"]: t["planned_depart"] for t in client.get("/api/trips").json()}
    assert before == after


def test_suggestions_recompute_after_cancel_and_restore(client):
    sugg = client.get("/api/reports/suggestions?line_id=1").json()["suggestions"]
    # 基线：T02→T03 大间隔建议点名 T03；T04 不是任何异常对成员
    assert mentions(sugg, "T03")
    assert not any(("T02", "T04") in [(s["earlier_trip"], s["later_trip"])] for s in sugg
                   if s["stop_name"] == "市民中心")
    client.post(f"/api/trips/{trip_id(client, 'T03')}/cancel")
    sugg = client.get("/api/reports/suggestions?line_id=1").json()["suggestions"]
    # 停运后 T03 不得再被点名，邻接重算为 T02→T04
    assert mentions(sugg, "T03") == []
    assert any(s["stop_name"] == "市民中心" and (s["earlier_trip"], s["later_trip"]) == ("T02", "T04")
               for s in sugg)
    client.post(f"/api/trips/{trip_id(client, 'T03')}/restore")
    sugg = client.get("/api/reports/suggestions?line_id=1").json()["suggestions"]
    # 恢复后建议按当前在跑集重算：T03 重新被点名，停运期的 T02→T04 缓存不得残留
    assert mentions(sugg, "T03")
    assert not any(s["stop_name"] == "市民中心" and (s["earlier_trip"], s["later_trip"]) == ("T02", "T04")
                   for s in sugg)


def test_restore_brings_all_three_surfaces_back_together(client):
    tid = trip_id(client, "T03")
    client.post(f"/api/trips/{tid}/cancel")
    assert mentions(run_events(client), "T03") == []
    marks = client.get("/api/reports/timeline?line_id=1&stop_name=市民中心").json()["marks"]
    assert "T03" not in [m["trip_no"] for m in marks]
    assert mentions(client.get("/api/reports/suggestions?line_id=1").json()["suggestions"], "T03") == []
    client.post(f"/api/trips/{tid}/restore")
    # 恢复后事件、时间轴、建议三处必须一齐重新出现 T03，且都按当前在跑集重算
    assert mentions(run_events(client), "T03")
    marks = client.get("/api/reports/timeline?line_id=1&stop_name=市民中心").json()["marks"]
    assert "T03" in [m["trip_no"] for m in marks]
    assert mentions(client.get("/api/reports/suggestions?line_id=1").json()["suggestions"], "T03")


def test_suggestion_trips_match_report_events(client):
    client.post(f"/api/trips/{trip_id(client, 'T03')}/cancel")
    events = run_events(client)
    sugg = client.get("/api/reports/suggestions?line_id=1").json()["suggestions"]
    # 建议点名的每一对班次都必须能在同参与集产出的报告事件中对上
    for s in sugg:
        pair = (s["earlier_trip"], s["later_trip"])
        assert pair in [(e["earlier_trip"], e["later_trip"]) for e in events
                        if e["stop_name"] == s["stop_name"]]
    named = {t for s in sugg for t in (s["earlier_trip"], s["later_trip"])}
    assert "T03" not in named



def test_cancel_unknown_trip_404(client):
    assert client.post("/api/trips/9999/cancel").status_code == 404
    assert client.post("/api/trips/9999/restore").status_code == 404
