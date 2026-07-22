"""Live dashboard delivery is delegated to the Firebase synchronizer.

No local WebSocket route is exposed in Phase 10, preventing a second,
competing synchronization path.
"""
