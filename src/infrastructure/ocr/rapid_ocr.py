from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from src.domain.ports.ocr_port import OcrPort
from src.shared.config import OCR_DPI, OCR_ENABLED, OCR_MAX_WORKERS
from src.shared.logging_utils import log_event

if TYPE_CHECKING:
    from rapidocr_onnxruntime import RapidOCR

logger = logging.getLogger("agroecology.parsers")

_MAX_WORKERS_CAP = 8


class RapidOcrService(OcrPort):
    """OCR via RapidOCR (PaddleOCR models compiled to ONNX).

    The engine is initialized lazily on first use and kept per worker
    thread so pages can be recognized concurrently without sharing
    mutable inference state. If initialization fails, the service
    degrades silently (returns empty text) instead of breaking parsing.

    Note: the text-direction classifier is disabled (use_cls=False)
    because it misclassifies horizontal Latin crops as rotated 180
    degrees, which degrades recognition quality; text is recognized
    with the detector and recognizer only.
    """

    _disabled: bool = False
    _disabled_lock = threading.Lock()

    def __init__(self) -> None:
        self._thread_local: Any = threading.local()

    def ocr_images(self, images: list[bytes]) -> list[str]:
        if not images or not OCR_ENABLED:
            return ["" for _ in images]

        if RapidOcrService._disabled:
            return ["" for _ in images]

        max_workers = self._resolve_max_workers()
        if max_workers == 1 or len(images) == 1:
            serial_results: list[str] = []
            for image in images:
                try:
                    serial_results.append(self._recognize_one(image))
                except Exception as e:
                    log_event(
                        logger,
                        logging.WARNING,
                        "ocr_page_failed",
                        error=str(e),
                    )
                    serial_results.append("")
            return serial_results

        results: list[str | None] = [None] * len(images)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(self._recognize_one, image): index
                for index, image in enumerate(images)
            }
            for future in futures:
                index = futures[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    log_event(
                        logger,
                        logging.WARNING,
                        "ocr_page_failed",
                        error=str(e),
                    )
                    results[index] = ""

        return [result if result is not None else "" for result in results]

    def _recognize_one(self, image: bytes) -> str:
        engine = self._get_engine()
        if engine is None:
            return ""
        result, _ = engine(image, use_cls=False)
        if not result:
            return ""
        lines = [item[1] for item in result if len(item) >= 2 and item[1]]
        return "\n".join(lines)

    def _get_engine(self) -> RapidOCR | None:
        engine = getattr(self._thread_local, "engine", None)
        if engine is not None:
            return engine

        if RapidOcrService._disabled:
            return None

        try:
            from rapidocr_onnxruntime import RapidOCR

            engine = RapidOCR()
            angle_cls = getattr(engine, "use_angle_cls", None)
            if angle_cls is not None:
                engine.use_angle_cls = False
            use_cls = getattr(engine, "use_cls", None)
            if use_cls is not None:
                engine.use_cls = False
            self._thread_local.engine = engine
            log_event(
                logger,
                logging.INFO,
                "ocr_engine_initialized",
                dpi=OCR_DPI,
                max_workers=self._resolve_max_workers(),
            )
            return engine
        except Exception as e:
            with RapidOcrService._disabled_lock:
                RapidOcrService._disabled = True
            log_event(
                logger,
                logging.WARNING,
                "ocr_engine_init_failed_disabled",
                error=str(e),
            )
            return None

    def _resolve_max_workers(self) -> int:
        if OCR_MAX_WORKERS > 0:
            return OCR_MAX_WORKERS
        return min(max(1, os.cpu_count() or 2), _MAX_WORKERS_CAP)
