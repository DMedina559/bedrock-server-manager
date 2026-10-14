# Backend architecture and documentation

The application context composes storage, server management, plugins, events and web resources. API modules form the operation boundary and validate typed request/response contracts. Core components should receive the capabilities they need rather than the whole application context.

## Choose a boundary

| Work | Entry point |
|---|---|
| HTTP integration | Running OpenAPI schema and HTTP routes |
| Plugin integration | `PluginBase`, typed `self.api` and owned event capabilities |
| Backend contribution | Internal Python API/class/core references |
| Event transport | Standalone event subsystem with transport observers |
| Web process control | Web runtime and FastAPI lifespan |

Core publishes through the event subsystem without importing HTTP API machinery. Before-operation hooks can affect operation execution; notification observers report delivery failures without cancelling mutations. Runtime cleanup drains work and releases plugin/transport ownership before disposing storage.

## Maintain documentation

Use native Sphinx/reStructuredText docstrings. Write a short purpose sentence and add `:param name:`, `:returns:`, `:yields:`, `:raises Error:` or `:ivar name:` only where they explain a meaningful contract. Keep annotated types in signatures; document units, ownership, side effects and failure semantics when relevant.

Keep tutorials and extended examples in these guides. Update generated plugin API/event references when registered contracts change, and verify HTTP examples against exported OpenAPI. Documentation for the development branch can differ from released packages.

See the repository's `CONTRIBUTING.md` for formatting, hooks and test isolation requirements. Build the Sphinx documentation after editing directives, links or docstrings; passing Python tests alone does not validate rendered documentation.
