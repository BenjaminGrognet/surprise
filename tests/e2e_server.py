"""The site the browser tests drive (app/e2e, `npm run e2e` in app/): the app's web build for the local Supabase
(app/dist-e2e), and the API on the activities of the project's base (tests/prod_activities.py: read in production,
never written) for the next Friday, the day the app proposes, on a store of its own. Their images are the sites' own, a
kept evening's copied here; no booking engine asked, no Claude. Started by app/playwright.config.ts.

    uv run python tests/e2e_server.py --port 8011
"""

import argparse
import os
import sys
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import prod_activities  # noqa: E402
from surprise import images, parcours, quiz  # noqa: E402

# The accounts of the browser tests: the local Supabase (npm run db:start), never the project's.
LOCAL_ACCOUNTS = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def main() -> None:
    parser = argparse.ArgumentParser(description="Site des tests navigateur : l'app (dist-e2e) et l'API sur les activités de prod")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    os.environ.pop("ANTHROPIC_API_KEY", None)
    quiz.WEB = Path(__file__).resolve().parents[1] / "app" / "dist-e2e"
    if not (quiz.WEB / "index.html").exists():
        sys.exit("app/dist-e2e manque : npm run build:e2e dans app/")
    try:
        base = prod_activities.base()
    except LookupError as error:
        sys.exit(str(error))
    parcours.Base.load = classmethod(lambda cls, store: base)
    work = Path(tempfile.mkdtemp(prefix="surprise-e2e-"))
    images.DIRECTORY = work / "images"  # a kept evening's copies (parcours.keep_images), not in data/images
    server = ThreadingHTTPServer(("127.0.0.1", args.port), quiz.make_handler(work / "e2e.db", checks=0, accounts=LOCAL_ACCOUNTS))
    print(f"Site des tests : http://127.0.0.1:{args.port} ({len(base.items)} activités de prod)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
