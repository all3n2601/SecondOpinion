# Stack implementation references

Checked 2026-11-12 against installed packages, repository configuration, bundled Next.js docs, and official online references. Guidance below distinguishes existing behavior from implementation recommendations.

## Installed versions

| Component | Installed version | Evidence |
| --- | --- | --- |
| Next.js | 16.4.6 | `node_modules/next/package.json` |
| React / React DOM | 19.3.0 / 19.3.0 | Workspace dependency pins; React package inspected |
| TypeScript | 5.9.3 | `node_modules/typescript/package.json` |
| Tailwind CSS / Turbopack loader | 4.3.3 / 4.3.3 | Installed `tailwindcss` and `@tailwindcss/turbopack` package metadata |
| FastAPI | 0.162.5 | `.venv` distribution metadata |
| Pydantic | 2.14.3 | `.venv` distribution metadata |
| pandas | 3.1.1 | `.venv` distribution metadata |
| Uvicorn / python-multipart | 0.54.0 / 0.0.33 | `.venv` distribution metadata |
| Node.js / Python | 26.12.0 / 3.13.16 | Local runtimes |

These are the current environment, not guaranteed fresh-install resolutions. JavaScript has `package-lock.json`; Python uses version ranges in `pyproject.toml` and editable `-e .[dev]` via `requirements.txt`, without a Python lockfile. Pydantic is currently transitive through FastAPI. Declared runtime requirements are Node >=22 and Python >=3.11,<3.15.

## Next.js App Router and TypeScript

Read the installed docs before implementation; this repository explicitly requires that in `apps/web/AGENTS.md`. Sources read under `node_modules/next/dist/docs/`:

| Bundled document | Official reference | Practical guidance |
| --- | --- | --- |
| `01-app/01-getting-started/05-server-and-client-components.md` | [Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components) | Pages/layouts default to Server Components. Put state, upload controls, event handlers, and browser APIs behind a small `"use client"` boundary. Keep secrets server-side. |
| `01-app/01-getting-started/15-route-handlers.md` | [Route Handlers](https://nextjs.org/docs/app/getting-started/route-handlers) | Handlers use `app/**/route.ts` and Web Request/Response APIs. They are not cached by default. Add a handler only where a web-specific adapter is needed. |
| `01-app/03-api-reference/05-config/02-typescript.md` | [TypeScript](https://nextjs.org/docs/app/api-reference/config/typescript) | Use workspace TypeScript and generated Next types. Existing `npm run typecheck` runs `next typegen && tsc --noEmit`. TypeScript annotations alone do not validate API JSON at runtime. |
| `01-app/03-api-reference/05-config/01-next-config-js/rewrites.md` | [Rewrites](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites) | External rewrites proxy requests while retaining the browser URL. Filesystem routes take precedence over the existing array-form rewrites; avoid overlapping `app/api` handlers. |

## API rewrite and ASGI root path

Existing `apps/web/next.config.ts` maps `/api/:path*` to `${API_ORIGIN}/:path*`, with default origin `http://127.0.0.1:8000`. Root npm API scripts start Uvicorn with `--root-path /api`.

- Browser `/api/health` → backend `/health`; FastAPI route decorators remain `/health` and `/variants`.
- `root_path` describes the externally stripped prefix for URL generation and OpenAPI; it does not replace the proxy or mean route decorators should gain another `/api` prefix. Use `/api/docs` and `/api/openapi.json` through Next. Direct backend Swagger UI can fail to load its schema because it expects the external prefix. [FastAPI: behind a proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)
- Keep `API_ORIGIN` as the backend origin without `/api` for this configuration. Production must run both services and provide a reachable backend origin; loopback only reaches the same host/container. Browser calls can use same-origin `/api/...`; server-side fetches should use an absolute backend URL. This is a deployment recommendation derived from the current rewrite.
- Verify proxy behavior with `/api/health`, `/api/variants`, and Swagger's schema request after deployment. These routes were inspected, not exercised as part of this documentation task.

## Tailwind CSS v4

Existing `apps/web/src/app/globals.css` uses `@import "tailwindcss"`; `next.config.ts` applies the installed `@tailwindcss/turbopack` CSS loader. The [official Next.js installation guide](https://tailwindcss.com/docs/installation/framework-guides/nextjs) describes a PostCSS integration. It is a reference for v4 CSS usage, not an exact description of this repository's loader configuration. Preserve the current integration unless intentionally migrating; do not mix in v3 setup instructions or install a second pipeline merely to match the guide.

## FastAPI uploads and Pydantic contracts

- Prefer `UploadFile` over a whole-body `bytes` parameter for datasets: it exposes a spooled file and async read/seek/close operations. In a synchronous endpoint, `.file` provides the file-like object. `python-multipart` is already installed. File requests use multipart; accompanying metadata belongs in form fields, not a simultaneous JSON request body. [FastAPI: request files](https://fastapi.tiangolo.com/tutorial/request-files/)
- Recommended upload design: accept multipart report/data fields, enforce byte and decompressed-size limits, validate expected release filenames/content, stage files in a request-scoped directory, and clean up afterward. Never use an untrusted upload filename as an output path. These are proposed implementation constraints; no upload endpoint exists in the inspected API.
- Define request/response contracts with Pydantic v2 `BaseModel`; use `model_validate` for parsed data and `model_dump(mode="json")` for JSON-compatible values. Validation may coerce values; choose strict fields where coercion would hide invalid scientific inputs. Current health/variant endpoints already declare response models. [Pydantic: models](https://docs.pydantic.dev/latest/concepts/models/)

## Shared Python engine and pandas

Repository architecture: `second_opinion/` owns reusable calculations and release loading; `apps/api/app/main.py` is an HTTP adapter and `second_opinion/cli.py` is the CLI adapter. Both import the same installed Python package through the editable project. Keep audit logic out of React and endpoint handlers; have adapters translate transport inputs/errors and return explicit JSON-compatible contracts.

- Current `load_release()` in `second_opinion/release.py` requires five named TSV/TSV.GZ files and uses `pd.read_csv(..., sep="\t", low_memory=False)`. Extension-based gzip inference works for those paths; an uploaded file-like object should receive an explicit compression setting when appropriate. Use `dtype`/`usecols` and explicit missing-value rules when the dataset schema is established. `chunksize` enables incremental reads; `low_memory=False` alone does not make loading incremental. [pandas: read_csv](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html)
- Recommended: validate columns, identifiers, and join cardinality inside the shared engine; convert pandas/NumPy values and missing values into the API contract before serialization. File presence checks alone do not establish scientific validity.
- Blocking pandas work should not execute directly inside an async handler. FastAPI runs normal `def` endpoints in a thread pool; a normal helper called from `async def` is not automatically offloaded. Long CPU-heavy audits may need separate worker processes/jobs. [FastAPI: concurrency](https://fastapi.tiangolo.com/async/)
- Current limitation: the CLI loads a release then raises `NotImplementedError`; claim extraction, checks, and audit export remain unbuilt. Treat this document as an implementation reference, not evidence of a completed auditing pipeline.
