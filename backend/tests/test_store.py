import pytest

from diary import store


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    return tmp_path


def entry(date):
    return {"metadata": {"date": date}, "sections": []}


def test_write_then_read_round_trips():
    store.write(entry("2026-10-24"))
    assert store.read("2026-10-24") == entry("2026-10-24")


def test_read_unknown_date_is_none():
    assert store.read("2026-01-01") is None


def test_write_refuses_to_clobber_without_force():
    store.write(entry("2026-10-24"))
    with pytest.raises(FileExistsError):
        store.write(entry("2026-10-24"))
    store.write({**entry("2026-10-24"), "v": 2}, force=True)
    assert store.read("2026-10-24")["v"] == 2


def test_list_dates_is_sorted_and_ignores_other_files(data_dir):
    for d in ("2026-10-24", "2026-10-22", "2026-10-23"):
        store.write(entry(d))
    (data_dir / "notes.json").write_text("{}")
    assert store.list_dates() == ["2026-10-22", "2026-10-23", "2026-10-24"]


def test_bad_dates_never_reach_the_filesystem():
    with pytest.raises(ValueError):
        store.read("../../etc/passwd")
    with pytest.raises(ValueError):
        store.write(entry("2026-1-1"))


def test_write_leaves_no_temp_files(data_dir):
    store.write(entry("2026-10-24"))
    assert [p.name for p in data_dir.iterdir()] == ["2026-10-24.json"]


def test_written_files_are_readable_by_other_users(data_dir):
    store.write(entry("2026-10-24"))
    assert (data_dir / "2026-10-24.json").stat().st_mode & 0o777 == 0o644
