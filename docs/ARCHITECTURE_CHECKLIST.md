# Architecture Checklist for Code Reviews

Use this checklist when adding or modifying code to prevent regressions toward layered coupling.

## General

- [ ] Business logic is NOT in adapters (HTTP routes, CLI handlers)
- [ ] Business logic is NOT in infrastructure (DB queries, file I/O, PDF parsing)
- [ ] Infrastructure code does NOT leak into application layer via imports
- [ ] No `asyncio.run()` in `src/application/` — async execution is the adapter's concern
- [ ] No `threading` in `src/application/` — thread management is the adapter's or bootstrap's concern

## Domain layer (`src/domain/`)

- [ ] No imports from `src/adapters/`, `src/application/`, `src/infrastructure/`, or `src/bootstrap/`
- [ ] Models are plain dataclasses (no ORM, no Pydantic, no FastAPI)
- [ ] Ports are ABCs with abstract methods only — no concrete dependencies
- [ ] Domain services depend only on ports and domain models

## Application layer (`src/application/`)

- [ ] Dependencies are injected via constructor (no `import` of concrete infrastructure classes)
- [ ] No direct filesystem access (`Path`, `open()`, `write_bytes()`, etc.)
- [ ] No direct PDF/image parsing (`import fitz`, `import PIL`, etc.)
- [ ] No imports from `src.adapters.*` or `src.bootstrap.*`
- [ ] Returns typed DTOs or domain models — no raw `dict`
- [ ] Raises `ValueError` or custom exceptions for business errors (not `HTTPException`)

## Infrastructure layer (`src/infrastructure/`)

- [ ] Implements domain ports — no direct exposure to application
- [ ] All resources (pools, connections, file handles) have proper `close()` cleanup
- [ ] No SQL string interpolation — always use parameterized queries

## Adapters (`src/adapters/`)

- [ ] REST routes only validate HTTP input, call use cases, serialize responses
- [ ] No business logic inline (no upload validation, no auth orchestration, no dedup logic)
- [ ] No direct import of infrastructure classes (repos, parsers, AI models) — go through container or dependencies
- [ ] Exception handlers catch `ValueError` from use cases and convert to `HTTPException`

## Bootstrap (`src/bootstrap/`)

- [ ] All dependencies wired through `Container` — no module-level lazy singletons
- [ ] `Container.init()` is idempotent (safe to call multiple times)
- [ ] `Container.start()` is idempotent
- [ ] `Container.shutdown()` closes **all** resources and calls `reset()`
- [ ] `reset()` nulls all references (preventing stale object access after shutdown)
- [ ] Entry points (`main.py`, `server.py`, `chat.py`) use the same `Container` for consistency

## Entry points

- [ ] `main.py` (CLI): calls `asyncio.run(init_services())` → use case → `asyncio.run(shutdown_services())`
- [ ] `backend/server.py` (ASGI): wraps FastAPI app with `ProxyHeadersMiddleware`
- [ ] `chat.py` (interactive): same init/shutdown pattern as CLI

## New use cases

- [ ] Follows the existing pattern: constructor injection → `execute()` method → typed return DTO
- [ ] Wired in `Container._create_use_cases()`
- [ ] Getter added to `src/adapters/rest/dependencies.py` (if used from REST)
- [ ] Tests cover happy path and error cases
