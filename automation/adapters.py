from dataclasses import dataclass, field


@dataclass(frozen=True)
class SiteAdapter:
    site_id: str
    page_url: str
    url_input_selector: str | None = None
    title_input_selector: str | None = None
    rss_input_selector: str | None = None
    submit_selector: str | None = None
    checkbox_selectors: tuple[str, ...] = field(default_factory=tuple)
    success_text_patterns: tuple[str, ...] = field(default_factory=tuple)
    error_text_patterns: tuple[str, ...] = field(default_factory=tuple)
    captcha_selectors: tuple[str, ...] = field(default_factory=tuple)


ADAPTERS = {
    "pingomatic": SiteAdapter(
        site_id="pingomatic",
        page_url="https://pingomatic.com/",
        url_input_selector='input[name="blogurl"]',
        title_input_selector='input[name="title"]',
        rss_input_selector='input[name="rssurl"]',
        submit_selector='a.bigbutton',
        checkbox_selectors=('input[type="checkbox"].common',),
        success_text_patterns=("pinging complete", "ping sent", "pings being sent", "pinged", "success"),
        error_text_patterns=("error", "invalid", "required"),
    ),
    "sitesondisplay": SiteAdapter(
        site_id="sitesondisplay",
        page_url="https://www.sitesondisplay.com/add.html",
        success_text_patterns=("thank you", "submitted", "success"),
        error_text_patterns=("error", "invalid", "required"),
    ),
    "indexkings": SiteAdapter(
        site_id="indexkings",
        page_url="http://www.indexkings.com/index.php",
        success_text_patterns=("success", "submitted", "processed"),
        error_text_patterns=("error", "invalid", "required"),
    ),
    "pingmyurls": SiteAdapter(
        site_id="pingmyurls",
        page_url="https://www.pingmyurls.com/",
        success_text_patterns=("success", "submitted", "pinged"),
        error_text_patterns=("error", "invalid", "required"),
    ),
    "bulklink": SiteAdapter(
        site_id="bulklink",
        page_url="http://bulklink.org/",
        success_text_patterns=("success", "submitted", "done"),
        error_text_patterns=("error", "invalid", "required"),
    ),
}


def get_adapter(site_id):
    return ADAPTERS.get(site_id)
