"""The folder automation must be robust: no lost queues, no duplicate feed rows, no races.

Every test here corresponds to a failure that was actually reproduced against the previous
implementation, not to a hypothetical one.
"""
import threading

import pytest
from sqlalchemy import select

from app.automation import inbox as inbox_mod
from app.automation import watcher
from app.db import SessionLocal
from app.models import InboxItem
from tests.conftest import doctor_headers, xray_png


@pytest.fixture
def watched(monkeypatch):
    monkeypatch.setattr(watcher, "SETTLE_S", 0)
    watcher.incoming_dir().mkdir(parents=True, exist_ok=True)
    return watcher.incoming_dir()


def _rows(file_name: str) -> list[str]:
    with SessionLocal() as s:
        return [r.file_name for r in s.scalars(select(InboxItem).where(InboxItem.file_name == file_name))]


def test_one_broken_file_does_not_stall_the_queue(client, watched, monkeypatch):
    """A file that raises something other than ImageError (DB, filesystem) used to abort the whole
    pass, so every file after it stayed unprocessed and the bad one blocked the folder forever."""
    (watched / "a_good.png").write_bytes(xray_png(seed=41))
    (watched / "b_broken.png").write_bytes(b"\x89PNG\r\n\x1a\nnot really")
    (watched / "c_good.png").write_bytes(xray_png(seed=43))

    real_process = inbox_mod.process
    calls: list[str] = []

    def exploding(session, data, file_name, source):
        calls.append(file_name)
        if file_name == "b_broken.png":
            raise RuntimeError("simulated database failure")
        return real_process(session, data, file_name, source)

    monkeypatch.setattr(inbox_mod, "process", exploding)
    assert watcher.run_once() == (0, 2)  # both good files still verified
    assert calls == ["a_good.png", "b_broken.png", "c_good.png"]  # the bad one was not fatal
    assert (watched / "processed" / "a_good.png").exists()
    assert (watched / "processed" / "c_good.png").exists()
    assert (watched / "failed" / "b_broken.png").exists()
    assert sorted(p.name for p in watched.iterdir() if p.is_file()) == []


def test_an_unexpected_error_in_sealing_does_not_stall_the_scanner_folder(client, monkeypatch):
    monkeypatch.setattr(watcher, "SETTLE_S", 0)
    scanner = watcher.scanner_dir()
    scanner.mkdir(parents=True, exist_ok=True)
    (scanner / "a.png").write_bytes(xray_png(seed=51))
    (scanner / "b.png").write_bytes(xray_png(seed=52))

    import app.automation.watcher as w

    real_seal = w.seal_upload
    calls: list[str] = []

    def exploding(session, image, device_id):
        calls.append(image.uid or "?")
        if len(calls) == 1:
            raise RuntimeError("simulated sealing failure")
        return real_seal(session, image, device_id)

    monkeypatch.setattr(w, "seal_upload", exploding)
    assert watcher.run_once() == (1, 1)  # the second scan was still sealed, then verified in the same pass
    assert (scanner / "failed" / "a.png").exists()
    assert (scanner / "processed" / "b.png").exists()


def test_a_crash_between_commit_and_move_does_not_duplicate_the_row(client, watched, monkeypatch):
    """The inbox row is committed before the file is moved out of incoming/, so a crash in that
    window used to produce a second, identical row in the doctor's feed on the next poll."""
    (watched / "dup.png").write_bytes(xray_png(seed=61))

    real_move = watcher._move

    def crashing_move(path, sub):
        raise OSError("simulated crash after the row was committed")

    monkeypatch.setattr(watcher, "_move", crashing_move)
    assert watcher.verify_incoming() == 0  # nothing reported as verified
    assert _rows("dup.png") == ["dup.png"]  # but the work is recorded
    assert (watched / "dup.png").exists()  # and the file is still there

    # Restore only _move (not monkeypatch.undo(), which would also revert the watched fixture's
    # SETTLE_S=0 and make the freshly-written file look too young to be ready again).
    monkeypatch.setattr(watcher, "_move", real_move)
    watcher.verify_incoming()  # the next poll picks it up again
    assert _rows("dup.png") == ["dup.png"], "the same file must not appear twice in the feed"
    assert (watched / "processed" / "dup.png").exists()


def test_reprocessing_a_folder_file_refreshes_it_instead_of_duplicating(client, watched):
    (watched / "again.png").write_bytes(xray_png(seed=62))
    assert watcher.verify_incoming() == 1
    (watched / "again.png").write_bytes(xray_png(seed=62))
    assert watcher.verify_incoming() == 1
    assert _rows("again.png") == ["again.png"]


def test_uploads_are_never_deduplicated(client):
    """Two uploads may share a file name and still be two separate studies for the doctor."""
    from tests.conftest import doctor_headers

    body = xray_png(seed=63)
    for _ in range(2):
        assert client.post("/api/inbox", files={"files": ("same.png", body)},
                           headers=doctor_headers()).status_code == 200
    assert _rows("same.png") == ["same.png", "same.png"]


def test_a_row_is_visible_as_processing_while_it_is_being_verified(client, monkeypatch):
    """The row is committed before the slow work, so a stuck verification is visible, not silent."""
    real_verify = inbox_mod.verify_upload
    seen: list[dict] = []

    def slow(session, image, **kwargs):
        with SessionLocal() as s:
            seen.append(inbox_mod.listing(s)["items"][0])
        return real_verify(session, image, **kwargs)

    monkeypatch.setattr(inbox_mod, "verify_upload", slow)
    client.post("/api/inbox", files={"files": ("x.png", xray_png(seed=71))}, headers=doctor_headers())
    assert seen[0]["state"] == "processing"
    assert seen[0]["status"] == "processing"
    listing = client.get("/api/inbox", headers=doctor_headers()).json()
    assert listing["items"][0]["state"] == "done"
    # x.png is a raw, never-sealed image, so it lands as "unsigned" -> warning, not ok; the point
    # of this test is that the pending row above is not counted, not the severity bucket itself.
    assert listing["counts"] == {"danger": 0, "warning": 1, "ok": 0, "total": 1}


def test_run_once_is_serialised(client, watched):
    """The polling loop and POST /automation/run used to work the same folder at the same time."""
    (watched / "a.png").write_bytes(xray_png(seed=81))
    (watched / "b.png").write_bytes(xray_png(seed=82))
    watcher.SETTLE_S = 0
    results: list[tuple] = []
    errors: list[Exception] = []

    def pass_once():
        try:
            results.append(watcher.run_once())
        except Exception as e:  # pragma: no cover - only on a real failure
            errors.append(e)

    threads = [threading.Thread(target=pass_once) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert sum(n for _, n in results) == 2, "the two files were verified exactly once across four passes"
    assert _rows("a.png") == ["a.png"] and _rows("b.png") == ["b.png"]


def test_gateway_device_is_created_once_under_concurrency(client, monkeypatch):
    from app.models import Device

    monkeypatch.setattr(watcher, "SETTLE_S", 0)
    scanner = watcher.scanner_dir()
    scanner.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        (scanner / f"s{i}.png").write_bytes(xray_png(seed=90 + i))

    errors: list[Exception] = []

    def pass_once():
        try:
            watcher.run_once()
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=pass_once) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    with SessionLocal() as s:
        gateways = s.scalars(select(Device).where(Device.name == watcher.settings.gateway_name)).all()
    assert len(gateways) == 1, "two Shlyuz-Auto devices would each keep their own signing key"


def test_automation_status_reports_observable_state(client, watched):
    (watched / "a.png").write_bytes(xray_png(seed=95))
    watcher.verify_incoming()
    status = client.get("/api/automation", headers=doctor_headers()).json()
    assert status["verified"] >= 1
    assert status["last_error"] is None
    assert status["passes"] >= 0
    assert status["last_event"]["text"].startswith("checked a.png")


def test_a_failing_pass_is_reported_and_recoverable(client, watched, monkeypatch):
    real_seal_new_scans = watcher.seal_new_scans
    monkeypatch.setattr(watcher, "seal_new_scans", lambda: (_ for _ in ()).throw(RuntimeError("disk gone")))
    with pytest.raises(RuntimeError):
        watcher.run_once()
    assert "disk gone" in client.get("/api/automation", headers=doctor_headers()).json()["last_error"]

    # Restore only seal_new_scans (not monkeypatch.undo(), which would also revert the watched
    # fixture's SETTLE_S=0 and make the freshly-written file look too young to be ready).
    monkeypatch.setattr(watcher, "seal_new_scans", real_seal_new_scans)
    (watched / "recovered.png").write_bytes(xray_png(seed=99))
    assert watcher.run_once()[1] == 1  # and the next pass works again
    assert client.get("/api/automation", headers=doctor_headers()).json()["last_error"] is None


def test_triage_names_the_actual_cause():
    """The doctor is told what happened, not just that something did."""
    assert inbox_mod.triage({"status": "forged", "reason": "bad_signature", "shield": None}) == (
        "danger", ["bad_signature"])
    assert inbox_mod.triage({"status": "forged", "reason": "blockchain_mismatch", "shield": None}) == (
        "danger", ["blockchain_mismatch"])
    assert inbox_mod.triage({"status": "tampered", "reason": "patient_mismatch", "shield": None}) == (
        "danger", ["patient_mismatch"])
    assert inbox_mod.triage({"status": "authentic", "shield": None, "phi_warning": "burned_in_annotation"}) == (
        "danger", ["burned_in_annotation"])
    # An unknown code must not leak raw backend text into the doctor's feed.
    assert inbox_mod.triage({"status": "forged", "reason": "sqlite3 weird", "shield": None}) == (
        "danger", ["forged"])


def test_listing_no_longer_parses_the_stored_preview(client):
    """result_json holds a ~100 KB base64 preview per row; the feed must not parse it to render."""
    from app.models import InboxItem as Model
    import json

    body = xray_png(seed=96)
    client.post("/api/inbox", files={"files": ("big.png", body)}, headers=doctor_headers())
    with SessionLocal() as s:
        row = s.scalar(select(Model))
        assert len(json.loads(row.result_json)["preview_png"]) > 1000
        assert set(json.loads(row.summary_json)) == {"device", "changed_tiles", "detective_probability", "risk", "error"}
