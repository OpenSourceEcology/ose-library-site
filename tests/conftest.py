from __future__ import annotations

import sys
from pathlib import Path


LOCAL_LIBTOOLS = Path("/Users/cct/code/vcs-library")
if LOCAL_LIBTOOLS.is_dir() and str(LOCAL_LIBTOOLS) not in sys.path:
    sys.path.insert(0, str(LOCAL_LIBTOOLS))

