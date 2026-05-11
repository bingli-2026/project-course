"""In-process live state for the current monitoring task.

The web backend and the feature-extraction pipeline run inside the same Python
process on the Orange Pi. The pipeline calls `publish_window(...)` to push a
fresh `WindowSample` into the in-memory buffer; HTTP handlers read from the
same buffer to answer dashboard polls. Optionally the pipeline calls
`record_sync_quality(...)` to update offset/drift/aligned-ratio metrics.

Window samples for the current task are also written through to SQLite so that
a) polling clients can ask for any past window of the active task, and b) the
history page can replay completed tasks after a restart.
"""

from project_course.api.live.state import (
    LIVE_STATE,
    LiveState,
    finish_task,
    get_active_task,
    get_recent_windows,
    publish_window,
    record_sync_quality,
    start_task,
)

__all__ = [
    "LIVE_STATE",
    "LiveState",
    "finish_task",
    "get_active_task",
    "get_recent_windows",
    "publish_window",
    "record_sync_quality",
    "start_task",
]
