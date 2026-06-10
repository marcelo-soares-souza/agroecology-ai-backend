from __future__ import annotations

from dataclasses import dataclass

from src.shared.config import check_schema_version


@dataclass
class SchemaStatus:
    ok: bool
    expected: str
    actual: str


class GetSchemaStatus:
    def execute(self) -> SchemaStatus:
        ok, expected, actual = check_schema_version()
        return SchemaStatus(ok=ok, expected=expected, actual=actual)
