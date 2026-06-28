from app import create_app
from app.services.sites import load_sites


def test_load_sites_preserves_configured_captcha_policy(tmp_path):
    config_path = tmp_path / "sites.yaml"
    config_path.write_text(
        """
sites:
  - id: solver_site
    name: Solver Site
    url: https://example.com
    enabled: true
    captcha_policy: solve
  - id: default_site
    name: Default Site
    url: https://default.example
    enabled: true
""",
        encoding="utf-8",
    )
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
            "SITES_CONFIG_PATH": str(config_path),
            "CAPTCHA_POLICY_DEFAULT": "none",
        }
    )

    with app.app_context():
        sites = load_sites()

    assert sites["solver_site"]["captcha_policy"] == "solve"
    assert sites["default_site"]["captcha_policy"] == "none"
