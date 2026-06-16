import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haloheads.schema import image_hash
from haloheads.storage import get_storage
from haloheads.store import get_store


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Stage pending carnage-report photos locally so Claude Code can read them."
    )
    parser.add_argument("--all", action="store_true", dest="reanalyze")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--stage-dir", default="./.localdata/inbox")
    args = parser.parse_args(argv)

    storage = get_storage()
    store = get_store()
    inbox = Path(args.stage_dir)
    inbox.mkdir(parents=True, exist_ok=True)

    keys = storage.list_pending()
    if args.limit is not None:
        keys = keys[: args.limit]

    manifest = []
    skipped = 0
    for key in keys:
        data = storage.read(key)
        h = image_hash(data)
        if store.match_exists(h) and not args.reanalyze:
            storage.move(key, "analyzed/")
            skipped += 1
            continue
        name = key.split("/")[-1]
        path = inbox / name
        path.write_bytes(data)
        manifest.append({
            "key": key,
            "path": str(path),
            "image_hash": h,
            "uploaded_at": storage.meta(key).get("uploaded_at"),
            "map": storage.meta(key).get("map"),
        })

    (inbox / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    print(f"staged {len(manifest)} image(s) to {inbox}, {skipped} already-known", file=sys.stderr)
    return manifest


if __name__ == "__main__":
    main()
