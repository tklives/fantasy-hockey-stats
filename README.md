# Fantasy Hockey Stats

A read-only weekly summary for an ESPN fantasy hockey league: who scored what, on which day, and how
many points were left on the bench. A GitHub Action refreshes it every morning and publishes it to
GitHub Pages.

- `espn_weekly_pull.py` reads the league from ESPN (GET requests only) and saves one file per week in `data/`.
- `build_page.py` turns `data/` into a single static page, `site/index.html`.
- `check_no_secrets.py` fails the nightly run if a cookie value ever ends up in the files it is about to publish.
- `.github/workflows/nightly.yml` runs the three above on a schedule and deploys the page.

## Run it locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process RemoteSigned
pip install -r requirements.txt

$env:ESPN_S2   = '<espn_s2 cookie>'     # from your browser's cookies for fantasy.espn.com
$env:ESPN_SWID = '{<SWID cookie>}'      # keep the braces

python espn_weekly_pull.py --week 3     # or --auto for the previous and current week
python build_page.py                    # then open site\index.html
```

`--discover` dumps raw samples to `out/` for checking ESPN's field names and ids.

## The nightly job

Add two repository secrets (Settings > Secrets and variables > Actions, or `gh secret set NAME`):
`ESPN_S2` and `ESPN_SWID`. The workflow commits the updated `data/` files back to the repo, so the
history of finished weeks lives in git. Days older than yesterday are reused from `data/` rather than
fetched again.

If a run fails with "ESPN rejected the cookies", the `espn_s2` cookie has expired: copy a fresh value
from the browser and update the secret.

## Notes

- Weeks run Monday to Sunday, and scoring period 1 was 2026-09-29. Both are set in the code.
- The `DNP` tag is exact (the team played and the player has an empty stat line). `O` / `DTD` come from ESPN's
  injury status as of the last update, not a per-game flag, so they only appear for the current day.
