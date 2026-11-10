# Real-time WebSockets and log streaming

BSM exposes a single multiplexed WebSocket endpoint at `/ws` for live server telemetry, application metrics, log streaming, background task progress, and event notifications.

## Connecting and authenticating

1. Open a WebSocket connection to `ws://<host>:<port>/ws` (or `wss://<host>/ws` behind TLS).
2. Authenticate on the **first message** within **5 seconds** of connecting (otherwise the connection is closed with code `1008`):
   - **Bearer / integration token (`bsm_it_...`):**
     ```json
     {"action": "authenticate", "token": "<jwt_or_bsm_it_token>"}
     ```
   - **Same-origin browser session (HttpOnly cookie):**
     ```json
     {"action": "authenticate"}
     ```
3. Upon successful authentication, the server replies with `{"status": "authenticated"}`.
4. Subscribe or unsubscribe to topics at any time:
   ```json
   {"action": "subscribe", "topic": "resource-monitor:survival"}
   {"action": "unsubscribe", "topic": "resource-monitor:survival"}
   ```

## Available topics

| Topic pattern | Required permission | Payload `type` | Description |
|---|---|---|---|
| `event:<event_name>` / `ws_event:<event_name>` | Authenticated (server-scoped events filter by `servers:read` on `server_name`) | `event` | Real-time notifications for public application and server lifecycle events (see [Event catalog](../plugins/plugin_events.md)) |
| `resource-monitor:<server_name>` | `servers:read` on `<server_name>` | `resource_update` | Per-server process CPU, memory, PID, and uptime samples |
| `application-metrics` | `system:info` | `resource_update` | Host and BSM process CPU, memory, disk I/O, network rates, and event-loop delay (`MetricsSample`) |
| `server_log:<server_name>` | `servers:logs` on `<server_name>` | `server_log` | Live stdout/console log lines for `<server_name>` (initial snapshot + incremental lines) |
| `app_log` (or `app_logs`) | `application:logs` | `app_log` | Live BSM application log lines (initial snapshot + incremental lines) |
| `task:<task_id>` | Automatic for task owner (or `admin`) | `task_update` | Background task status, stage, percentage, and completion updates |
| `*` (wildcard) | Filtered per message by the connection's live permissions | Varies | Receives all broadcast topics that the authenticated user is authorized to read (deduplicated if also subscribed to a specific topic) |

### Log history over HTTP (`GET /api/logs/history`)

Before or alongside subscribing to `server_log:<server_name>` or `app_log`, clients can paginate historical log lines with `GET /api/logs/history`:

- Query parameters: `source=server` (requires `server_name` and `servers:logs`) or `source=application` (requires `application:logs`), `limit` (`1`–`1000`, default `400`), and optional `before` cursor for scrolling backward through rotated `.log` files.

### Control frames and connection lifecycle

When an account's role, server assignments, or session validity changes while connected:

- **`access_changed` / `policy_changed`:** Sent to affected connections when permissions or per-server grants change; unauthorized topic subscriptions (such as `resource-monitor:<server>` or `server_log:<server>`) are automatically revoked.
- **Close code `1008` (Policy Violation):** Sent when authentication fails, times out, or the backing session/user is disabled or revoked.
- **Close code `1001` (Going Away):** Sent during graceful BSM web server shutdown.
- **Outbound queue limit (`web.outbound_queue_limit`):** Outbound sends are serialized per client with a bounded queue (default `64` messages, configurable from `8` to `1024`). If a slow client falls behind, the newest excess send is dropped rather than blocking other clients.

## Request / response data providers

Clients can query registered real-time data providers over `/ws` using `action: "request"` (or `"request_data"`):

```json
{
    "action": "request",
    "topic": "my_plugin:status",
    "data": {"server_name": "survival"},
    "request_id": "req-101"
}
```

The server invokes the provider registered for `topic` and replies directly to the requesting connection:

```json
{
    "status": "success",
    "type": "response",
    "topic": "my_plugin:status",
    "request_id": "req-101",
    "data": {"connected": true}
}
```

Plugin authors register custom topic providers with `@data_provider("my_plugin:status")` (or `@websocket_provider`) on `PluginBase` and broadcast messages with `self.api.websocket.websocket_broadcast` or `websocket_send_to_user`. Because `@data_provider` registers the topic string verbatim, prefix plugin topics with `<plugin_name>:`. See [Write a plugin](../developer/plugins/introduction.md#diagnostic-and-websocket-data-providers) and the [WebSocket API reference](../plugins/api/websocket.md).

### Task Manager Topics

The Task Manager is responsible for handling background tasks and notifying the user of their progress. Unlike event topics or resource monitor topics, the client does not need to explicitly subscribe to task topics. Instead, the server automatically pushes updates to the user who initiated the task.

The message structure for task updates is as follows:

```json
{
    "type": "task_update",
    "topic": "task:{task_id}",
    "data": {
        "id": "task-id",
        "status": "running",
        "message": "Task is running.",
        "result": null,
        "error": null
    }
}
```

-   `type`: Indicates the type of message. For task updates, this is always `task_update`.
-   `topic`: The topic of the message. This follows the format `task:{task_id}`, where `{task_id}` is the unique identifier of the task.
-   `data`: An object containing details about the task:
    -   `status`: The current status of the task (`queued`, `running`, `completed`, `failed`, `cancelling`, or `cancelled`).
    -   `message`: A human-readable message describing the status.
    -   `result`: The result of the task, if any.
    -   `id`: The task ID used to poll its status.
    -   `error`: A safe structured error when the task fails, otherwise `null`.

## State ordering across HTTP and WebSockets

Core state messages include `epoch` (a backend-process UUID) and `revision`
(a positive, monotonically increasing, JavaScript-safe integer). Compare revisions
only for the same resource and epoch. Equal revisions describe the same captured
state and may be ignored as duplicates. An epoch change requires clearing ordering
watermarks and fetching fresh snapshots; UUID epochs are not sortable. A delayed
message from a retired connection must not switch the client back to its old epoch.

Task HTTP snapshots and `task_update.data` contain the same stored revision for
that task transition. Repeated polling does not advance it. Fleet HTTP responses
and each server entry, individual server summaries and running-status responses,
process-info HTTP responses, and `resource_update.data`
also carry revisions. Plugin event envelopes carry them at the top level, covering
server lifecycle and player changes without altering plugin callback arguments.

Observation revisions are reserved before asynchronous reads; event revisions are
reserved before plugin callbacks and socket delivery. A slow earlier read or
callback therefore cannot become newer merely because its response arrives later.
These are ordering tokens, not database transaction revisions: fleet reads are
not atomic snapshots of every server. Fields are optional in model constructors
for compatibility with existing producers, but the core paths above supply them.

The sequence is process-local and does not synchronize independent web workers.
A shared persistent revision authority would be required for a multi-process
state service. Arbitrary plugin WebSocket payloads and log streams are unchanged.


## Application performance metrics

Authenticated clients can read `GET /api/metrics` (`get_application_metrics`) or subscribe to `application-metrics`. The core application sampler publishes `resource_update` frames with a `MetricsSample` in `data`, including its `epoch` and `revision`. HTTP returns `latest`, `history`, `interval_seconds`, and `history_limit` using the same samples.

Samples are collected approximately every three seconds. The application keeps the latest 180 samples in memory; history resets on restart. Application CPU is process CPU and can exceed 100% across cores. Memory is measured in MiB (displayed as MB in the UI); host memory and host I/O describe the whole machine. Network and disk rates use KiB/s. First-sample rates and inaccessible measurements are null rather than fabricated zeros. Event-loop delay measures how late the sampler resumes after its scheduled sleep, not request latency.
