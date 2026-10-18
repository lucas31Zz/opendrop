import collections
import threading
import time


class RateLimiter:
    def __init__(self, max_requests: int = 60, window: int = 60):
        self._max = max_requests
        self._window = window
        self._requests: dict[str, collections.deque] = {}
        self._lock = threading.Lock()

    def allow(self, ip: str) -> bool:
        now = time.monotonic()
        with self._lock:
            if ip not in self._requests:
                self._requests[ip] = collections.deque()
            q = self._requests[ip]
            while q and now - q[0] > self._window:
                q.popleft()
            if len(q) >= self._max:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


limiter_general = RateLimiter(max_requests=120, window=60)
limiter_upload = RateLimiter(max_requests=10, window=60)
limiter_download = RateLimiter(max_requests=30, window=60)
# Slices of a chunked upload (offset>0): the per-minute budget is much
# higher than a new upload (128 MiB per slice at LAN speed can exceed
# limiter_upload's 10/min for a multi-gigabyte send), but still bounds
# token guessing on this path (applied before _check_token in do_POST).
limiter_part = RateLimiter(max_requests=240, window=60)
# Brute-force protection for the session code (6 characters).
limiter_session = RateLimiter(max_requests=5, window=60)
