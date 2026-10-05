"""The site the browser tests drive (app/e2e, `npm run e2e` in app/): the app's web build for the local Supabase
(app/dist-e2e), and the API on the test catalogue (test_journey) for the next Friday, the day the app proposes,
on a store of its own. No live check, no Claude, no image asked for. Started by app/playwright.config.ts.

    uv run python tests/e2e_server.py --port 8011
"""

import argparse
import os
import sys
import tempfile
from datetime import date, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from surprise import parcours, quiz  # noqa: E402
from test_journey import catalogue  # noqa: E402


def next_friday(today: date) -> date:
    """As the app's nextFriday (app/src/lib/dates.ts): a Friday is followed by the next one."""
    return today + timedelta(days=(4 - today.weekday()) % 7 or 7)


def main() -> None:
    parser = argparse.ArgumentParser(description="Site des tests navigateur : l'app (dist-e2e) et l'API sur le catalogue de test")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    os.environ.pop("ANTHROPIC_API_KEY", None)
    items = catalogue(next_friday(date.today()))
    base = parcours.Base(items, {(i["source_id"], i["external_id"]): 35 for i in items})
    parcours.Base.load = classmethod(lambda cls, store: base)
    parcours.unshown = lambda steps: set()
    quiz.WEB = Path(__file__).resolve().parents[1] / "app" / "dist-e2e"
    if not (quiz.WEB / "index.html").exists():
        sys.exit("app/dist-e2e manque : npm run build:e2e dans app/")
    db = Path(tempfile.mkdtemp(prefix="surprise-e2e-")) / "e2e.db"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), quiz.make_handler(db, checks=0))
    print(f"Site des tests : http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
