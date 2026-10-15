# WebSocket Implementation

This document provides an overview of the WebSocket implementation in the Bedrock Server Manager, covering backend (server-side) components.

The backend WebSocket implementation is built using FastAPI and is divided into two main components: a WebSocket router and a connection manager.

## WebSocket Router

The WebSocket router is defined in `src/bedrock_server_manager/web/routers/websocket.py`. It is responsible for the following:

-   **Endpoint**: Creates a WebSocket endpoint at `/ws`.
-   **Authentication**: Authenticates the user on the first message payload. The client must send an authentication message within 5 seconds of connecting, containing their JWT access token (e.g., `{"action": "authenticate", "token": "eyJhb..."}`).
-   **Message Handling**: Listens for incoming JSON messages from the client. After authentication, supported actions include `subscribe`, `unsubscribe`, `request`, and `request_data`.
-   **Connection Management**: Hands off the connection and subscription management to the `ConnectionManager`.

## Connection Manager & Plugin Messaging API

The `ConnectionManager` is a class defined in `src/bedrock_server_manager/web/websocket_manager.py`. It is the core of the backend WebSocket implementation and is responsible for the following:

-   **Connection Tracking**: Keeps track of all active WebSocket connections and their authenticated `UserResponse` identity (`user.username`, `user.role`, `user.id`).
-   **Topic-Based Subscriptions**: Manages which clients are subscribed to which topics.
-   **Message Broadcasting**: Provides methods for sending messages to a single client, all clients subscribed to a specific topic, or all clients for a specific user.
-   **Data Provider Registration**: Allows plugins to register real-time topic data providers to handle client request-response messages.

Plugins use typed requests with `self.api.websocket`; provider registration belongs to owned runtime capabilities:

```python
await self.api.websocket.websocket_broadcast({"topic": "my-plugin:status", "data": {"connected": True}})
await self.api.websocket.websocket_send_to_user({"username": "admin", "data": {"message": "Ready"}})
await self.api.runtime.register_data_provider("my-plugin:status", handler)
```

See the generated [WebSocket API reference](../plugins/api/websocket.md) for exact request fields and delivery results. Providers enforce access to their own data.

## Request / Response Messaging

Clients can request data from real-time topics or plugin-registered data providers by sending a request payload over `/ws`:

```json
{
    "action": "request",
    "topic": "server-status",
    "data": { "server_name": "my_server" },
    "request_id": "req-101"
}
```

The server routes the request to the registered data provider for `topic`. Handlers can accept `topic`, `data`, `client_id`, and `user` (containing `user.role` like `"admin"` or `"user"`).

The server responds directly to the requesting client:

```json
{
    "status": "success",
    "type": "response",
    "topic": "server-status",
    "request_id": "req-101",
    "data": {
        "server_name": "my_server",
        "running": true,
        "players_online": 3
    }
}
```

### Role-Based Access in Data Providers
Because `user` is passed to the data provider callback, handlers can verify permissions based on `user.role`:

```python
async def admin_status_provider(topic, data, user):
    if user.role != "admin":
        raise PermissionError("Admin access required")
    return {"admin_metrics": ...}
```

## Wildcard Subscription

Clients can subscribe to the wildcard topic `*`. A client subscribed to `*` will receive **all** broadcast messages sent to any specific topic. This is useful for monitoring tools or dashboards that need a global view of system activity.

If a client is subscribed to both a specific topic (e.g., `event:server_start`) and the wildcard `*`, the system ensures the client only receives the message once.

## Architecture

1.  A client connects to the `/ws` endpoint (e.g., `ws://<host>:<port>/ws`).
2.  The client immediately sends an authentication message: `{"action": "authenticate", "token": "<your_access_token>"}`.
3.  The `websocket_router` authenticates the user using the provided token and passes the connection to the `ConnectionManager`.
4.  The client sends a `subscribe` message to a topic.
5.  The `websocket_router` calls the `ConnectionManager` to subscribe the client to the topic.
6.  When an event occurs on the server (e.g., the server status changes), the `ConnectionManager` is used to broadcast a message to all clients subscribed to the relevant topic.

## Available Topics

The following WebSocket topics are available for subscription:

### Event Topics

Event topics broadcast a message when a specific event occurs on the server. The topic name is in the format `event:{event_name}`.

See the generated [event catalog](../plugins/plugin_events.md) for current names and payloads. Only public event declarations are published; plugin listeners and WebSocket subscriptions have different cancellation capabilities.

### Resource Monitor Topics

Resource monitor topics broadcast resource usage information for a specific server. The topic name is in the format `resource-monitor:{server_name}`. Replace `{server_name}` with the name of the server you want to monitor.

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

The former bundled benchmark plugin is replaced by this core service. Remove any separately installed copy of `benchmark_plugin.py` to avoid duplicate sampling and its old plugin page.
