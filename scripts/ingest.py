import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haloheads.docs import build_docs
from haloheads.schema import image_hash, validate_report
from haloheads.storage import get_storage
from haloheads.store import get_store


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Ingest Claude Code's extracted carnage reports into the store."
    )
    parser.add_argument("--reports", required=True, help="JSON file mapping image key -> carnage report dict.")
    parser.add_argument("--manifest", default="./.localdata/inbox/manifest.json")
    args = parser.parse_args(argv)

    storage = get_storage()
    store = get_store()
    now_iso = datetime.now(timezone.utc).isoformat()

    reports = json.loads(Path(args.reports).read_text())
    manifest = {m["key"]: m for m in json.loads(Path(args.manifest).read_text())}

    n_new = 0
    n_players = 0
    n_skipped = 0
    for key, report_dict in reports.items():
        report = validate_report(report_dict)
        info = manifest.get(key, {})
        h = info.get("image_hash") or image_hash(storage.read(key))
        if store.match_exists(h):
            n_skipped += 1
            continue
        match, players = build_docs(
            report,
            match_id=uuid4().hex,
            source_image=key,
            img_hash=h,
            uploaded_at=info.get("uploaded_at") or now_iso,
            analyzed_at=now_iso,
        )
        store.add_match(match, players)
        try:
            storage.move(key, "analyzed/")
        except Exception:
            pass
        n_new += 1
        n_players += len(players)

    print(f"ingested {n_new} match(es), {n_players} player rows, {n_skipped} already-known")


if __name__ == "__main__":
    main()
