import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haloheads.docs import build_docs
from haloheads.extraction import get_extractor
from haloheads.schema import image_hash
from haloheads.storage import get_storage
from haloheads.store import get_store


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze pending Halo carnage-report images.")
    parser.add_argument("--dry-run", action="store_true", help="Extract and print without writing or moving.")
    parser.add_argument("--all", action="store_true", dest="reanalyze", help="Re-analyze even if image_hash already in store.")
    parser.add_argument("--image", metavar="PATH", help="Analyze a single local file instead of the bucket.")
    parser.add_argument("--limit", type=int, metavar="N", help="Cap how many pending images to process.")
    args = parser.parse_args(argv)

    now_iso = datetime.now(timezone.utc).isoformat()
    storage = get_storage()
    store = get_store()
    extract = get_extractor()

    if args.image:
        data = Path(args.image).read_bytes()
        h = image_hash(data)
        report = extract(data)
        match, players = build_docs(
            report,
            match_id=uuid4().hex,
            source_image=args.image,
            img_hash=h,
            uploaded_at=now_iso,
            analyzed_at=now_iso,
        )
        if args.dry_run:
            print(json.dumps(asdict(report), indent=2))
        else:
            store.add_match(match, players)
        print(f"analyzed {args.image}: {len(players)} player rows")
        return

    keys = storage.list_pending()
    if args.limit is not None:
        keys = keys[: args.limit]

    n_new = 0
    n_players = 0
    n_skipped = 0
    n_failed = 0

    for key in keys:
        data = storage.read(key)
        h = image_hash(data)

        if store.match_exists(h) and not args.reanalyze:
            storage.move(key, "analyzed/")
            n_skipped += 1
            continue

        try:
            report = extract(data)
        except Exception as e:
            print(f"error processing {key}: {e}")
            storage.move(key, "failed/")
            n_failed += 1
            continue

        meta = storage.meta(key)
        uploaded_at = meta.get("uploaded_at") or now_iso
        match, players = build_docs(
            report,
            match_id=uuid4().hex,
            source_image=key,
            img_hash=h,
            uploaded_at=uploaded_at,
            analyzed_at=now_iso,
        )

        if args.dry_run:
            print(json.dumps(asdict(report), indent=2))
            continue

        if store.game_exists(match["game_hash"]):
            storage.move(key, "analyzed/")
            n_skipped += 1
            continue

        store.add_match(match, players)
        storage.move(key, "analyzed/")
        n_new += 1
        n_players += len(players)

    print(
        f"analyzed {n_new} new image(s), {n_players} player rows, "
        f"{n_skipped} already-known, {n_failed} failed"
    )


if __name__ == "__main__":
    main()
