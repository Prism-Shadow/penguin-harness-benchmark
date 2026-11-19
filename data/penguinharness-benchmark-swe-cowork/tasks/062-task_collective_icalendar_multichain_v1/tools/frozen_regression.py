"""CLI compatibility entry point for the build-time frozen asset authenticator."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "environment"))

from regression_assets import (
    DEFAULTS, REVISION, SCHEMA, TEST_ROOT, main, object_id, require,
    tests_tree, tree_entries, verify_directory, verify_record,
)


if __name__ == "__main__":
    main()
