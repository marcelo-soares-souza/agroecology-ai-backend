import threading


class IngestState:
    _instance: "IngestState | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "IngestState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._status_lock = threading.Lock()
        self.status: str = "idle"
        self.chunks_indexed: int = 0
        self.error: str | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        with self._status_lock:
            if self.status == "processing":
                return False
            self.status = "processing"
            self.chunks_indexed = 0
            self.error = None

        self._thread = threading.Thread(target=self._run_ingest, daemon=True)
        self._thread.start()
        return True

    def _run_ingest(self) -> None:
        from .ingest import ingest_all

        try:
            _table, count = ingest_all()
            with self._status_lock:
                self.status = "done"
                self.chunks_indexed = count
                self.error = None
        except Exception as e:
            with self._status_lock:
                self.status = "error"
                self.chunks_indexed = 0
                self.error = str(e)

    def to_dict(self) -> dict:
        with self._status_lock:
            result = {"status": self.status}
            if self.status == "done":
                result["chunks_indexed"] = self.chunks_indexed
            elif self.status == "error":
                result["error"] = self.error
            return result


ingest_state = IngestState()
