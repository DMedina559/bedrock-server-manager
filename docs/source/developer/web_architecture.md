# Web composition and package boundaries

`web.app.create_web_app` assembles the application without starting services. Keep request processing and runtime behavior in their owning modules:

| Concern | Module |
|---|---|
| Startup and shutdown | `web.lifespan` |
| Sanitized HTTP exception envelopes | `web.errors` |
| Middleware order and CORS | `web.middleware.configure` |
| Shutdown mutation admission | `web.middleware.lifecycle` |
| Request identity, setup, ingress | `web.middleware.auth`, `setup`, `ingress` |
| Frontend/theme static mounts | `web.static` |
| Windows SCM web host | `web.windows_service` |

Middleware executes ingress first, followed by CORS, identity, setup, and shutdown admission. Preserve this order when adding a layer. Static mounts handle ingress prefixes, but are ASGI applications rather than HTTP middleware.

Core system helpers manage operating-system services without importing the web runtime. The Windows web-service host belongs to `web`; the CLI composes that host when running under the Windows service dispatcher.

Metrics observations live in `services.metrics_models`, and revision metadata lives in `state_revision`. API modules wrap or re-export these contracts so service code does not depend on HTTP/plugin API types.

Within `diagnostics`, `composition` wires application providers, `health` evaluates evidence, `activity` bounds event details and recent counters, `comparison` compares snapshots, `sampling` owns optional periodic health history, and `history` manages independent database persistence. `service` coordinates these components and supplies narrow callbacks to application services.
