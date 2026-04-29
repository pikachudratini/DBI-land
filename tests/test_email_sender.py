from dbi_land.email_sender import EmailConfig, send_digest


def test_dry_run_returns_payload():
    cfg = EmailConfig(
        api_key="k",
        from_addr="bot@example.com",
        to_addrs=("buyer@example.com",),
    )
    out = send_digest(cfg, subject="hi", html="<p>x</p>", dry_run=True)
    assert out["dry_run"] is True
    assert out["payload"]["from"] == "bot@example.com"
    assert out["payload"]["to"] == ["buyer@example.com"]
    assert out["payload"]["subject"] == "[DBI Land] hi"
    assert out["payload"]["html"] == "<p>x</p>"


def test_from_env(monkeypatch):
    monkeypatch.setenv("DBI_RESEND_API_KEY", "k")
    monkeypatch.setenv("DBI_RESEND_FROM", "bot@example.com")
    monkeypatch.setenv("DBI_RESEND_TO", "a@example.com, b@example.com")
    cfg = EmailConfig.from_env()
    assert cfg.api_key == "k"
    assert cfg.to_addrs == ("a@example.com", "b@example.com")
