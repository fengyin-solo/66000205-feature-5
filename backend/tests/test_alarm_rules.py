"""End-to-end checks for configurable per-point alarm rules.

Run:  python -m pytest backend/tests -q   (or execute this file directly)
Uses a throwaway SQLite directory via ALARM_DB_DIR.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp(prefix="alarm_rules_test_")
os.environ["ALARM_DB_DIR"] = _tmp

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def client():
    return TestClient(app)


def main() -> None:
    with client() as c:
        # --- validation rejects with per-field reasons and saves nothing ---
        r = c.post("/api/alarm/rules", json={"point": "温度", "condition": "gt", "level": "warning", "scope": []})
        assert r.status_code == 400 and "upperLimit" in r.json()["detail"]["errors"]

        r = c.post("/api/alarm/rules", json={"point": "温度", "condition": "between",
                                             "lowerLimit": 40, "upperLimit": 30, "level": "critical", "scope": []})
        assert r.status_code == 400 and "lowerLimit" in r.json()["detail"]["errors"]

        r = c.post("/api/alarm/rules", json={"point": "温度", "condition": "gt", "upperLimit": 28,
                                             "level": "warning", "scope": ["ghost"]})
        assert r.status_code == 400 and "scope" in r.json()["detail"]["errors"]

        r = c.post("/api/alarm/rules", json={"point": "温度", "condition": "weird",
                                             "upperLimit": 1, "level": "warning", "scope": []})
        assert r.status_code in (400, 422)

        # --- create warning + critical rules for 温度 ---
        r = c.post("/api/alarm/rules", headers={"X-Operator": "zhangsan"},
                   json={"point": "温度", "condition": "gt", "upperLimit": 0, "level": "warning", "scope": []})
        assert r.status_code == 201
        warn_id = r.json()["rule"]["id"]

        r = c.post("/api/alarm/rules", headers={"X-Operator": "zhangsan"},
                   json={"point": "温度", "condition": "gt", "upperLimit": 0, "level": "critical", "scope": []})
        crit_id = r.json()["rule"]["id"]

        # duplicate point+level+scope is rejected
        r = c.post("/api/alarm/rules", headers={"X-Operator": "zhangsan"},
                   json={"point": "温度", "condition": "gt", "upperLimit": 99, "level": "warning", "scope": []})
        assert r.status_code == 400 and "point" in r.json()["detail"]["errors"]

        # --- idempotent retry with the same key: one rule, one audit row ---
        key = "client-retry-key-1"
        payload = {"point": "管道压力", "condition": "lt", "lowerLimit": 100, "level": "info", "scope": ["dev2"]}
        ids = set()
        for _ in range(3):
            r = c.post("/api/alarm/rules", headers={"Idempotency-Key": key, "X-Operator": "lisi"}, json=payload)
            assert r.status_code == 201
            ids.add(r.json()["rule"]["id"])
        assert len(ids) == 1
        press = [x for x in c.get("/api/alarm/rules").json() if x["point"] == "管道压力"]
        press_audits = [a for a in c.get("/api/alarm/audit").json() if a["point"] == "管道压力"]
        assert len(press) == 1 and len(press_audits) == 1

        # failed validation releases the key so a corrected retry can reuse it
        bad = {**payload, "point": "差压", "lowerLimit": None}
        r = c.post("/api/alarm/rules", headers={"Idempotency-Key": "reused-after-fail", "X-Operator": "lisi"}, json=bad)
        assert r.status_code == 400
        good = {**payload, "point": "差压"}
        r = c.post("/api/alarm/rules", headers={"Idempotency-Key": "reused-after-fail", "X-Operator": "lisi"}, json=good)
        assert r.status_code == 201

        # --- poll evaluates under the CURRENT rules; worst matching level wins ---
        r = c.post("/api/modbus/poll")
        ta = [a for a in r.json()["alarms"] if a["point"] == "温度"]
        assert ta and ta[0]["level"] == "critical" and ta[0]["ruleVersion"] == 1
        old_record = c.get("/api/alarm/records?point=温度").json()[-1]

        # edit the critical rule: raise threshold out of reach -> takes effect immediately
        r = c.put(f"/api/alarm/rules/{crit_id}", headers={"X-Operator": "wangwu"},
                  json={"point": "温度", "condition": "gt", "upperLimit": 999, "level": "critical", "scope": []})
        assert r.status_code == 200 and r.json()["rule"]["version"] == 2

        # historical record still renders with the snapshot level/version, also after re-fetch
        rec = next(x for x in c.get("/api/alarm/records?point=温度").json() if x["id"] == old_record["id"])
        assert rec["level"] == "critical" and rec["ruleVersion"] == 1

        r = c.post("/api/modbus/poll")
        assert all(a["level"] != "critical" for a in r.json()["alarms"] if a["point"] == "温度")

        # PUT with idempotency key retried -> version bumps once, one audit row
        key2 = "put-retry-key"
        for i in range(2):
            r = c.put(f"/api/alarm/rules/{warn_id}", headers={"Idempotency-Key": key2, "X-Operator": "wangwu"},
                      json={"point": "温度", "condition": "gt", "upperLimit": 999, "level": "warning", "scope": []})
            assert r.status_code == 200
        rule = c.get(f"/api/alarm/rules/{warn_id}").json()
        assert rule["version"] == 2
        wh = c.get(f"/api/alarm/audit?rule_id={warn_id}").json()
        assert [a["action"] for a in wh] == ["update", "create"]

        # no more temperature alarms at all after both thresholds move out of reach
        r = c.post("/api/modbus/poll")
        assert not [a for a in r.json()["alarms"] if a["point"] == "温度"]

        # failed update writes no audit row
        n_before = len(c.get("/api/alarm/audit").json())
        r = c.put(f"/api/alarm/rules/{warn_id}", headers={"X-Operator": "x"},
                  json={"point": "温度", "condition": "between", "lowerLimit": 9, "upperLimit": 1,
                        "level": "warning", "scope": []})
        assert r.status_code == 400
        assert len(c.get("/api/alarm/audit").json()) == n_before

        # enable/disable leaves its own trace
        c.post(f"/api/alarm/rules/{crit_id}/toggle?enabled=false", headers={"X-Operator": "admin"})
        c.post(f"/api/alarm/rules/{crit_id}/toggle?enabled=true", headers={"X-Operator": "admin"})
        actions = [a["action"] for a in c.get(f"/api/alarm/audit?rule_id={crit_id}").json()]
        assert "disable" in actions and "enable" in actions

        # scope isolation: a scoped rule only fires for devices inside its scope
        c.post("/api/alarm/rules", headers={"X-Operator": "admin"},
               json={"point": "湿度", "condition": "lt", "lowerLimit": 999, "level": "info", "scope": ["dev2"]})
        r = c.post("/api/modbus/poll")
        assert not [a for a in r.json()["alarms"] if a["point"] == "湿度"]  # dev1 not in scope

    # fresh client = "refresh": persisted snapshot records unchanged
    recs = client().get("/api/alarm/records?point=温度").json()
    assert any(x["level"] == "critical" and x["ruleVersion"] == 1 for x in recs)

    shutil.rmtree(_tmp, ignore_errors=True)
    print("ALL BACKEND TESTS PASSED")


if __name__ == "__main__":
    main()
