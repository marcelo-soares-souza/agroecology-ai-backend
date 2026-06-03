import asyncio
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
        if getattr(self, "_initialized", False):
            return
        self._initialized: bool = True
        self._status_lock = threading.Lock()
        self.status: str = "idle"
        self.chunks_indexed: int = 0
        self.error: str | None = None
        self.current_run_id: str | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        with self._status_lock:
            if self.status == "processing":
                return False
            self.status = "processing"
            self.chunks_indexed = 0
            self.error = None
            self.current_run_id = None

        self._thread = threading.Thread(target=self._run_ingest, daemon=True)
        self._thread.start()
        return True

    def _run_ingest(self) -> None:
        from .database import insert_ingestion_run, update_ingestion_run
        from .ingest import ingest_all

        try:
            run = asyncio.run(insert_ingestion_run())
            run_id = run["id"]
            with self._status_lock:
                self.current_run_id = run_id

            _table, count = ingest_all()

            asyncio.run(
                update_ingestion_run(run_id, status="done", chunks_indexed=count)
            )
            with self._status_lock:
                self.status = "done"
                self.chunks_indexed = count
                self.error = None
        except Exception as e:
            error_msg = str(e)
            with self._status_lock:
                self.status = "error"
                self.chunks_indexed = 0
                self.error = error_msg
                if self.current_run_id:
                    run_id = self.current_run_id
                else:
                    return
            try:
                asyncio.run(
                    update_ingestion_run(run_id, status="error", error=error_msg)
                )
            except Exception:
                pass

    def to_dict(self) -> dict:
        with self._status_lock:
            result: dict = {
                "status": self.status,
            }
            if self.status == "done":
                result["chunks_indexed"] = self.chunks_indexed
            elif self.status == "error":
                result["error"] = self.error
            if self.current_run_id:
                result["run_id"] = self.current_run_id
            return result


ingest_state = IngestState()
