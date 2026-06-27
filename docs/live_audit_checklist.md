# Live Audit Checklist

Use this checklist only for manual, low-volume verification on sites where testing is allowed.

Do not bypass third-party CAPTCHA. If a site blocks automation, leave it enabled only if the failure is clearly logged and useful for the demo.

## Sites

| Site | URL | Audit result | Notes |
| --- | --- | --- | --- |
| pingomatic | https://pingomatic.com/ | Not run | Phase 3 code logs success, failure, CAPTCHA, and retry outcomes. |
| sitesondisplay | https://www.sitesondisplay.com/add.html | Not run | Phase 3 code logs success, failure, CAPTCHA, and retry outcomes. |
| indexkings | http://www.indexkings.com/index.php | Not run | Phase 3 code logs success, failure, CAPTCHA, and retry outcomes. |
| pingmyurls | https://www.pingmyurls.com/ | Not run | Phase 3 code logs success, failure, CAPTCHA, and retry outcomes. |
| bulklink | http://bulklink.org/ | Not run | Phase 3 code logs success, failure, CAPTCHA, and retry outcomes. |

## Steps

1. Start Flask with `flask --app app:create_app run --debug`.
2. Create one job with one safe URL.
3. Click **Run now** from the job page.
4. Confirm the terminal prints structured activity.
5. Confirm the job page activity panel updates.
6. Confirm JSON and Markdown reports download.
7. Disable any site that is not a legitimate ping endpoint or blocks automation in a way that prevents clear logging.
