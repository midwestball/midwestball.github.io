import os
from projection_ops import secrets


def test_load_backend_credentials_accepts_lowercase_without_printing(tmp_path, monkeypatch, capsys):
    env = tmp_path / ".env"
    env.write_text("supabase_url=https://example.invalid\nsupabase_service_role_key=secret-value\n")
    monkeypatch.setattr(secrets.SETTINGS, "repo_root", tmp_path.parent) if False else None
    monkeypatch.setattr(secrets, "SETTINGS", type("S", (), {"repo_root": tmp_path.parent})())
    (tmp_path.parent / "backend").mkdir(exist_ok=True)
    env.replace(tmp_path.parent / "backend" / ".env")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    secrets.load_backend_credentials()
    assert os.environ["SUPABASE_URL"] == "https://example.invalid"
    assert capsys.readouterr().out == ""
