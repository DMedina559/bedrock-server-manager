# WebSocket Implementation

This document provides an overview of the WebSocket implementation in the Bedrock Server Manager, covering backend (server-side) components.

The backend WebSocket implementation is built using FastAPI and is divided into two main components: a WebSocket router and a connection manager.

### WebSocket Router

The WebSocket router is defined in `src/bedrock_server_manager/web/routers/websocket_router.py`. It is responsible for the following:

-   **Endpoint**: Creates a WebSocket endpoint at `/ws`.
-   **Authentication**: Uses a dependency to authenticate the user before establishing a connection.
-   **Message Handling**: Listens for incoming JSON messages from the client. These messages are expected to have an `action` (`subscribe` or `unsubscribe`) and a `topic`.
-   **Connection Management**: Hands off the connection and subscription management to the `ConnectionManager`.

### Connection Manager

The `ConnectionManager` is a class defined in `src/bedrock_server_manager/web/websocket_manager.py`. It is the core of the backend WebSocket implementation and is responsible for the following:

-   **Connection Tracking**: Keeps track of all active WebSocket connections.
-   **Topic-Based Subscriptions**: Manages which clients are subscribed to which topics.
-   **Message Broadcasting**: Provides methods for sending messages to a single client, all clients subscribed to a specific topic, or all clients for a specific user.

### Wildcard Subscription

Clients can subscribe to the wildcard topic `*`. A client subscribed to `*` will receive **all** broadcast messages sent to any specific topic. This is useful for monitoring tools or dashboards that need a global view of system activity.

If a client is subscribed to both a specific topic (e.g., `event:server_start`) and the wildcard `*`, the system ensures the client only receives the message once.

### Architecture

1.  A client connects to the `/ws` endpoint.
2.  The `websocket_router` authenticates the user.
3.  The `websocket_router` passes the connection to the `ConnectionManager`.
4.  The client sends a `subscribe` message to a topic.
5.  The `websocket_router` calls the `ConnectionManager` to subscribe the client to the topic.
6.  When an event occurs on the server (e.g., the server status changes), the `ConnectionManager` is used to broadcast a message to all clients subscribed to the relevant topic.

## Available Topics

The following WebSocket topics are available for subscription:

### Event Topics

Event topics broadcast a message when a specific event occurs on the server. The topic name is in the format `event:{event_name}`.

-   `event:before_addon_import`
-   `event:after_addon_import`
-   `event:before_backup`
-   `event:after_backup`
-   `event:before_restore`
-   `event:after_restore`
-   `event:before_prune_backups`
-   `event:after_prune_backups`
-   `event:before_players_add`
-   `event:after_players_add`
-   `event:before_player_db_scan`
-   `event:after_player_db_scan`
-   `event:before_server_start`
-   `event:after_server_start`
-   `event:before_server_stop`
-   `event:after_server_stop`
-   `event:before_command_send`
-   `event:after_command_send`
-   `event:before_allowlist_change`
-   `event:after_allowlist_change`
-   `event:before_server_install`
-   `event:after_server_install`
-   `event:before_server_update`
-   `event:after_server_update`
-   `event:before_autostart_change`
-   `event:after_autostart_change`
-   `event:after_server_statuses_updated`
-   `event:before_web_server_start`
-   `event:after_web_server_start`
-   `event:before_web_server_stop`
-   `event:after_web_server_stop`
-   `event:before_world_export`
-   `event:after_world_export`
-   `event:before_world_import`
-   `event:after_world_import`
-   `event:before_world_reset`
-   `event:after_world_reset`

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
        "status": "in_progress" | "success" | "error",
        "message": "Task is running." | "Task completed successfully." | "error message",
        "result": null | object,
        "username": "username"
    }
}
```

-   `type`: Indicates the type of message. For task updates, this is always `task_update`.
-   `topic`: The topic of the message. This follows the format `task:{task_id}`, where `{task_id}` is the unique identifier of the task.
-   `data`: An object containing details about the task:
    -   `status`: The current status of the task (`in_progress`, `success`, or `error`).
    -   `message`: A human-readable message describing the status.
    -   `result`: The result of the task, if any.
    -   `username`: The username of the user who initiated the task.
