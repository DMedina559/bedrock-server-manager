# Available plugin APIs

> _Generated from registered core contracts._

---
This list contains all functions available to plugins via the `self.api` object.
For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.

## `addon.disable_addon`
```python
await self.api.addon.disable_addon(request: bedrock_server_manager.api.models.addon.DisableAddonRequest)
```
- **Async (Requires await):** Yes

- **Description:** Disables an active addon for a server's active world, preserving files.

- **Returns:** `DisableAddonResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import DisableAddonRequest
payload = {...}  # Supply required request fields below.
request = DisableAddonRequest(**payload)
result = await self.api.addon.disable_addon(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "pack_type": {
      "enum": [
        "behavior",
        "resource"
      ],
      "title": "Pack Type",
      "type": "string"
    },
    "pack_uuid": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Pack Uuid",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "pack_uuid",
    "pack_type"
  ],
  "title": "DisableAddonRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "DisableAddonResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.DisableAddonRequest` | `REQUIRED` |

---


## `addon.enable_addon`
```python
await self.api.addon.enable_addon(request: bedrock_server_manager.api.models.addon.EnableAddonRequest)
```
- **Async (Requires await):** Yes

- **Description:** Enables a disabled addon for a server's active world.

- **Returns:** `EnableAddonResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import EnableAddonRequest
payload = {...}  # Supply required request fields below.
request = EnableAddonRequest(**payload)
result = await self.api.addon.enable_addon(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "pack_type": {
      "enum": [
        "behavior",
        "resource"
      ],
      "title": "Pack Type",
      "type": "string"
    },
    "pack_uuid": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Pack Uuid",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "pack_uuid",
    "pack_type"
  ],
  "title": "EnableAddonRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "EnableAddonResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.EnableAddonRequest` | `REQUIRED` |

---


## `addon.import_addon`
```python
await self.api.addon.import_addon(request: bedrock_server_manager.api.models.addon.ImportAddonRequest)
```
- **Async (Requires await):** Yes

- **Description:** Installs an addon to a specified Bedrock server.

- **Returns:** `ImportAddonResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ImportAddonRequest
payload = {...}  # Supply required request fields below.
request = ImportAddonRequest(**payload)
result = await self.api.addon.import_addon(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "addon_file_path": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Addon File Path",
      "type": "string"
    },
    "restart_only_on_success": {
      "default": true,
      "title": "Restart Only On Success",
      "type": "boolean"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "stop_start_server": {
      "default": true,
      "title": "Stop Start Server",
      "type": "boolean"
    }
  },
  "required": [
    "server_name",
    "addon_file_path"
  ],
  "title": "ImportAddonRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "ImportAddonResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.ImportAddonRequest` | `REQUIRED` |

---


## `addon.list_available_addons`
```python
await self.api.addon.list_available_addons(request: bedrock_server_manager.api.models.addon.ListAvailableAddonsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Lists available .mcaddon and .mcpack files from the content directory.

- **Returns:** `ListAvailableAddonsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ListAvailableAddonsRequest
payload = {}
request = ListAvailableAddonsRequest(**payload)
result = await self.api.addon.list_available_addons(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ListAvailableAddonsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "files": {
      "items": {
        "type": "string"
      },
      "title": "Files",
      "type": "array"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "files"
  ],
  "title": "ListAvailableAddonsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.ListAvailableAddonsRequest` | `REQUIRED` |

---


## `addon.list_installed_addons`
```python
await self.api.addon.list_installed_addons(request: bedrock_server_manager.api.models.addon.ListInstalledAddonsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Lists all addons for a server's active world.

- **Returns:** `ListInstalledAddonsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ListInstalledAddonsRequest
payload = {'server_name': 'example'}
request = ListInstalledAddonsRequest(**payload)
result = await self.api.addon.list_installed_addons(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "ListInstalledAddonsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "InstalledAddon": {
      "additionalProperties": false,
      "properties": {
        "active_subpack": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Active Subpack"
        },
        "icon": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Icon"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Path"
        },
        "status": {
          "enum": [
            "ACTIVE",
            "INACTIVE",
            "ORPHANED"
          ],
          "title": "Status",
          "type": "string"
        },
        "subpacks": {
          "items": {
            "$ref": "#/$defs/Subpack"
          },
          "title": "Subpacks",
          "type": "array"
        },
        "uuid": {
          "title": "Uuid",
          "type": "string"
        },
        "version": {
          "items": {
            "type": "integer"
          },
          "title": "Version",
          "type": "array"
        }
      },
      "required": [
        "name",
        "uuid",
        "version",
        "status"
      ],
      "title": "InstalledAddon",
      "type": "object"
    },
    "InstalledAddons": {
      "additionalProperties": false,
      "properties": {
        "behavior_packs": {
          "items": {
            "$ref": "#/$defs/InstalledAddon"
          },
          "title": "Behavior Packs",
          "type": "array"
        },
        "resource_packs": {
          "items": {
            "$ref": "#/$defs/InstalledAddon"
          },
          "title": "Resource Packs",
          "type": "array"
        }
      },
      "title": "InstalledAddons",
      "type": "object"
    },
    "Subpack": {
      "additionalProperties": false,
      "properties": {
        "folder_name": {
          "title": "Folder Name",
          "type": "string"
        },
        "memory_tier": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Memory Tier"
        },
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Name"
        }
      },
      "required": [
        "folder_name"
      ],
      "title": "Subpack",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "addons": {
      "$ref": "#/$defs/InstalledAddons"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "addons"
  ],
  "title": "ListInstalledAddonsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.ListInstalledAddonsRequest` | `REQUIRED` |

---


## `addon.reorder_addons`
```python
await self.api.addon.reorder_addons(request: bedrock_server_manager.api.models.addon.ReorderAddonsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reorder the active addons for a server's active world.

- **Returns:** `ReorderAddonsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ReorderAddonsRequest
payload = {...}  # Supply required request fields below.
request = ReorderAddonsRequest(**payload)
result = await self.api.addon.reorder_addons(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "pack_type": {
      "enum": [
        "behavior",
        "resource"
      ],
      "title": "Pack Type",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "uuids": {
      "items": {
        "minLength": 1,
        "pattern": ".*\\S.*",
        "type": "string"
      },
      "title": "Uuids",
      "type": "array"
    }
  },
  "required": [
    "server_name",
    "uuids",
    "pack_type"
  ],
  "title": "ReorderAddonsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "ReorderAddonsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.addon.ReorderAddonsRequest` | `REQUIRED` |

---


## `allowlist.add_to_allowlist`
```python
await self.api.allowlist.add_to_allowlist(request: bedrock_server_manager.api.models.allowlist.AddToAllowlistRequest)
```
- **Async (Requires await):** Yes

- **Description:** Adds a list of players to the server's allowlist.

- **Returns:** `AddToAllowlistResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import AddToAllowlistRequest
payload = {...}  # Supply required request fields below.
request = AddToAllowlistRequest(**payload)
result = await self.api.allowlist.add_to_allowlist(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "$defs": {
    "AllowlistPlayer": {
      "additionalProperties": false,
      "properties": {
        "ignoresPlayerLimit": {
          "default": false,
          "title": "Ignoresplayerlimit",
          "type": "boolean"
        },
        "name": {
          "minLength": 1,
          "pattern": ".*\\S.*",
          "title": "Name",
          "type": "string"
        },
        "xuid": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Xuid"
        }
      },
      "required": [
        "name"
      ],
      "title": "AllowlistPlayer",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "new_players_data": {
      "items": {
        "$ref": "#/$defs/AllowlistPlayer"
      },
      "title": "New Players Data",
      "type": "array"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "new_players_data"
  ],
  "title": "AddToAllowlistRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "added_count": {
      "minimum": 0,
      "title": "Added Count",
      "type": "integer"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "added_count"
  ],
  "title": "AddToAllowlistResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.allowlist.AddToAllowlistRequest` | `REQUIRED` |

---


## `allowlist.get_allowlist`
```python
await self.api.allowlist.get_allowlist(request: bedrock_server_manager.api.models.allowlist.GetAllowlistRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the current allowlist for a given server.

- **Returns:** `GetAllowlistResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetAllowlistRequest
payload = {'server_name': 'example'}
request = GetAllowlistRequest(**payload)
result = await self.api.allowlist.get_allowlist(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "GetAllowlistRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "AllowlistPlayer": {
      "additionalProperties": false,
      "properties": {
        "ignoresPlayerLimit": {
          "default": false,
          "title": "Ignoresplayerlimit",
          "type": "boolean"
        },
        "name": {
          "minLength": 1,
          "pattern": ".*\\S.*",
          "title": "Name",
          "type": "string"
        },
        "xuid": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Xuid"
        }
      },
      "required": [
        "name"
      ],
      "title": "AllowlistPlayer",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "players": {
      "items": {
        "$ref": "#/$defs/AllowlistPlayer"
      },
      "title": "Players",
      "type": "array"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "players"
  ],
  "title": "GetAllowlistResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.allowlist.GetAllowlistRequest` | `REQUIRED` |

---


## `allowlist.remove_from_allowlist`
```python
await self.api.allowlist.remove_from_allowlist(request: bedrock_server_manager.api.models.allowlist.RemoveFromAllowlistRequest)
```
- **Async (Requires await):** Yes

- **Description:** Remove a list of players from the server's allowlist.

- **Returns:** `RemoveFromAllowlistResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RemoveFromAllowlistRequest
payload = {...}  # Supply required request fields below.
request = RemoveFromAllowlistRequest(**payload)
result = await self.api.allowlist.remove_from_allowlist(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "player_names": {
      "items": {
        "minLength": 1,
        "pattern": ".*\\S.*",
        "type": "string"
      },
      "title": "Player Names",
      "type": "array"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "player_names"
  ],
  "title": "RemoveFromAllowlistRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "AllowlistRemovalDetails": {
      "additionalProperties": false,
      "properties": {
        "not_found": {
          "items": {
            "type": "string"
          },
          "title": "Not Found",
          "type": "array"
        },
        "removed": {
          "items": {
            "type": "string"
          },
          "title": "Removed",
          "type": "array"
        }
      },
      "required": [
        "removed",
        "not_found"
      ],
      "title": "AllowlistRemovalDetails",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "details": {
      "$ref": "#/$defs/AllowlistRemovalDetails"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "details"
  ],
  "title": "RemoveFromAllowlistResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.allowlist.RemoveFromAllowlistRequest` | `REQUIRED` |

---


## `application.get_all_servers_data`
```python
await self.api.application.get_all_servers_data(request: bedrock_server_manager.api.models.application.GetAllServersDataRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return status and version for all detected servers.

- **Returns:** `GetAllServersDataResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetAllServersDataRequest
payload = {}
request = GetAllServersDataRequest(**payload)
result = await self.api.application.get_all_servers_data(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetAllServersDataRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "FailureInfo": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "enum": [
            "validation_error",
            "not_found",
            "conflict",
            "forbidden",
            "unauthorized",
            "http_error",
            "operation_canceled",
            "invalid_server_name",
            "server_start_failed",
            "server_stop_failed",
            "server_error",
            "application_error",
            "internal_error",
            "unavailable",
            "operation_incomplete",
            "file_error",
            "storage_error",
            "configuration_error",
            "network_error",
            "system_error"
          ],
          "title": "Code",
          "type": "string"
        },
        "details": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Details",
          "type": "object"
        },
        "message": {
          "title": "Message",
          "type": "string"
        }
      },
      "required": [
        "code",
        "message"
      ],
      "title": "FailureInfo",
      "type": "object"
    },
    "JsonValue": {},
    "PlayerInfo": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "xuid": {
          "title": "Xuid",
          "type": "string"
        }
      },
      "required": [
        "name",
        "xuid"
      ],
      "title": "PlayerInfo",
      "type": "object"
    },
    "ResourceFailure": {
      "additionalProperties": false,
      "properties": {
        "error": {
          "$ref": "#/$defs/FailureInfo"
        },
        "resource": {
          "title": "Resource",
          "type": "string"
        }
      },
      "required": [
        "resource",
        "error"
      ],
      "title": "ResourceFailure",
      "type": "object"
    },
    "ServerSummary": {
      "additionalProperties": false,
      "properties": {
        "epoch": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Epoch"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "player_count": {
          "default": 0,
          "minimum": 0,
          "title": "Player Count",
          "type": "integer"
        },
        "players": {
          "items": {
            "$ref": "#/$defs/PlayerInfo"
          },
          "title": "Players",
          "type": "array"
        },
        "players_available": {
          "default": true,
          "title": "Players Available",
          "type": "boolean"
        },
        "revision": {
          "anyOf": [
            {
              "maximum": 9007199254740991,
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Revision"
        },
        "status": {
          "title": "Status",
          "type": "string"
        },
        "version": {
          "title": "Version",
          "type": "string"
        }
      },
      "required": [
        "name",
        "status",
        "version"
      ],
      "title": "ServerSummary",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "epoch": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Epoch"
    },
    "errors": {
      "items": {
        "$ref": "#/$defs/ResourceFailure"
      },
      "title": "Errors",
      "type": "array"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "revision": {
      "anyOf": [
        {
          "maximum": 9007199254740991,
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Revision"
    },
    "servers": {
      "items": {
        "$ref": "#/$defs/ServerSummary"
      },
      "title": "Servers",
      "type": "array"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "servers"
  ],
  "title": "GetAllServersDataResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.application.GetAllServersDataRequest` | `REQUIRED` |

---


## `application.get_system_and_app_info`
```python
self.api.application.get_system_and_app_info(request: bedrock_server_manager.api.models.application.GetSystemAndAppInfoRequest)
```
- **Async (Requires await):** No

- **Description:** Return basic system and application information.

- **Returns:** `GetSystemAndAppInfoResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetSystemAndAppInfoRequest
payload = {}
request = GetSystemAndAppInfoRequest(**payload)
result = self.api.application.get_system_and_app_info(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetSystemAndAppInfoRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "app_version": {
      "title": "App Version",
      "type": "string"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "os_type": {
      "title": "Os Type",
      "type": "string"
    },
    "splash_text": {
      "title": "Splash Text",
      "type": "string"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "os_type",
    "app_version",
    "splash_text"
  ],
  "title": "GetSystemAndAppInfoResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.application.GetSystemAndAppInfoRequest` | `REQUIRED` |

---


## `application.list_available_worlds`
```python
await self.api.application.list_available_worlds(request: bedrock_server_manager.api.models.application.ListAvailableWorldsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Lists available .mcworld files from the content directory.

- **Returns:** `ListAvailableWorldsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ListAvailableWorldsRequest
payload = {}
request = ListAvailableWorldsRequest(**payload)
result = await self.api.application.list_available_worlds(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ListAvailableWorldsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "files": {
      "items": {
        "type": "string"
      },
      "title": "Files",
      "type": "array"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "files"
  ],
  "title": "ListAvailableWorldsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.application.ListAvailableWorldsRequest` | `REQUIRED` |

---


## `backup_restore.backup_all`
```python
await self.api.backup_restore.backup_all(request: bedrock_server_manager.api.models.backup_restore.BackupAllRequest)
```
- **Async (Requires await):** Yes

- **Description:** Performs a full backup of the server's world and configuration files.

- **Returns:** `BackupAllResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import BackupAllRequest
payload = {'server_name': 'example'}
request = BackupAllRequest(**payload)
result = await self.api.backup_restore.backup_all(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "BackupAllRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "CompletedItem": {
      "additionalProperties": false,
      "properties": {
        "error": {
          "default": null,
          "title": "Error",
          "type": "null"
        },
        "outcome": {
          "const": "completed",
          "default": "completed",
          "title": "Outcome",
          "type": "string"
        },
        "path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Path"
        },
        "reason": {
          "default": null,
          "title": "Reason",
          "type": "null"
        }
      },
      "title": "CompletedItem",
      "type": "object"
    },
    "ComponentResults": {
      "additionalProperties": false,
      "properties": {
        "components": {
          "additionalProperties": {
            "discriminator": {
              "mapping": {
                "completed": "#/$defs/CompletedItem",
                "failed": "#/$defs/FailedItem",
                "skipped": "#/$defs/SkippedItem"
              },
              "propertyName": "outcome"
            },
            "oneOf": [
              {
                "$ref": "#/$defs/CompletedItem"
              },
              {
                "$ref": "#/$defs/SkippedItem"
              },
              {
                "$ref": "#/$defs/FailedItem"
              }
            ]
          },
          "title": "Components",
          "type": "object"
        },
        "outcome": {
          "default": "noop",
          "enum": [
            "completed",
            "partial",
            "failed",
            "noop"
          ],
          "title": "Outcome",
          "type": "string"
        }
      },
      "title": "ComponentResults",
      "type": "object"
    },
    "FailedItem": {
      "additionalProperties": false,
      "properties": {
        "error": {
          "$ref": "#/$defs/FailureInfo"
        },
        "outcome": {
          "const": "failed",
          "default": "failed",
          "title": "Outcome",
          "type": "string"
        },
        "path": {
          "default": null,
          "title": "Path",
          "type": "null"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason"
        }
      },
      "required": [
        "error"
      ],
      "title": "FailedItem",
      "type": "object"
    },
    "FailureInfo": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "enum": [
            "validation_error",
            "not_found",
            "conflict",
            "forbidden",
            "unauthorized",
            "http_error",
            "operation_canceled",
            "invalid_server_name",
            "server_start_failed",
            "server_stop_failed",
            "server_error",
            "application_error",
            "internal_error",
            "unavailable",
            "operation_incomplete",
            "file_error",
            "storage_error",
            "configuration_error",
            "network_error",
            "system_error"
          ],
          "title": "Code",
          "type": "string"
        },
        "details": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Details",
          "type": "object"
        },
        "message": {
          "title": "Message",
          "type": "string"
        }
      },
      "required": [
        "code",
        "message"
      ],
      "title": "FailureInfo",
      "type": "object"
    },
    "JsonValue": {},
    "SkippedItem": {
      "additionalProperties": false,
      "properties": {
        "error": {
          "default": null,
          "title": "Error",
          "type": "null"
        },
        "outcome": {
          "const": "skipped",
          "default": "skipped",
          "title": "Outcome",
          "type": "string"
        },
        "path": {
          "default": null,
          "title": "Path",
          "type": "null"
        },
        "reason": {
          "title": "Reason",
          "type": "string"
        }
      },
      "required": [
        "reason"
      ],
      "title": "SkippedItem",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "details": {
      "$ref": "#/$defs/ComponentResults"
    },
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "BackupAllResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.BackupAllRequest` | `REQUIRED` |

---


## `backup_restore.backup_config_file`
```python
await self.api.backup_restore.backup_config_file(request: bedrock_server_manager.api.models.backup_restore.BackupConfigFileRequest)
```
- **Async (Requires await):** Yes

- **Description:** Create a backup of a specific server configuration file.

- **Returns:** `BackupConfigFileResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import BackupConfigFileRequest
payload = {...}  # Supply required request fields below.
request = BackupConfigFileRequest(**payload)
result = await self.api.backup_restore.backup_config_file(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "file_to_backup": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "File To Backup",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "file_to_backup"
  ],
  "title": "BackupConfigFileRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "BackupConfigFileResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.BackupConfigFileRequest` | `REQUIRED` |

---


## `backup_restore.backup_world`
```python
await self.api.backup_restore.backup_world(request: bedrock_server_manager.api.models.backup_restore.BackupWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Create a backup of the server's world directory.

- **Returns:** `BackupWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import BackupWorldRequest
payload = {'server_name': 'example'}
request = BackupWorldRequest(**payload)
result = await self.api.backup_restore.backup_world(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "BackupWorldRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "BackupWorldResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.BackupWorldRequest` | `REQUIRED` |

---


## `backup_restore.list_backup_files`
```python
await self.api.backup_restore.list_backup_files(request: bedrock_server_manager.api.models.backup_restore.ListBackupFilesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Lists available backup files for a given server and type.

- **Returns:** `ListBackupFilesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ListBackupFilesRequest
payload = {...}  # Supply required request fields below.
request = ListBackupFilesRequest(**payload)
result = await self.api.backup_restore.list_backup_files(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "backup_type": {
      "enum": [
        "world",
        "properties",
        "allowlist",
        "permissions",
        "all"
      ],
      "title": "Backup Type",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "backup_type"
  ],
  "title": "ListBackupFilesRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "backups": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "additionalProperties": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "type": "object"
        }
      ],
      "title": "Backups"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "backups"
  ],
  "title": "ListBackupFilesResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.ListBackupFilesRequest` | `REQUIRED` |

---


## `backup_restore.prune_old_backups`
```python
await self.api.backup_restore.prune_old_backups(request: bedrock_server_manager.api.models.backup_restore.PruneOldBackupsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Prunes old backups for a server based on retention settings.

- **Returns:** `PruneOldBackupsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import PruneOldBackupsRequest
payload = {'server_name': 'example'}
request = PruneOldBackupsRequest(**payload)
result = await self.api.backup_restore.prune_old_backups(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "PruneOldBackupsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "CleanupResult": {
      "additionalProperties": false,
      "properties": {
        "deleted": {
          "items": {
            "type": "string"
          },
          "title": "Deleted",
          "type": "array"
        },
        "failures": {
          "additionalProperties": {
            "$ref": "#/$defs/FailureInfo"
          },
          "title": "Failures",
          "type": "object"
        },
        "outcome": {
          "default": "noop",
          "enum": [
            "completed",
            "partial",
            "failed",
            "noop"
          ],
          "title": "Outcome",
          "type": "string"
        },
        "retained": {
          "items": {
            "type": "string"
          },
          "title": "Retained",
          "type": "array"
        }
      },
      "title": "CleanupResult",
      "type": "object"
    },
    "FailureInfo": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "enum": [
            "validation_error",
            "not_found",
            "conflict",
            "forbidden",
            "unauthorized",
            "http_error",
            "operation_canceled",
            "invalid_server_name",
            "server_start_failed",
            "server_stop_failed",
            "server_error",
            "application_error",
            "internal_error",
            "unavailable",
            "operation_incomplete",
            "file_error",
            "storage_error",
            "configuration_error",
            "network_error",
            "system_error"
          ],
          "title": "Code",
          "type": "string"
        },
        "details": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Details",
          "type": "object"
        },
        "message": {
          "title": "Message",
          "type": "string"
        }
      },
      "required": [
        "code",
        "message"
      ],
      "title": "FailureInfo",
      "type": "object"
    },
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "result": {
      "$ref": "#/$defs/CleanupResult"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "PruneOldBackupsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.PruneOldBackupsRequest` | `REQUIRED` |

---


## `backup_restore.restore_all`
```python
await self.api.backup_restore.restore_all(request: bedrock_server_manager.api.models.backup_restore.RestoreAllRequest)
```
- **Async (Requires await):** Yes

- **Description:** Restores the server from the latest available backups.

- **Returns:** `RestoreAllResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RestoreAllRequest
payload = {'server_name': 'example'}
request = RestoreAllRequest(**payload)
result = await self.api.backup_restore.restore_all(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "stop_start_server": {
      "default": true,
      "title": "Stop Start Server",
      "type": "boolean"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "RestoreAllRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "CompletedItem": {
      "additionalProperties": false,
      "properties": {
        "error": {
          "default": null,
          "title": "Error",
          "type": "null"
        },
        "outcome": {
          "const": "completed",
          "default": "completed",
          "title": "Outcome",
          "type": "string"
        },
        "path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Path"
        },
        "reason": {
          "default": null,
          "title": "Reason",
          "type": "null"
        }
      },
      "title": "CompletedItem",
      "type": "object"
    },
    "ComponentResults": {
      "additionalProperties": false,
      "properties": {
        "components": {
          "additionalProperties": {
            "discriminator": {
              "mapping": {
                "completed": "#/$defs/CompletedItem",
                "failed": "#/$defs/FailedItem",
                "skipped": "#/$defs/SkippedItem"
              },
              "propertyName": "outcome"
            },
            "oneOf": [
              {
                "$ref": "#/$defs/CompletedItem"
              },
              {
                "$ref": "#/$defs/SkippedItem"
              },
              {
                "$ref": "#/$defs/FailedItem"
              }
            ]
          },
          "title": "Components",
          "type": "object"
        },
        "outcome": {
          "default": "noop",
          "enum": [
            "completed",
            "partial",
            "failed",
            "noop"
          ],
          "title": "Outcome",
          "type": "string"
        }
      },
      "title": "ComponentResults",
      "type": "object"
    },
    "FailedItem": {
      "additionalProperties": false,
      "properties": {
        "error": {
          "$ref": "#/$defs/FailureInfo"
        },
        "outcome": {
          "const": "failed",
          "default": "failed",
          "title": "Outcome",
          "type": "string"
        },
        "path": {
          "default": null,
          "title": "Path",
          "type": "null"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason"
        }
      },
      "required": [
        "error"
      ],
      "title": "FailedItem",
      "type": "object"
    },
    "FailureInfo": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "enum": [
            "validation_error",
            "not_found",
            "conflict",
            "forbidden",
            "unauthorized",
            "http_error",
            "operation_canceled",
            "invalid_server_name",
            "server_start_failed",
            "server_stop_failed",
            "server_error",
            "application_error",
            "internal_error",
            "unavailable",
            "operation_incomplete",
            "file_error",
            "storage_error",
            "configuration_error",
            "network_error",
            "system_error"
          ],
          "title": "Code",
          "type": "string"
        },
        "details": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Details",
          "type": "object"
        },
        "message": {
          "title": "Message",
          "type": "string"
        }
      },
      "required": [
        "code",
        "message"
      ],
      "title": "FailureInfo",
      "type": "object"
    },
    "JsonValue": {},
    "SkippedItem": {
      "additionalProperties": false,
      "properties": {
        "error": {
          "default": null,
          "title": "Error",
          "type": "null"
        },
        "outcome": {
          "const": "skipped",
          "default": "skipped",
          "title": "Outcome",
          "type": "string"
        },
        "path": {
          "default": null,
          "title": "Path",
          "type": "null"
        },
        "reason": {
          "title": "Reason",
          "type": "string"
        }
      },
      "required": [
        "reason"
      ],
      "title": "SkippedItem",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "details": {
      "$ref": "#/$defs/ComponentResults"
    },
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "RestoreAllResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.RestoreAllRequest` | `REQUIRED` |

---


## `backup_restore.restore_config_file`
```python
await self.api.backup_restore.restore_config_file(request: bedrock_server_manager.api.models.backup_restore.RestoreConfigFileRequest)
```
- **Async (Requires await):** Yes

- **Description:** Restores a specific config file from a backup.

- **Returns:** `RestoreConfigFileResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RestoreConfigFileRequest
payload = {...}  # Supply required request fields below.
request = RestoreConfigFileRequest(**payload)
result = await self.api.backup_restore.restore_config_file(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "backup_file_path": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Backup File Path",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "stop_start_server": {
      "default": true,
      "title": "Stop Start Server",
      "type": "boolean"
    }
  },
  "required": [
    "server_name",
    "backup_file_path"
  ],
  "title": "RestoreConfigFileRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "RestoreConfigFileResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.RestoreConfigFileRequest` | `REQUIRED` |

---


## `backup_restore.restore_world`
```python
await self.api.backup_restore.restore_world(request: bedrock_server_manager.api.models.backup_restore.RestoreWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Restores a server's world from a specific backup file.

- **Returns:** `RestoreWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RestoreWorldRequest
payload = {...}  # Supply required request fields below.
request = RestoreWorldRequest(**payload)
result = await self.api.backup_restore.restore_world(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "backup_file_path": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Backup File Path",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "stop_start_server": {
      "default": true,
      "title": "Stop Start Server",
      "type": "boolean"
    }
  },
  "required": [
    "server_name",
    "backup_file_path"
  ],
  "title": "RestoreWorldRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "RestoreWorldResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.backup_restore.RestoreWorldRequest` | `REQUIRED` |

---


## `ban.add_server_ban`
```python
await self.api.ban.add_server_ban(request: bedrock_server_manager.api.models.ban.AddServerBanRequest)
```
- **Async (Requires await):** Yes

- **Description:** Adds a player to the server ban list.

- **Returns:** `AddServerBanResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import AddServerBanRequest
payload = {...}  # Supply required request fields below.
request = AddServerBanRequest(**payload)
result = await self.api.ban.add_server_ban(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "player_name": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Player Name",
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Reason"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "xuid": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Xuid",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "player_name",
    "xuid"
  ],
  "title": "AddServerBanRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "AddServerBanResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.ban.AddServerBanRequest` | `REQUIRED` |

---


## `ban.get_server_bans`
```python
await self.api.ban.get_server_bans(request: bedrock_server_manager.api.models.ban.GetServerBansRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return all bans for a specific server.

- **Returns:** `GetServerBansResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetServerBansRequest
payload = {'server_name': 'example'}
request = GetServerBansRequest(**payload)
result = await self.api.ban.get_server_bans(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "GetServerBansRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "BanInfo": {
      "additionalProperties": false,
      "properties": {
        "banned_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Banned At"
        },
        "player_name": {
          "title": "Player Name",
          "type": "string"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason"
        },
        "xuid": {
          "title": "Xuid",
          "type": "string"
        }
      },
      "required": [
        "player_name",
        "xuid"
      ],
      "title": "BanInfo",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "bans": {
      "items": {
        "$ref": "#/$defs/BanInfo"
      },
      "title": "Bans",
      "type": "array"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "bans"
  ],
  "title": "GetServerBansResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.ban.GetServerBansRequest` | `REQUIRED` |

---


## `diagnostics.get_application_diagnostics`
```python
await self.api.diagnostics.get_application_diagnostics(request: bedrock_server_manager.api.models.diagnostics.GetApplicationDiagnosticsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read bounded subsystem metadata; unavailable providers remain isolated.

- **Returns:** `GetApplicationDiagnosticsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetApplicationDiagnosticsRequest
payload = {}
request = GetApplicationDiagnosticsRequest(**payload)
result = await self.api.diagnostics.get_application_diagnostics(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "subsystem": {
      "anyOf": [
        {
          "maxLength": 80,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Subsystem"
    }
  },
  "title": "GetApplicationDiagnosticsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "DiagnosticEnvironment": {
      "additionalProperties": false,
      "properties": {
        "backend_version": {
          "title": "Backend Version",
          "type": "string"
        },
        "database_dialect": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Database Dialect"
        },
        "database_schema_revision": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Database Schema Revision"
        },
        "frontend_version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Frontend Version"
        },
        "operating_system": {
          "title": "Operating System",
          "type": "string"
        },
        "python_version": {
          "title": "Python Version",
          "type": "string"
        }
      },
      "required": [
        "backend_version",
        "python_version",
        "operating_system"
      ],
      "title": "DiagnosticEnvironment",
      "type": "object"
    },
    "DiagnosticFinding": {
      "additionalProperties": false,
      "properties": {
        "issue": {
          "$ref": "#/$defs/DiagnosticIssue"
        },
        "owner": {
          "title": "Owner",
          "type": "string"
        },
        "subsystem": {
          "title": "Subsystem",
          "type": "string"
        }
      },
      "required": [
        "subsystem",
        "owner",
        "issue"
      ],
      "title": "DiagnosticFinding",
      "type": "object"
    },
    "DiagnosticIssue": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "anyOf": [
            {
              "enum": [
                "inspect_logs",
                "inspect_events",
                "inspect_storage",
                "inspect_plugins",
                "wait_for_drain",
                "check_configuration"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Action"
        },
        "code": {
          "title": "Code",
          "type": "string"
        },
        "message": {
          "title": "Message",
          "type": "string"
        },
        "severity": {
          "default": "warning",
          "enum": [
            "warning",
            "error"
          ],
          "title": "Severity",
          "type": "string"
        }
      },
      "required": [
        "code",
        "message"
      ],
      "title": "DiagnosticIssue",
      "type": "object"
    },
    "DiagnosticSection": {
      "additionalProperties": false,
      "properties": {
        "age_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Age Seconds"
        },
        "collected_at": {
          "title": "Collected At",
          "type": "number"
        },
        "data": {
          "anyOf": [
            {
              "discriminator": {
                "mapping": {
                  "events": "#/$defs/EventsDiagnostics",
                  "metrics": "#/$defs/MetricsDiagnostics",
                  "plugin_values": "#/$defs/PluginValues",
                  "plugins": "#/$defs/PluginsDiagnostics",
                  "processes": "#/$defs/ProcessesDiagnostics",
                  "runtime": "#/$defs/RuntimeDiagnostics",
                  "state": "#/$defs/StateDiagnostics",
                  "storage": "#/$defs/StorageDiagnostics",
                  "tasks": "#/$defs/TasksDiagnostics",
                  "transport": "#/$defs/TransportDiagnostics"
                },
                "propertyName": "kind"
              },
              "oneOf": [
                {
                  "$ref": "#/$defs/RuntimeDiagnostics"
                },
                {
                  "$ref": "#/$defs/StateDiagnostics"
                },
                {
                  "$ref": "#/$defs/StorageDiagnostics"
                },
                {
                  "$ref": "#/$defs/EventsDiagnostics"
                },
                {
                  "$ref": "#/$defs/TransportDiagnostics"
                },
                {
                  "$ref": "#/$defs/PluginsDiagnostics"
                },
                {
                  "$ref": "#/$defs/TasksDiagnostics"
                },
                {
                  "$ref": "#/$defs/ProcessesDiagnostics"
                },
                {
                  "$ref": "#/$defs/MetricsDiagnostics"
                },
                {
                  "$ref": "#/$defs/PluginValues"
                }
              ]
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Data"
        },
        "duration_ms": {
          "default": 0,
          "title": "Duration Ms",
          "type": "number"
        },
        "issues": {
          "items": {
            "$ref": "#/$defs/DiagnosticIssue"
          },
          "maxItems": 20,
          "title": "Issues",
          "type": "array"
        },
        "last_success_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Success At"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "observed_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Observed At"
        },
        "owner": {
          "default": "application",
          "title": "Owner",
          "type": "string"
        },
        "stale": {
          "default": false,
          "title": "Stale",
          "type": "boolean"
        },
        "status": {
          "default": "unknown",
          "enum": [
            "ok",
            "degraded",
            "unavailable",
            "unknown"
          ],
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "name",
        "collected_at"
      ],
      "title": "DiagnosticSection",
      "type": "object"
    },
    "DiagnosticSummary": {
      "additionalProperties": false,
      "properties": {
        "counts_by_status": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Counts By Status",
          "type": "object"
        },
        "findings": {
          "items": {
            "$ref": "#/$defs/DiagnosticFinding"
          },
          "maxItems": 100,
          "title": "Findings",
          "type": "array"
        },
        "ready": {
          "title": "Ready",
          "type": "boolean"
        },
        "status": {
          "enum": [
            "ok",
            "degraded",
            "unavailable",
            "unknown"
          ],
          "title": "Status",
          "type": "string"
        },
        "truncated": {
          "default": false,
          "title": "Truncated",
          "type": "boolean"
        }
      },
      "required": [
        "status",
        "ready",
        "counts_by_status"
      ],
      "title": "DiagnosticSummary",
      "type": "object"
    },
    "EventDelivery": {
      "additionalProperties": false,
      "properties": {
        "failed": {
          "default": 0,
          "minimum": 0,
          "title": "Failed",
          "type": "integer"
        },
        "owner": {
          "title": "Owner",
          "type": "string"
        },
        "sent": {
          "default": 0,
          "minimum": 0,
          "title": "Sent",
          "type": "integer"
        },
        "targeted": {
          "default": 0,
          "minimum": 0,
          "title": "Targeted",
          "type": "integer"
        },
        "unavailable": {
          "default": 0,
          "minimum": 0,
          "title": "Unavailable",
          "type": "integer"
        }
      },
      "required": [
        "owner"
      ],
      "title": "EventDelivery",
      "type": "object"
    },
    "EventDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "accepting": {
          "title": "Accepting",
          "type": "boolean"
        },
        "active": {
          "items": {
            "$ref": "#/$defs/EventRecord"
          },
          "title": "Active",
          "type": "array"
        },
        "active_dispatches": {
          "default": 0,
          "title": "Active Dispatches",
          "type": "integer"
        },
        "active_listeners_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Active Listeners By Owner",
          "type": "object"
        },
        "emitted": {
          "title": "Emitted",
          "type": "integer"
        },
        "failed_listeners": {
          "title": "Failed Listeners",
          "type": "integer"
        },
        "notification_delivery": {
          "const": "inline",
          "default": "inline",
          "title": "Notification Delivery",
          "type": "string"
        },
        "pending_waits": {
          "default": 0,
          "title": "Pending Waits",
          "type": "integer"
        },
        "pending_workers": {
          "default": 0,
          "title": "Pending Workers",
          "type": "integer"
        },
        "recent": {
          "items": {
            "$ref": "#/$defs/EventRecord"
          },
          "title": "Recent",
          "type": "array"
        },
        "rejections_by_reason": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Rejections By Reason",
          "type": "object"
        },
        "subscriptions": {
          "title": "Subscriptions",
          "type": "integer"
        },
        "subscriptions_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Subscriptions By Owner",
          "type": "object"
        },
        "suppressed": {
          "title": "Suppressed",
          "type": "integer"
        },
        "timeouts_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Timeouts By Owner",
          "type": "object"
        },
        "workers_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Workers By Owner",
          "type": "object"
        }
      },
      "required": [
        "accepting",
        "emitted",
        "suppressed",
        "failed_listeners",
        "subscriptions",
        "active",
        "recent"
      ],
      "title": "EventDiagnostics",
      "type": "object"
    },
    "EventOptions": {
      "additionalProperties": false,
      "properties": {
        "history_limit": {
          "default": 200,
          "maximum": 10000,
          "minimum": 0,
          "title": "History Limit",
          "type": "integer"
        },
        "hook_timeout_seconds": {
          "default": 120,
          "exclusiveMinimum": 0,
          "maximum": 3600,
          "title": "Hook Timeout Seconds",
          "type": "number"
        },
        "listener_timeout_seconds": {
          "default": 30,
          "exclusiveMinimum": 0,
          "maximum": 3600,
          "title": "Listener Timeout Seconds",
          "type": "number"
        },
        "max_active": {
          "default": 256,
          "maximum": 10000,
          "minimum": 1,
          "title": "Max Active",
          "type": "integer"
        },
        "max_depth": {
          "default": 32,
          "maximum": 128,
          "minimum": 1,
          "title": "Max Depth",
          "type": "integer"
        },
        "max_workers": {
          "anyOf": [
            {
              "maximum": 10000,
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Max Workers"
        },
        "max_workers_per_owner": {
          "anyOf": [
            {
              "maximum": 10000,
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Max Workers Per Owner"
        }
      },
      "title": "EventOptions",
      "type": "object"
    },
    "EventRecord": {
      "additionalProperties": false,
      "properties": {
        "cancellation_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Cancellation Reason"
        },
        "correlation_id": {
          "title": "Correlation Id",
          "type": "string"
        },
        "deliveries": {
          "items": {
            "$ref": "#/$defs/EventDelivery"
          },
          "title": "Deliveries",
          "type": "array"
        },
        "duration_ms": {
          "default": 0,
          "title": "Duration Ms",
          "type": "number"
        },
        "event_id": {
          "title": "Event Id",
          "type": "string"
        },
        "failures": {
          "items": {
            "$ref": "#/$defs/ListenerFailure"
          },
          "title": "Failures",
          "type": "array"
        },
        "listeners": {
          "items": {
            "$ref": "#/$defs/ListenerRecord"
          },
          "title": "Listeners",
          "type": "array"
        },
        "listeners_called": {
          "default": 0,
          "title": "Listeners Called",
          "type": "integer"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "rejection_reason": {
          "anyOf": [
            {
              "enum": [
                "recursion",
                "depth_limit",
                "capacity",
                "shutdown"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Rejection Reason"
        },
        "source": {
          "title": "Source",
          "type": "string"
        },
        "status": {
          "enum": [
            "dispatching",
            "completed",
            "partial",
            "cancelled",
            "suppressed"
          ],
          "title": "Status",
          "type": "string"
        },
        "timestamp": {
          "title": "Timestamp",
          "type": "number"
        }
      },
      "required": [
        "event_id",
        "correlation_id",
        "name",
        "source",
        "timestamp",
        "status"
      ],
      "title": "EventRecord",
      "type": "object"
    },
    "EventsDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "activity": {
          "$ref": "#/$defs/EventDiagnostics"
        },
        "capacity": {
          "$ref": "#/$defs/EventOptions"
        },
        "kind": {
          "const": "events",
          "default": "events",
          "title": "Kind",
          "type": "string"
        }
      },
      "required": [
        "activity",
        "capacity"
      ],
      "title": "EventsDiagnostics",
      "type": "object"
    },
    "ListenerFailure": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "enum": [
            "event_listener_failed",
            "event_listener_timeout",
            "event_depth_limit",
            "event_capacity"
          ],
          "title": "Code",
          "type": "string"
        },
        "error_type": {
          "title": "Error Type",
          "type": "string"
        },
        "owner": {
          "title": "Owner",
          "type": "string"
        }
      },
      "required": [
        "owner",
        "error_type",
        "code"
      ],
      "title": "ListenerFailure",
      "type": "object"
    },
    "ListenerRecord": {
      "additionalProperties": false,
      "properties": {
        "duration_ms": {
          "default": 0,
          "minimum": 0,
          "title": "Duration Ms",
          "type": "number"
        },
        "failure": {
          "anyOf": [
            {
              "$ref": "#/$defs/ListenerFailure"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "listener_name": {
          "title": "Listener Name",
          "type": "string"
        },
        "observer": {
          "title": "Observer",
          "type": "boolean"
        },
        "owner": {
          "title": "Owner",
          "type": "string"
        },
        "status": {
          "default": "running",
          "enum": [
            "running",
            "completed",
            "failed",
            "timed_out",
            "cancelled"
          ],
          "title": "Status",
          "type": "string"
        },
        "subscription_id": {
          "title": "Subscription Id",
          "type": "string"
        }
      },
      "required": [
        "subscription_id",
        "owner",
        "observer",
        "listener_name"
      ],
      "title": "ListenerRecord",
      "type": "object"
    },
    "MetricsDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "attempts": {
          "default": 0,
          "title": "Attempts",
          "type": "integer"
        },
        "failures": {
          "default": 0,
          "title": "Failures",
          "type": "integer"
        },
        "interval_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Interval Seconds"
        },
        "kind": {
          "const": "metrics",
          "default": "metrics",
          "title": "Kind",
          "type": "string"
        },
        "last_duration_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Duration Ms"
        },
        "last_error_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Error Type"
        },
        "last_sample_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Sample At"
        },
        "missed_intervals": {
          "default": 0,
          "title": "Missed Intervals",
          "type": "integer"
        },
        "sample_age_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sample Age Seconds"
        },
        "successes": {
          "default": 0,
          "title": "Successes",
          "type": "integer"
        },
        "unavailable_measurements": {
          "items": {
            "type": "string"
          },
          "title": "Unavailable Measurements",
          "type": "array"
        },
        "warming_up": {
          "default": true,
          "title": "Warming Up",
          "type": "boolean"
        }
      },
      "title": "MetricsDiagnostics",
      "type": "object"
    },
    "PersistenceDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "accepting": {
          "title": "Accepting",
          "type": "boolean"
        },
        "dropped": {
          "title": "Dropped",
          "type": "integer"
        },
        "history_limit": {
          "title": "History Limit",
          "type": "integer"
        },
        "queue_limit": {
          "title": "Queue Limit",
          "type": "integer"
        },
        "queued": {
          "title": "Queued",
          "type": "integer"
        },
        "retention_days": {
          "title": "Retention Days",
          "type": "integer"
        },
        "write_failures": {
          "title": "Write Failures",
          "type": "integer"
        }
      },
      "required": [
        "queued",
        "queue_limit",
        "dropped",
        "write_failures",
        "accepting",
        "history_limit",
        "retention_days"
      ],
      "title": "PersistenceDiagnostics",
      "type": "object"
    },
    "PluginDiagnostic": {
      "additionalProperties": false,
      "properties": {
        "active_tasks": {
          "title": "Active Tasks",
          "type": "integer"
        },
        "diagnostic_providers": {
          "default": 0,
          "title": "Diagnostic Providers",
          "type": "integer"
        },
        "drain_failures": {
          "default": 0,
          "title": "Drain Failures",
          "type": "integer"
        },
        "draining": {
          "title": "Draining",
          "type": "boolean"
        },
        "generation": {
          "title": "Generation",
          "type": "integer"
        },
        "last_drain_duration_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Drain Duration Ms"
        },
        "last_transition_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Transition At"
        },
        "listeners": {
          "default": 0,
          "title": "Listeners",
          "type": "integer"
        },
        "load_failures": {
          "default": 0,
          "title": "Load Failures",
          "type": "integer"
        },
        "managed_tasks": {
          "default": 0,
          "title": "Managed Tasks",
          "type": "integer"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "status": {
          "title": "Status",
          "type": "string"
        },
        "version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Version"
        },
        "workers": {
          "default": 0,
          "title": "Workers",
          "type": "integer"
        }
      },
      "required": [
        "name",
        "status",
        "generation",
        "active_tasks",
        "draining"
      ],
      "title": "PluginDiagnostic",
      "type": "object"
    },
    "PluginValues": {
      "additionalProperties": false,
      "description": "Explicit observations; string dumps and secrets are excluded.",
      "properties": {
        "health": {
          "default": "unknown",
          "enum": [
            "ok",
            "degraded",
            "unknown"
          ],
          "title": "Health",
          "type": "string"
        },
        "kind": {
          "const": "plugin_values",
          "default": "plugin_values",
          "title": "Kind",
          "type": "string"
        },
        "units": {
          "additionalProperties": {
            "enum": [
              "count",
              "seconds",
              "milliseconds",
              "bytes",
              "percent"
            ],
            "type": "string"
          },
          "maxProperties": 50,
          "title": "Units",
          "type": "object"
        },
        "values": {
          "additionalProperties": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ]
          },
          "maxProperties": 50,
          "title": "Values",
          "type": "object"
        }
      },
      "required": [
        "values"
      ],
      "title": "PluginValues",
      "type": "object"
    },
    "PluginsDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "plugins",
          "default": "plugins",
          "title": "Kind",
          "type": "string"
        },
        "plugins": {
          "items": {
            "$ref": "#/$defs/PluginDiagnostic"
          },
          "title": "Plugins",
          "type": "array"
        },
        "total": {
          "default": 0,
          "title": "Total",
          "type": "integer"
        },
        "truncated": {
          "default": false,
          "title": "Truncated",
          "type": "boolean"
        }
      },
      "title": "PluginsDiagnostics",
      "type": "object"
    },
    "ProcessDiagnostic": {
      "additionalProperties": false,
      "properties": {
        "expected_status": {
          "title": "Expected Status",
          "type": "string"
        },
        "last_error_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Error Type"
        },
        "observed_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Observed At"
        },
        "observed_running": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Observed Running"
        },
        "pid": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Pid"
        },
        "server_name": {
          "title": "Server Name",
          "type": "string"
        }
      },
      "required": [
        "server_name",
        "expected_status"
      ],
      "title": "ProcessDiagnostic",
      "type": "object"
    },
    "ProcessesDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "processes",
          "default": "processes",
          "title": "Kind",
          "type": "string"
        },
        "last_monitor_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Monitor At"
        },
        "monitor_failures": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Monitor Failures"
        },
        "observation_available": {
          "title": "Observation Available",
          "type": "boolean"
        },
        "observed_running": {
          "title": "Observed Running",
          "type": "integer"
        },
        "processes": {
          "items": {
            "$ref": "#/$defs/ProcessDiagnostic"
          },
          "title": "Processes",
          "type": "array"
        },
        "registered": {
          "title": "Registered",
          "type": "integer"
        },
        "truncated": {
          "default": false,
          "title": "Truncated",
          "type": "boolean"
        }
      },
      "required": [
        "registered",
        "observed_running",
        "observation_available"
      ],
      "title": "ProcessesDiagnostics",
      "type": "object"
    },
    "RegistryDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "failures": {
          "default": 0,
          "title": "Failures",
          "type": "integer"
        },
        "max_providers": {
          "title": "Max Providers",
          "type": "integer"
        },
        "max_providers_per_owner": {
          "title": "Max Providers Per Owner",
          "type": "integer"
        },
        "owner_limits_scope": {
          "const": "plugins",
          "default": "plugins",
          "title": "Owner Limits Scope",
          "type": "string"
        },
        "pending": {
          "title": "Pending",
          "type": "integer"
        },
        "pending_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Pending By Owner",
          "type": "object"
        },
        "registered": {
          "title": "Registered",
          "type": "integer"
        },
        "registered_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Registered By Owner",
          "type": "object"
        },
        "rejected": {
          "default": 0,
          "title": "Rejected",
          "type": "integer"
        },
        "timeouts": {
          "default": 0,
          "title": "Timeouts",
          "type": "integer"
        }
      },
      "required": [
        "registered",
        "pending",
        "max_providers",
        "max_providers_per_owner"
      ],
      "title": "RegistryDiagnostics",
      "type": "object"
    },
    "RuntimeDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "runtime",
          "default": "runtime",
          "title": "Kind",
          "type": "string"
        },
        "phase": {
          "title": "Phase",
          "type": "string"
        },
        "pid": {
          "title": "Pid",
          "type": "integer"
        },
        "python_version": {
          "title": "Python Version",
          "type": "string"
        },
        "ready": {
          "default": false,
          "title": "Ready",
          "type": "boolean"
        },
        "shutdown_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Shutdown Reason"
        },
        "shutdown_requested": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Shutdown Requested"
        },
        "stage": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stage"
        },
        "stage_elapsed_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stage Elapsed Seconds"
        },
        "stage_started_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stage Started At"
        },
        "stage_timeout_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stage Timeout Seconds"
        },
        "uptime_seconds": {
          "title": "Uptime Seconds",
          "type": "number"
        },
        "version": {
          "title": "Version",
          "type": "string"
        }
      },
      "required": [
        "phase",
        "pid",
        "uptime_seconds",
        "version",
        "python_version"
      ],
      "title": "RuntimeDiagnostics",
      "type": "object"
    },
    "StateDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "counts": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Counts",
          "type": "object"
        },
        "epoch": {
          "title": "Epoch",
          "type": "string"
        },
        "kind": {
          "const": "state",
          "default": "state",
          "title": "Kind",
          "type": "string"
        },
        "observation_revision": {
          "title": "Observation Revision",
          "type": "integer"
        },
        "oldest_pending_age_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Oldest Pending Age Seconds"
        },
        "pending_changes": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Pending Changes",
          "type": "object"
        }
      },
      "required": [
        "epoch",
        "observation_revision",
        "counts",
        "pending_changes"
      ],
      "title": "StateDiagnostics",
      "type": "object"
    },
    "StorageDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "active": {
          "default": 0,
          "title": "Active",
          "type": "integer"
        },
        "attempts": {
          "default": 0,
          "title": "Attempts",
          "type": "integer"
        },
        "failures": {
          "default": 0,
          "title": "Failures",
          "type": "integer"
        },
        "kind": {
          "const": "storage",
          "default": "storage",
          "title": "Kind",
          "type": "string"
        },
        "last_duration_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Duration Ms"
        },
        "last_error_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Error Type"
        },
        "last_reload_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Reload At"
        },
        "last_reload_duration_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Reload Duration Ms"
        },
        "last_reload_error_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Reload Error Type"
        },
        "last_success_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Success At"
        },
        "lock_wait_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Lock Wait Ms"
        },
        "lock_waiters": {
          "default": 0,
          "title": "Lock Waiters",
          "type": "integer"
        },
        "max_lock_wait_ms": {
          "default": 0,
          "title": "Max Lock Wait Ms",
          "type": "number"
        },
        "reload_active": {
          "default": false,
          "title": "Reload Active",
          "type": "boolean"
        },
        "reload_attempts": {
          "default": 0,
          "title": "Reload Attempts",
          "type": "integer"
        },
        "reload_failures": {
          "default": 0,
          "title": "Reload Failures",
          "type": "integer"
        },
        "reload_successes": {
          "default": 0,
          "title": "Reload Successes",
          "type": "integer"
        },
        "successes": {
          "default": 0,
          "title": "Successes",
          "type": "integer"
        },
        "total_lock_wait_ms": {
          "default": 0,
          "title": "Total Lock Wait Ms",
          "type": "number"
        }
      },
      "title": "StorageDiagnostics",
      "type": "object"
    },
    "TaskDiagnostic": {
      "additionalProperties": false,
      "properties": {
        "cancellation_requested": {
          "default": false,
          "title": "Cancellation Requested",
          "type": "boolean"
        },
        "correlation_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Correlation Id"
        },
        "elapsed_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Elapsed Seconds"
        },
        "error_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Code"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "name": {
          "default": "background_task",
          "title": "Name",
          "type": "string"
        },
        "owner": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Owner"
        },
        "progress_percent": {
          "anyOf": [
            {
              "maximum": 100,
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Progress Percent"
        },
        "status": {
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "id",
        "status"
      ],
      "title": "TaskDiagnostic",
      "type": "object"
    },
    "TasksDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "accepting": {
          "title": "Accepting",
          "type": "boolean"
        },
        "active": {
          "title": "Active",
          "type": "integer"
        },
        "capacity": {
          "default": 100,
          "title": "Capacity",
          "type": "integer"
        },
        "counts_by_status": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Counts By Status",
          "type": "object"
        },
        "kind": {
          "const": "tasks",
          "default": "tasks",
          "title": "Kind",
          "type": "string"
        },
        "oldest_active_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Oldest Active Seconds"
        },
        "tasks": {
          "items": {
            "$ref": "#/$defs/TaskDiagnostic"
          },
          "title": "Tasks",
          "type": "array"
        }
      },
      "required": [
        "active",
        "counts_by_status",
        "accepting"
      ],
      "title": "TasksDiagnostics",
      "type": "object"
    },
    "TransportDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "accepting": {
          "default": true,
          "title": "Accepting",
          "type": "boolean"
        },
        "active_sends": {
          "default": 0,
          "title": "Active Sends",
          "type": "integer"
        },
        "connected_clients": {
          "title": "Connected Clients",
          "type": "integer"
        },
        "delivery_mode": {
          "const": "direct",
          "default": "direct",
          "title": "Delivery Mode",
          "type": "string"
        },
        "disconnects_by_reason": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Disconnects By Reason",
          "type": "object"
        },
        "dropped_messages": {
          "default": 0,
          "title": "Dropped Messages",
          "type": "integer"
        },
        "failed_sends": {
          "default": 0,
          "title": "Failed Sends",
          "type": "integer"
        },
        "high_water_mark": {
          "default": 0,
          "title": "High Water Mark",
          "type": "integer"
        },
        "kind": {
          "const": "transport",
          "default": "transport",
          "title": "Kind",
          "type": "string"
        },
        "last_send_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Send At"
        },
        "last_send_duration_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Send Duration Ms"
        },
        "max_pending_per_client": {
          "default": 0,
          "title": "Max Pending Per Client",
          "type": "integer"
        },
        "pending_sends": {
          "default": 0,
          "title": "Pending Sends",
          "type": "integer"
        },
        "queue_limit_per_client": {
          "default": 64,
          "title": "Queue Limit Per Client",
          "type": "integer"
        },
        "send_timeouts": {
          "default": 0,
          "title": "Send Timeouts",
          "type": "integer"
        },
        "subscriptions": {
          "title": "Subscriptions",
          "type": "integer"
        },
        "successful_sends": {
          "default": 0,
          "title": "Successful Sends",
          "type": "integer"
        },
        "topics": {
          "title": "Topics",
          "type": "integer"
        }
      },
      "required": [
        "connected_clients",
        "subscriptions",
        "topics"
      ],
      "title": "TransportDiagnostics",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "collected_at": {
      "title": "Collected At",
      "type": "number"
    },
    "counter_scope": {
      "const": "current_instance",
      "default": "current_instance",
      "title": "Counter Scope",
      "type": "string"
    },
    "environment": {
      "$ref": "#/$defs/DiagnosticEnvironment"
    },
    "instance_id": {
      "title": "Instance Id",
      "type": "string"
    },
    "persistence": {
      "$ref": "#/$defs/PersistenceDiagnostics"
    },
    "registry": {
      "$ref": "#/$defs/RegistryDiagnostics"
    },
    "schema_version": {
      "const": 1,
      "default": 1,
      "title": "Schema Version",
      "type": "integer"
    },
    "sections": {
      "items": {
        "$ref": "#/$defs/DiagnosticSection"
      },
      "title": "Sections",
      "type": "array"
    },
    "summary": {
      "$ref": "#/$defs/DiagnosticSummary"
    }
  },
  "required": [
    "instance_id",
    "collected_at",
    "sections",
    "summary",
    "registry",
    "environment",
    "persistence"
  ],
  "title": "GetApplicationDiagnosticsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.GetApplicationDiagnosticsRequest` | `REQUIRED` |

---


## `diagnostics.get_diagnostic_history`
```python
await self.api.diagnostics.get_diagnostic_history(request: bedrock_server_manager.api.models.diagnostics.GetDiagnosticHistoryRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read sanitized retained records, optionally scoped to an application run.

- **Returns:** `GetDiagnosticHistoryResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetDiagnosticHistoryRequest
payload = {}
request = GetDiagnosticHistoryRequest(**payload)
result = await self.api.diagnostics.get_diagnostic_history(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "code": {
      "anyOf": [
        {
          "maxLength": 80,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Code"
    },
    "correlation_id": {
      "anyOf": [
        {
          "maxLength": 160,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Correlation Id"
    },
    "cursor": {
      "anyOf": [
        {
          "maxLength": 512,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Cursor"
    },
    "instance_id": {
      "anyOf": [
        {
          "maxLength": 32,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Instance Id"
    },
    "limit": {
      "default": 100,
      "maximum": 200,
      "minimum": 1,
      "title": "Limit",
      "type": "integer"
    },
    "operation_id": {
      "anyOf": [
        {
          "maxLength": 160,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Operation Id"
    },
    "outcome": {
      "anyOf": [
        {
          "enum": [
            "completed",
            "failed",
            "cancelled"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Outcome"
    },
    "owner": {
      "anyOf": [
        {
          "maxLength": 160,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Owner"
    },
    "subsystem": {
      "anyOf": [
        {
          "maxLength": 80,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Subsystem"
    }
  },
  "title": "GetDiagnosticHistoryRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "DiagnosticRecord": {
      "additionalProperties": false,
      "properties": {
        "backend_version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Backend Version"
        },
        "code": {
          "maxLength": 80,
          "title": "Code",
          "type": "string"
        },
        "correlation_id": {
          "anyOf": [
            {
              "maxLength": 160,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Correlation Id"
        },
        "duration_ms": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Duration Ms"
        },
        "error_type": {
          "anyOf": [
            {
              "maxLength": 80,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Type"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "instance_id": {
          "title": "Instance Id",
          "type": "string"
        },
        "operation": {
          "maxLength": 160,
          "title": "Operation",
          "type": "string"
        },
        "operation_id": {
          "anyOf": [
            {
              "maxLength": 160,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Operation Id"
        },
        "outcome": {
          "enum": [
            "completed",
            "failed",
            "cancelled"
          ],
          "title": "Outcome",
          "type": "string"
        },
        "owner": {
          "anyOf": [
            {
              "maxLength": 160,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Owner"
        },
        "phase": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Phase"
        },
        "subsystem": {
          "maxLength": 80,
          "pattern": "^[\\w.:-]+$",
          "title": "Subsystem",
          "type": "string"
        },
        "timestamp": {
          "title": "Timestamp",
          "type": "number"
        }
      },
      "required": [
        "id",
        "instance_id",
        "timestamp",
        "subsystem",
        "operation",
        "outcome",
        "code"
      ],
      "title": "DiagnosticRecord",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "available": {
      "title": "Available",
      "type": "boolean"
    },
    "next_cursor": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Next Cursor"
    },
    "records": {
      "items": {
        "$ref": "#/$defs/DiagnosticRecord"
      },
      "title": "Records",
      "type": "array"
    },
    "truncated": {
      "title": "Truncated",
      "type": "boolean"
    }
  },
  "required": [
    "records",
    "available",
    "truncated"
  ],
  "title": "GetDiagnosticHistoryResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.GetDiagnosticHistoryRequest` | `REQUIRED` |

---


## `diagnostics.get_diagnostic_report`
```python
await self.api.diagnostics.get_diagnostic_report(request: bedrock_server_manager.api.models.diagnostics.GetDiagnosticReportRequest)
```
- **Async (Requires await):** Yes

- **Description:** Build a support report without secrets, task arguments, or event payloads.

- **Returns:** `GetDiagnosticReportResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetDiagnosticReportRequest
payload = {}
request = GetDiagnosticReportRequest(**payload)
result = await self.api.diagnostics.get_diagnostic_report(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetDiagnosticReportRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "DiagnosticEnvironment": {
      "additionalProperties": false,
      "properties": {
        "backend_version": {
          "title": "Backend Version",
          "type": "string"
        },
        "database_dialect": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Database Dialect"
        },
        "database_schema_revision": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Database Schema Revision"
        },
        "frontend_version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Frontend Version"
        },
        "operating_system": {
          "title": "Operating System",
          "type": "string"
        },
        "python_version": {
          "title": "Python Version",
          "type": "string"
        }
      },
      "required": [
        "backend_version",
        "python_version",
        "operating_system"
      ],
      "title": "DiagnosticEnvironment",
      "type": "object"
    },
    "DiagnosticFinding": {
      "additionalProperties": false,
      "properties": {
        "issue": {
          "$ref": "#/$defs/DiagnosticIssue"
        },
        "owner": {
          "title": "Owner",
          "type": "string"
        },
        "subsystem": {
          "title": "Subsystem",
          "type": "string"
        }
      },
      "required": [
        "subsystem",
        "owner",
        "issue"
      ],
      "title": "DiagnosticFinding",
      "type": "object"
    },
    "DiagnosticHistory": {
      "additionalProperties": false,
      "properties": {
        "available": {
          "title": "Available",
          "type": "boolean"
        },
        "next_cursor": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Next Cursor"
        },
        "records": {
          "items": {
            "$ref": "#/$defs/DiagnosticRecord"
          },
          "title": "Records",
          "type": "array"
        },
        "truncated": {
          "title": "Truncated",
          "type": "boolean"
        }
      },
      "required": [
        "records",
        "available",
        "truncated"
      ],
      "title": "DiagnosticHistory",
      "type": "object"
    },
    "DiagnosticIssue": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "anyOf": [
            {
              "enum": [
                "inspect_logs",
                "inspect_events",
                "inspect_storage",
                "inspect_plugins",
                "wait_for_drain",
                "check_configuration"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Action"
        },
        "code": {
          "title": "Code",
          "type": "string"
        },
        "message": {
          "title": "Message",
          "type": "string"
        },
        "severity": {
          "default": "warning",
          "enum": [
            "warning",
            "error"
          ],
          "title": "Severity",
          "type": "string"
        }
      },
      "required": [
        "code",
        "message"
      ],
      "title": "DiagnosticIssue",
      "type": "object"
    },
    "DiagnosticRecord": {
      "additionalProperties": false,
      "properties": {
        "backend_version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Backend Version"
        },
        "code": {
          "maxLength": 80,
          "title": "Code",
          "type": "string"
        },
        "correlation_id": {
          "anyOf": [
            {
              "maxLength": 160,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Correlation Id"
        },
        "duration_ms": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Duration Ms"
        },
        "error_type": {
          "anyOf": [
            {
              "maxLength": 80,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Type"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "instance_id": {
          "title": "Instance Id",
          "type": "string"
        },
        "operation": {
          "maxLength": 160,
          "title": "Operation",
          "type": "string"
        },
        "operation_id": {
          "anyOf": [
            {
              "maxLength": 160,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Operation Id"
        },
        "outcome": {
          "enum": [
            "completed",
            "failed",
            "cancelled"
          ],
          "title": "Outcome",
          "type": "string"
        },
        "owner": {
          "anyOf": [
            {
              "maxLength": 160,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Owner"
        },
        "phase": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Phase"
        },
        "subsystem": {
          "maxLength": 80,
          "pattern": "^[\\w.:-]+$",
          "title": "Subsystem",
          "type": "string"
        },
        "timestamp": {
          "title": "Timestamp",
          "type": "number"
        }
      },
      "required": [
        "id",
        "instance_id",
        "timestamp",
        "subsystem",
        "operation",
        "outcome",
        "code"
      ],
      "title": "DiagnosticRecord",
      "type": "object"
    },
    "DiagnosticRun": {
      "additionalProperties": false,
      "properties": {
        "backend_version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Backend Version"
        },
        "cancelled_records": {
          "title": "Cancelled Records",
          "type": "integer"
        },
        "current_instance": {
          "title": "Current Instance",
          "type": "boolean"
        },
        "failed_records": {
          "title": "Failed Records",
          "type": "integer"
        },
        "first_record_at": {
          "title": "First Record At",
          "type": "number"
        },
        "instance_id": {
          "title": "Instance Id",
          "type": "string"
        },
        "last_observed_phase": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Observed Phase"
        },
        "last_record_at": {
          "title": "Last Record At",
          "type": "number"
        },
        "recording_closed": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Recording Closed"
        },
        "retained_records": {
          "title": "Retained Records",
          "type": "integer"
        }
      },
      "required": [
        "instance_id",
        "first_record_at",
        "last_record_at",
        "retained_records",
        "failed_records",
        "cancelled_records",
        "current_instance"
      ],
      "title": "DiagnosticRun",
      "type": "object"
    },
    "DiagnosticRuns": {
      "additionalProperties": false,
      "properties": {
        "available": {
          "title": "Available",
          "type": "boolean"
        },
        "runs": {
          "items": {
            "$ref": "#/$defs/DiagnosticRun"
          },
          "title": "Runs",
          "type": "array"
        },
        "truncated": {
          "title": "Truncated",
          "type": "boolean"
        }
      },
      "required": [
        "runs",
        "available",
        "truncated"
      ],
      "title": "DiagnosticRuns",
      "type": "object"
    },
    "DiagnosticSection": {
      "additionalProperties": false,
      "properties": {
        "age_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Age Seconds"
        },
        "collected_at": {
          "title": "Collected At",
          "type": "number"
        },
        "data": {
          "anyOf": [
            {
              "discriminator": {
                "mapping": {
                  "events": "#/$defs/EventsDiagnostics",
                  "metrics": "#/$defs/MetricsDiagnostics",
                  "plugin_values": "#/$defs/PluginValues",
                  "plugins": "#/$defs/PluginsDiagnostics",
                  "processes": "#/$defs/ProcessesDiagnostics",
                  "runtime": "#/$defs/RuntimeDiagnostics",
                  "state": "#/$defs/StateDiagnostics",
                  "storage": "#/$defs/StorageDiagnostics",
                  "tasks": "#/$defs/TasksDiagnostics",
                  "transport": "#/$defs/TransportDiagnostics"
                },
                "propertyName": "kind"
              },
              "oneOf": [
                {
                  "$ref": "#/$defs/RuntimeDiagnostics"
                },
                {
                  "$ref": "#/$defs/StateDiagnostics"
                },
                {
                  "$ref": "#/$defs/StorageDiagnostics"
                },
                {
                  "$ref": "#/$defs/EventsDiagnostics"
                },
                {
                  "$ref": "#/$defs/TransportDiagnostics"
                },
                {
                  "$ref": "#/$defs/PluginsDiagnostics"
                },
                {
                  "$ref": "#/$defs/TasksDiagnostics"
                },
                {
                  "$ref": "#/$defs/ProcessesDiagnostics"
                },
                {
                  "$ref": "#/$defs/MetricsDiagnostics"
                },
                {
                  "$ref": "#/$defs/PluginValues"
                }
              ]
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Data"
        },
        "duration_ms": {
          "default": 0,
          "title": "Duration Ms",
          "type": "number"
        },
        "issues": {
          "items": {
            "$ref": "#/$defs/DiagnosticIssue"
          },
          "maxItems": 20,
          "title": "Issues",
          "type": "array"
        },
        "last_success_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Success At"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "observed_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Observed At"
        },
        "owner": {
          "default": "application",
          "title": "Owner",
          "type": "string"
        },
        "stale": {
          "default": false,
          "title": "Stale",
          "type": "boolean"
        },
        "status": {
          "default": "unknown",
          "enum": [
            "ok",
            "degraded",
            "unavailable",
            "unknown"
          ],
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "name",
        "collected_at"
      ],
      "title": "DiagnosticSection",
      "type": "object"
    },
    "DiagnosticSnapshot": {
      "additionalProperties": false,
      "properties": {
        "collected_at": {
          "title": "Collected At",
          "type": "number"
        },
        "counter_scope": {
          "const": "current_instance",
          "default": "current_instance",
          "title": "Counter Scope",
          "type": "string"
        },
        "environment": {
          "$ref": "#/$defs/DiagnosticEnvironment"
        },
        "instance_id": {
          "title": "Instance Id",
          "type": "string"
        },
        "persistence": {
          "$ref": "#/$defs/PersistenceDiagnostics"
        },
        "registry": {
          "$ref": "#/$defs/RegistryDiagnostics"
        },
        "schema_version": {
          "const": 1,
          "default": 1,
          "title": "Schema Version",
          "type": "integer"
        },
        "sections": {
          "items": {
            "$ref": "#/$defs/DiagnosticSection"
          },
          "title": "Sections",
          "type": "array"
        },
        "summary": {
          "$ref": "#/$defs/DiagnosticSummary"
        }
      },
      "required": [
        "instance_id",
        "collected_at",
        "sections",
        "summary",
        "registry",
        "environment",
        "persistence"
      ],
      "title": "DiagnosticSnapshot",
      "type": "object"
    },
    "DiagnosticSummary": {
      "additionalProperties": false,
      "properties": {
        "counts_by_status": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Counts By Status",
          "type": "object"
        },
        "findings": {
          "items": {
            "$ref": "#/$defs/DiagnosticFinding"
          },
          "maxItems": 100,
          "title": "Findings",
          "type": "array"
        },
        "ready": {
          "title": "Ready",
          "type": "boolean"
        },
        "status": {
          "enum": [
            "ok",
            "degraded",
            "unavailable",
            "unknown"
          ],
          "title": "Status",
          "type": "string"
        },
        "truncated": {
          "default": false,
          "title": "Truncated",
          "type": "boolean"
        }
      },
      "required": [
        "status",
        "ready",
        "counts_by_status"
      ],
      "title": "DiagnosticSummary",
      "type": "object"
    },
    "EventDelivery": {
      "additionalProperties": false,
      "properties": {
        "failed": {
          "default": 0,
          "minimum": 0,
          "title": "Failed",
          "type": "integer"
        },
        "owner": {
          "title": "Owner",
          "type": "string"
        },
        "sent": {
          "default": 0,
          "minimum": 0,
          "title": "Sent",
          "type": "integer"
        },
        "targeted": {
          "default": 0,
          "minimum": 0,
          "title": "Targeted",
          "type": "integer"
        },
        "unavailable": {
          "default": 0,
          "minimum": 0,
          "title": "Unavailable",
          "type": "integer"
        }
      },
      "required": [
        "owner"
      ],
      "title": "EventDelivery",
      "type": "object"
    },
    "EventDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "accepting": {
          "title": "Accepting",
          "type": "boolean"
        },
        "active": {
          "items": {
            "$ref": "#/$defs/EventRecord"
          },
          "title": "Active",
          "type": "array"
        },
        "active_dispatches": {
          "default": 0,
          "title": "Active Dispatches",
          "type": "integer"
        },
        "active_listeners_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Active Listeners By Owner",
          "type": "object"
        },
        "emitted": {
          "title": "Emitted",
          "type": "integer"
        },
        "failed_listeners": {
          "title": "Failed Listeners",
          "type": "integer"
        },
        "notification_delivery": {
          "const": "inline",
          "default": "inline",
          "title": "Notification Delivery",
          "type": "string"
        },
        "pending_waits": {
          "default": 0,
          "title": "Pending Waits",
          "type": "integer"
        },
        "pending_workers": {
          "default": 0,
          "title": "Pending Workers",
          "type": "integer"
        },
        "recent": {
          "items": {
            "$ref": "#/$defs/EventRecord"
          },
          "title": "Recent",
          "type": "array"
        },
        "rejections_by_reason": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Rejections By Reason",
          "type": "object"
        },
        "subscriptions": {
          "title": "Subscriptions",
          "type": "integer"
        },
        "subscriptions_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Subscriptions By Owner",
          "type": "object"
        },
        "suppressed": {
          "title": "Suppressed",
          "type": "integer"
        },
        "timeouts_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Timeouts By Owner",
          "type": "object"
        },
        "workers_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Workers By Owner",
          "type": "object"
        }
      },
      "required": [
        "accepting",
        "emitted",
        "suppressed",
        "failed_listeners",
        "subscriptions",
        "active",
        "recent"
      ],
      "title": "EventDiagnostics",
      "type": "object"
    },
    "EventOptions": {
      "additionalProperties": false,
      "properties": {
        "history_limit": {
          "default": 200,
          "maximum": 10000,
          "minimum": 0,
          "title": "History Limit",
          "type": "integer"
        },
        "hook_timeout_seconds": {
          "default": 120,
          "exclusiveMinimum": 0,
          "maximum": 3600,
          "title": "Hook Timeout Seconds",
          "type": "number"
        },
        "listener_timeout_seconds": {
          "default": 30,
          "exclusiveMinimum": 0,
          "maximum": 3600,
          "title": "Listener Timeout Seconds",
          "type": "number"
        },
        "max_active": {
          "default": 256,
          "maximum": 10000,
          "minimum": 1,
          "title": "Max Active",
          "type": "integer"
        },
        "max_depth": {
          "default": 32,
          "maximum": 128,
          "minimum": 1,
          "title": "Max Depth",
          "type": "integer"
        },
        "max_workers": {
          "anyOf": [
            {
              "maximum": 10000,
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Max Workers"
        },
        "max_workers_per_owner": {
          "anyOf": [
            {
              "maximum": 10000,
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Max Workers Per Owner"
        }
      },
      "title": "EventOptions",
      "type": "object"
    },
    "EventRecord": {
      "additionalProperties": false,
      "properties": {
        "cancellation_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Cancellation Reason"
        },
        "correlation_id": {
          "title": "Correlation Id",
          "type": "string"
        },
        "deliveries": {
          "items": {
            "$ref": "#/$defs/EventDelivery"
          },
          "title": "Deliveries",
          "type": "array"
        },
        "duration_ms": {
          "default": 0,
          "title": "Duration Ms",
          "type": "number"
        },
        "event_id": {
          "title": "Event Id",
          "type": "string"
        },
        "failures": {
          "items": {
            "$ref": "#/$defs/ListenerFailure"
          },
          "title": "Failures",
          "type": "array"
        },
        "listeners": {
          "items": {
            "$ref": "#/$defs/ListenerRecord"
          },
          "title": "Listeners",
          "type": "array"
        },
        "listeners_called": {
          "default": 0,
          "title": "Listeners Called",
          "type": "integer"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "rejection_reason": {
          "anyOf": [
            {
              "enum": [
                "recursion",
                "depth_limit",
                "capacity",
                "shutdown"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Rejection Reason"
        },
        "source": {
          "title": "Source",
          "type": "string"
        },
        "status": {
          "enum": [
            "dispatching",
            "completed",
            "partial",
            "cancelled",
            "suppressed"
          ],
          "title": "Status",
          "type": "string"
        },
        "timestamp": {
          "title": "Timestamp",
          "type": "number"
        }
      },
      "required": [
        "event_id",
        "correlation_id",
        "name",
        "source",
        "timestamp",
        "status"
      ],
      "title": "EventRecord",
      "type": "object"
    },
    "EventsDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "activity": {
          "$ref": "#/$defs/EventDiagnostics"
        },
        "capacity": {
          "$ref": "#/$defs/EventOptions"
        },
        "kind": {
          "const": "events",
          "default": "events",
          "title": "Kind",
          "type": "string"
        }
      },
      "required": [
        "activity",
        "capacity"
      ],
      "title": "EventsDiagnostics",
      "type": "object"
    },
    "ListenerFailure": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "enum": [
            "event_listener_failed",
            "event_listener_timeout",
            "event_depth_limit",
            "event_capacity"
          ],
          "title": "Code",
          "type": "string"
        },
        "error_type": {
          "title": "Error Type",
          "type": "string"
        },
        "owner": {
          "title": "Owner",
          "type": "string"
        }
      },
      "required": [
        "owner",
        "error_type",
        "code"
      ],
      "title": "ListenerFailure",
      "type": "object"
    },
    "ListenerRecord": {
      "additionalProperties": false,
      "properties": {
        "duration_ms": {
          "default": 0,
          "minimum": 0,
          "title": "Duration Ms",
          "type": "number"
        },
        "failure": {
          "anyOf": [
            {
              "$ref": "#/$defs/ListenerFailure"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "listener_name": {
          "title": "Listener Name",
          "type": "string"
        },
        "observer": {
          "title": "Observer",
          "type": "boolean"
        },
        "owner": {
          "title": "Owner",
          "type": "string"
        },
        "status": {
          "default": "running",
          "enum": [
            "running",
            "completed",
            "failed",
            "timed_out",
            "cancelled"
          ],
          "title": "Status",
          "type": "string"
        },
        "subscription_id": {
          "title": "Subscription Id",
          "type": "string"
        }
      },
      "required": [
        "subscription_id",
        "owner",
        "observer",
        "listener_name"
      ],
      "title": "ListenerRecord",
      "type": "object"
    },
    "MetricsDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "attempts": {
          "default": 0,
          "title": "Attempts",
          "type": "integer"
        },
        "failures": {
          "default": 0,
          "title": "Failures",
          "type": "integer"
        },
        "interval_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Interval Seconds"
        },
        "kind": {
          "const": "metrics",
          "default": "metrics",
          "title": "Kind",
          "type": "string"
        },
        "last_duration_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Duration Ms"
        },
        "last_error_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Error Type"
        },
        "last_sample_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Sample At"
        },
        "missed_intervals": {
          "default": 0,
          "title": "Missed Intervals",
          "type": "integer"
        },
        "sample_age_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sample Age Seconds"
        },
        "successes": {
          "default": 0,
          "title": "Successes",
          "type": "integer"
        },
        "unavailable_measurements": {
          "items": {
            "type": "string"
          },
          "title": "Unavailable Measurements",
          "type": "array"
        },
        "warming_up": {
          "default": true,
          "title": "Warming Up",
          "type": "boolean"
        }
      },
      "title": "MetricsDiagnostics",
      "type": "object"
    },
    "PersistenceDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "accepting": {
          "title": "Accepting",
          "type": "boolean"
        },
        "dropped": {
          "title": "Dropped",
          "type": "integer"
        },
        "history_limit": {
          "title": "History Limit",
          "type": "integer"
        },
        "queue_limit": {
          "title": "Queue Limit",
          "type": "integer"
        },
        "queued": {
          "title": "Queued",
          "type": "integer"
        },
        "retention_days": {
          "title": "Retention Days",
          "type": "integer"
        },
        "write_failures": {
          "title": "Write Failures",
          "type": "integer"
        }
      },
      "required": [
        "queued",
        "queue_limit",
        "dropped",
        "write_failures",
        "accepting",
        "history_limit",
        "retention_days"
      ],
      "title": "PersistenceDiagnostics",
      "type": "object"
    },
    "PluginDiagnostic": {
      "additionalProperties": false,
      "properties": {
        "active_tasks": {
          "title": "Active Tasks",
          "type": "integer"
        },
        "diagnostic_providers": {
          "default": 0,
          "title": "Diagnostic Providers",
          "type": "integer"
        },
        "drain_failures": {
          "default": 0,
          "title": "Drain Failures",
          "type": "integer"
        },
        "draining": {
          "title": "Draining",
          "type": "boolean"
        },
        "generation": {
          "title": "Generation",
          "type": "integer"
        },
        "last_drain_duration_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Drain Duration Ms"
        },
        "last_transition_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Transition At"
        },
        "listeners": {
          "default": 0,
          "title": "Listeners",
          "type": "integer"
        },
        "load_failures": {
          "default": 0,
          "title": "Load Failures",
          "type": "integer"
        },
        "managed_tasks": {
          "default": 0,
          "title": "Managed Tasks",
          "type": "integer"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "status": {
          "title": "Status",
          "type": "string"
        },
        "version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Version"
        },
        "workers": {
          "default": 0,
          "title": "Workers",
          "type": "integer"
        }
      },
      "required": [
        "name",
        "status",
        "generation",
        "active_tasks",
        "draining"
      ],
      "title": "PluginDiagnostic",
      "type": "object"
    },
    "PluginValues": {
      "additionalProperties": false,
      "description": "Explicit observations; string dumps and secrets are excluded.",
      "properties": {
        "health": {
          "default": "unknown",
          "enum": [
            "ok",
            "degraded",
            "unknown"
          ],
          "title": "Health",
          "type": "string"
        },
        "kind": {
          "const": "plugin_values",
          "default": "plugin_values",
          "title": "Kind",
          "type": "string"
        },
        "units": {
          "additionalProperties": {
            "enum": [
              "count",
              "seconds",
              "milliseconds",
              "bytes",
              "percent"
            ],
            "type": "string"
          },
          "maxProperties": 50,
          "title": "Units",
          "type": "object"
        },
        "values": {
          "additionalProperties": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ]
          },
          "maxProperties": 50,
          "title": "Values",
          "type": "object"
        }
      },
      "required": [
        "values"
      ],
      "title": "PluginValues",
      "type": "object"
    },
    "PluginsDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "plugins",
          "default": "plugins",
          "title": "Kind",
          "type": "string"
        },
        "plugins": {
          "items": {
            "$ref": "#/$defs/PluginDiagnostic"
          },
          "title": "Plugins",
          "type": "array"
        },
        "total": {
          "default": 0,
          "title": "Total",
          "type": "integer"
        },
        "truncated": {
          "default": false,
          "title": "Truncated",
          "type": "boolean"
        }
      },
      "title": "PluginsDiagnostics",
      "type": "object"
    },
    "ProcessDiagnostic": {
      "additionalProperties": false,
      "properties": {
        "expected_status": {
          "title": "Expected Status",
          "type": "string"
        },
        "last_error_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Error Type"
        },
        "observed_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Observed At"
        },
        "observed_running": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Observed Running"
        },
        "pid": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Pid"
        },
        "server_name": {
          "title": "Server Name",
          "type": "string"
        }
      },
      "required": [
        "server_name",
        "expected_status"
      ],
      "title": "ProcessDiagnostic",
      "type": "object"
    },
    "ProcessesDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "processes",
          "default": "processes",
          "title": "Kind",
          "type": "string"
        },
        "last_monitor_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Monitor At"
        },
        "monitor_failures": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Monitor Failures"
        },
        "observation_available": {
          "title": "Observation Available",
          "type": "boolean"
        },
        "observed_running": {
          "title": "Observed Running",
          "type": "integer"
        },
        "processes": {
          "items": {
            "$ref": "#/$defs/ProcessDiagnostic"
          },
          "title": "Processes",
          "type": "array"
        },
        "registered": {
          "title": "Registered",
          "type": "integer"
        },
        "truncated": {
          "default": false,
          "title": "Truncated",
          "type": "boolean"
        }
      },
      "required": [
        "registered",
        "observed_running",
        "observation_available"
      ],
      "title": "ProcessesDiagnostics",
      "type": "object"
    },
    "RegistryDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "failures": {
          "default": 0,
          "title": "Failures",
          "type": "integer"
        },
        "max_providers": {
          "title": "Max Providers",
          "type": "integer"
        },
        "max_providers_per_owner": {
          "title": "Max Providers Per Owner",
          "type": "integer"
        },
        "owner_limits_scope": {
          "const": "plugins",
          "default": "plugins",
          "title": "Owner Limits Scope",
          "type": "string"
        },
        "pending": {
          "title": "Pending",
          "type": "integer"
        },
        "pending_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Pending By Owner",
          "type": "object"
        },
        "registered": {
          "title": "Registered",
          "type": "integer"
        },
        "registered_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Registered By Owner",
          "type": "object"
        },
        "rejected": {
          "default": 0,
          "title": "Rejected",
          "type": "integer"
        },
        "timeouts": {
          "default": 0,
          "title": "Timeouts",
          "type": "integer"
        }
      },
      "required": [
        "registered",
        "pending",
        "max_providers",
        "max_providers_per_owner"
      ],
      "title": "RegistryDiagnostics",
      "type": "object"
    },
    "RuntimeDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "runtime",
          "default": "runtime",
          "title": "Kind",
          "type": "string"
        },
        "phase": {
          "title": "Phase",
          "type": "string"
        },
        "pid": {
          "title": "Pid",
          "type": "integer"
        },
        "python_version": {
          "title": "Python Version",
          "type": "string"
        },
        "ready": {
          "default": false,
          "title": "Ready",
          "type": "boolean"
        },
        "shutdown_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Shutdown Reason"
        },
        "shutdown_requested": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Shutdown Requested"
        },
        "stage": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stage"
        },
        "stage_elapsed_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stage Elapsed Seconds"
        },
        "stage_started_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stage Started At"
        },
        "stage_timeout_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stage Timeout Seconds"
        },
        "uptime_seconds": {
          "title": "Uptime Seconds",
          "type": "number"
        },
        "version": {
          "title": "Version",
          "type": "string"
        }
      },
      "required": [
        "phase",
        "pid",
        "uptime_seconds",
        "version",
        "python_version"
      ],
      "title": "RuntimeDiagnostics",
      "type": "object"
    },
    "StateDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "counts": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Counts",
          "type": "object"
        },
        "epoch": {
          "title": "Epoch",
          "type": "string"
        },
        "kind": {
          "const": "state",
          "default": "state",
          "title": "Kind",
          "type": "string"
        },
        "observation_revision": {
          "title": "Observation Revision",
          "type": "integer"
        },
        "oldest_pending_age_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Oldest Pending Age Seconds"
        },
        "pending_changes": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Pending Changes",
          "type": "object"
        }
      },
      "required": [
        "epoch",
        "observation_revision",
        "counts",
        "pending_changes"
      ],
      "title": "StateDiagnostics",
      "type": "object"
    },
    "StorageDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "active": {
          "default": 0,
          "title": "Active",
          "type": "integer"
        },
        "attempts": {
          "default": 0,
          "title": "Attempts",
          "type": "integer"
        },
        "failures": {
          "default": 0,
          "title": "Failures",
          "type": "integer"
        },
        "kind": {
          "const": "storage",
          "default": "storage",
          "title": "Kind",
          "type": "string"
        },
        "last_duration_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Duration Ms"
        },
        "last_error_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Error Type"
        },
        "last_reload_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Reload At"
        },
        "last_reload_duration_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Reload Duration Ms"
        },
        "last_reload_error_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Reload Error Type"
        },
        "last_success_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Success At"
        },
        "lock_wait_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Lock Wait Ms"
        },
        "lock_waiters": {
          "default": 0,
          "title": "Lock Waiters",
          "type": "integer"
        },
        "max_lock_wait_ms": {
          "default": 0,
          "title": "Max Lock Wait Ms",
          "type": "number"
        },
        "reload_active": {
          "default": false,
          "title": "Reload Active",
          "type": "boolean"
        },
        "reload_attempts": {
          "default": 0,
          "title": "Reload Attempts",
          "type": "integer"
        },
        "reload_failures": {
          "default": 0,
          "title": "Reload Failures",
          "type": "integer"
        },
        "reload_successes": {
          "default": 0,
          "title": "Reload Successes",
          "type": "integer"
        },
        "successes": {
          "default": 0,
          "title": "Successes",
          "type": "integer"
        },
        "total_lock_wait_ms": {
          "default": 0,
          "title": "Total Lock Wait Ms",
          "type": "number"
        }
      },
      "title": "StorageDiagnostics",
      "type": "object"
    },
    "TaskDiagnostic": {
      "additionalProperties": false,
      "properties": {
        "cancellation_requested": {
          "default": false,
          "title": "Cancellation Requested",
          "type": "boolean"
        },
        "correlation_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Correlation Id"
        },
        "elapsed_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Elapsed Seconds"
        },
        "error_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Code"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "name": {
          "default": "background_task",
          "title": "Name",
          "type": "string"
        },
        "owner": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Owner"
        },
        "progress_percent": {
          "anyOf": [
            {
              "maximum": 100,
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Progress Percent"
        },
        "status": {
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "id",
        "status"
      ],
      "title": "TaskDiagnostic",
      "type": "object"
    },
    "TasksDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "accepting": {
          "title": "Accepting",
          "type": "boolean"
        },
        "active": {
          "title": "Active",
          "type": "integer"
        },
        "capacity": {
          "default": 100,
          "title": "Capacity",
          "type": "integer"
        },
        "counts_by_status": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Counts By Status",
          "type": "object"
        },
        "kind": {
          "const": "tasks",
          "default": "tasks",
          "title": "Kind",
          "type": "string"
        },
        "oldest_active_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Oldest Active Seconds"
        },
        "tasks": {
          "items": {
            "$ref": "#/$defs/TaskDiagnostic"
          },
          "title": "Tasks",
          "type": "array"
        }
      },
      "required": [
        "active",
        "counts_by_status",
        "accepting"
      ],
      "title": "TasksDiagnostics",
      "type": "object"
    },
    "TransportDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "accepting": {
          "default": true,
          "title": "Accepting",
          "type": "boolean"
        },
        "active_sends": {
          "default": 0,
          "title": "Active Sends",
          "type": "integer"
        },
        "connected_clients": {
          "title": "Connected Clients",
          "type": "integer"
        },
        "delivery_mode": {
          "const": "direct",
          "default": "direct",
          "title": "Delivery Mode",
          "type": "string"
        },
        "disconnects_by_reason": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Disconnects By Reason",
          "type": "object"
        },
        "dropped_messages": {
          "default": 0,
          "title": "Dropped Messages",
          "type": "integer"
        },
        "failed_sends": {
          "default": 0,
          "title": "Failed Sends",
          "type": "integer"
        },
        "high_water_mark": {
          "default": 0,
          "title": "High Water Mark",
          "type": "integer"
        },
        "kind": {
          "const": "transport",
          "default": "transport",
          "title": "Kind",
          "type": "string"
        },
        "last_send_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Send At"
        },
        "last_send_duration_ms": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Send Duration Ms"
        },
        "max_pending_per_client": {
          "default": 0,
          "title": "Max Pending Per Client",
          "type": "integer"
        },
        "pending_sends": {
          "default": 0,
          "title": "Pending Sends",
          "type": "integer"
        },
        "queue_limit_per_client": {
          "default": 64,
          "title": "Queue Limit Per Client",
          "type": "integer"
        },
        "send_timeouts": {
          "default": 0,
          "title": "Send Timeouts",
          "type": "integer"
        },
        "subscriptions": {
          "title": "Subscriptions",
          "type": "integer"
        },
        "successful_sends": {
          "default": 0,
          "title": "Successful Sends",
          "type": "integer"
        },
        "topics": {
          "title": "Topics",
          "type": "integer"
        }
      },
      "required": [
        "connected_clients",
        "subscriptions",
        "topics"
      ],
      "title": "TransportDiagnostics",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "generated_at": {
      "title": "Generated At",
      "type": "number"
    },
    "history": {
      "$ref": "#/$defs/DiagnosticHistory"
    },
    "report_id": {
      "title": "Report Id",
      "type": "string"
    },
    "runs": {
      "anyOf": [
        {
          "$ref": "#/$defs/DiagnosticRuns"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "snapshot": {
      "$ref": "#/$defs/DiagnosticSnapshot"
    }
  },
  "required": [
    "snapshot",
    "history"
  ],
  "title": "GetDiagnosticReportResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.GetDiagnosticReportRequest` | `REQUIRED` |

---


## `diagnostics.get_diagnostic_runs`
```python
await self.api.diagnostics.get_diagnostic_runs(request: bedrock_server_manager.api.models.diagnostics.GetDiagnosticRunsRequest)
```
- **Async (Requires await):** Yes

- **Description:** List retained application instances without guessing whether older runs are alive.

- **Returns:** `GetDiagnosticRunsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetDiagnosticRunsRequest
payload = {}
request = GetDiagnosticRunsRequest(**payload)
result = await self.api.diagnostics.get_diagnostic_runs(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "limit": {
      "default": 20,
      "maximum": 50,
      "minimum": 1,
      "title": "Limit",
      "type": "integer"
    }
  },
  "title": "GetDiagnosticRunsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "DiagnosticRun": {
      "additionalProperties": false,
      "properties": {
        "backend_version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Backend Version"
        },
        "cancelled_records": {
          "title": "Cancelled Records",
          "type": "integer"
        },
        "current_instance": {
          "title": "Current Instance",
          "type": "boolean"
        },
        "failed_records": {
          "title": "Failed Records",
          "type": "integer"
        },
        "first_record_at": {
          "title": "First Record At",
          "type": "number"
        },
        "instance_id": {
          "title": "Instance Id",
          "type": "string"
        },
        "last_observed_phase": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Observed Phase"
        },
        "last_record_at": {
          "title": "Last Record At",
          "type": "number"
        },
        "recording_closed": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Recording Closed"
        },
        "retained_records": {
          "title": "Retained Records",
          "type": "integer"
        }
      },
      "required": [
        "instance_id",
        "first_record_at",
        "last_record_at",
        "retained_records",
        "failed_records",
        "cancelled_records",
        "current_instance"
      ],
      "title": "DiagnosticRun",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "available": {
      "title": "Available",
      "type": "boolean"
    },
    "runs": {
      "items": {
        "$ref": "#/$defs/DiagnosticRun"
      },
      "title": "Runs",
      "type": "array"
    },
    "truncated": {
      "title": "Truncated",
      "type": "boolean"
    }
  },
  "required": [
    "runs",
    "available",
    "truncated"
  ],
  "title": "GetDiagnosticRunsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.GetDiagnosticRunsRequest` | `REQUIRED` |

---


## `diagnostics.get_diagnostic_trace`
```python
await self.api.diagnostics.get_diagnostic_trace(request: bedrock_server_manager.api.models.diagnostics.GetDiagnosticTraceRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read events, tasks, and retained failures sharing one correlation identity.

- **Returns:** `GetDiagnosticTraceResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetDiagnosticTraceRequest
payload = {...}  # Supply required request fields below.
request = GetDiagnosticTraceRequest(**payload)
result = await self.api.diagnostics.get_diagnostic_trace(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "correlation_id": {
      "maxLength": 160,
      "minLength": 1,
      "title": "Correlation Id",
      "type": "string"
    },
    "cursor": {
      "anyOf": [
        {
          "maxLength": 512,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Cursor"
    },
    "limit": {
      "default": 100,
      "maximum": 200,
      "minimum": 1,
      "title": "Limit",
      "type": "integer"
    }
  },
  "required": [
    "correlation_id"
  ],
  "title": "GetDiagnosticTraceRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "DiagnosticHistory": {
      "additionalProperties": false,
      "properties": {
        "available": {
          "title": "Available",
          "type": "boolean"
        },
        "next_cursor": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Next Cursor"
        },
        "records": {
          "items": {
            "$ref": "#/$defs/DiagnosticRecord"
          },
          "title": "Records",
          "type": "array"
        },
        "truncated": {
          "title": "Truncated",
          "type": "boolean"
        }
      },
      "required": [
        "records",
        "available",
        "truncated"
      ],
      "title": "DiagnosticHistory",
      "type": "object"
    },
    "DiagnosticRecord": {
      "additionalProperties": false,
      "properties": {
        "backend_version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Backend Version"
        },
        "code": {
          "maxLength": 80,
          "title": "Code",
          "type": "string"
        },
        "correlation_id": {
          "anyOf": [
            {
              "maxLength": 160,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Correlation Id"
        },
        "duration_ms": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Duration Ms"
        },
        "error_type": {
          "anyOf": [
            {
              "maxLength": 80,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Type"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "instance_id": {
          "title": "Instance Id",
          "type": "string"
        },
        "operation": {
          "maxLength": 160,
          "title": "Operation",
          "type": "string"
        },
        "operation_id": {
          "anyOf": [
            {
              "maxLength": 160,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Operation Id"
        },
        "outcome": {
          "enum": [
            "completed",
            "failed",
            "cancelled"
          ],
          "title": "Outcome",
          "type": "string"
        },
        "owner": {
          "anyOf": [
            {
              "maxLength": 160,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Owner"
        },
        "phase": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Phase"
        },
        "subsystem": {
          "maxLength": 80,
          "pattern": "^[\\w.:-]+$",
          "title": "Subsystem",
          "type": "string"
        },
        "timestamp": {
          "title": "Timestamp",
          "type": "number"
        }
      },
      "required": [
        "id",
        "instance_id",
        "timestamp",
        "subsystem",
        "operation",
        "outcome",
        "code"
      ],
      "title": "DiagnosticRecord",
      "type": "object"
    },
    "EventDelivery": {
      "additionalProperties": false,
      "properties": {
        "failed": {
          "default": 0,
          "minimum": 0,
          "title": "Failed",
          "type": "integer"
        },
        "owner": {
          "title": "Owner",
          "type": "string"
        },
        "sent": {
          "default": 0,
          "minimum": 0,
          "title": "Sent",
          "type": "integer"
        },
        "targeted": {
          "default": 0,
          "minimum": 0,
          "title": "Targeted",
          "type": "integer"
        },
        "unavailable": {
          "default": 0,
          "minimum": 0,
          "title": "Unavailable",
          "type": "integer"
        }
      },
      "required": [
        "owner"
      ],
      "title": "EventDelivery",
      "type": "object"
    },
    "EventDiagnostics": {
      "additionalProperties": false,
      "properties": {
        "accepting": {
          "title": "Accepting",
          "type": "boolean"
        },
        "active": {
          "items": {
            "$ref": "#/$defs/EventRecord"
          },
          "title": "Active",
          "type": "array"
        },
        "active_dispatches": {
          "default": 0,
          "title": "Active Dispatches",
          "type": "integer"
        },
        "active_listeners_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Active Listeners By Owner",
          "type": "object"
        },
        "emitted": {
          "title": "Emitted",
          "type": "integer"
        },
        "failed_listeners": {
          "title": "Failed Listeners",
          "type": "integer"
        },
        "notification_delivery": {
          "const": "inline",
          "default": "inline",
          "title": "Notification Delivery",
          "type": "string"
        },
        "pending_waits": {
          "default": 0,
          "title": "Pending Waits",
          "type": "integer"
        },
        "pending_workers": {
          "default": 0,
          "title": "Pending Workers",
          "type": "integer"
        },
        "recent": {
          "items": {
            "$ref": "#/$defs/EventRecord"
          },
          "title": "Recent",
          "type": "array"
        },
        "rejections_by_reason": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Rejections By Reason",
          "type": "object"
        },
        "subscriptions": {
          "title": "Subscriptions",
          "type": "integer"
        },
        "subscriptions_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Subscriptions By Owner",
          "type": "object"
        },
        "suppressed": {
          "title": "Suppressed",
          "type": "integer"
        },
        "timeouts_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Timeouts By Owner",
          "type": "object"
        },
        "workers_by_owner": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Workers By Owner",
          "type": "object"
        }
      },
      "required": [
        "accepting",
        "emitted",
        "suppressed",
        "failed_listeners",
        "subscriptions",
        "active",
        "recent"
      ],
      "title": "EventDiagnostics",
      "type": "object"
    },
    "EventRecord": {
      "additionalProperties": false,
      "properties": {
        "cancellation_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Cancellation Reason"
        },
        "correlation_id": {
          "title": "Correlation Id",
          "type": "string"
        },
        "deliveries": {
          "items": {
            "$ref": "#/$defs/EventDelivery"
          },
          "title": "Deliveries",
          "type": "array"
        },
        "duration_ms": {
          "default": 0,
          "title": "Duration Ms",
          "type": "number"
        },
        "event_id": {
          "title": "Event Id",
          "type": "string"
        },
        "failures": {
          "items": {
            "$ref": "#/$defs/ListenerFailure"
          },
          "title": "Failures",
          "type": "array"
        },
        "listeners": {
          "items": {
            "$ref": "#/$defs/ListenerRecord"
          },
          "title": "Listeners",
          "type": "array"
        },
        "listeners_called": {
          "default": 0,
          "title": "Listeners Called",
          "type": "integer"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "rejection_reason": {
          "anyOf": [
            {
              "enum": [
                "recursion",
                "depth_limit",
                "capacity",
                "shutdown"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Rejection Reason"
        },
        "source": {
          "title": "Source",
          "type": "string"
        },
        "status": {
          "enum": [
            "dispatching",
            "completed",
            "partial",
            "cancelled",
            "suppressed"
          ],
          "title": "Status",
          "type": "string"
        },
        "timestamp": {
          "title": "Timestamp",
          "type": "number"
        }
      },
      "required": [
        "event_id",
        "correlation_id",
        "name",
        "source",
        "timestamp",
        "status"
      ],
      "title": "EventRecord",
      "type": "object"
    },
    "ListenerFailure": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "enum": [
            "event_listener_failed",
            "event_listener_timeout",
            "event_depth_limit",
            "event_capacity"
          ],
          "title": "Code",
          "type": "string"
        },
        "error_type": {
          "title": "Error Type",
          "type": "string"
        },
        "owner": {
          "title": "Owner",
          "type": "string"
        }
      },
      "required": [
        "owner",
        "error_type",
        "code"
      ],
      "title": "ListenerFailure",
      "type": "object"
    },
    "ListenerRecord": {
      "additionalProperties": false,
      "properties": {
        "duration_ms": {
          "default": 0,
          "minimum": 0,
          "title": "Duration Ms",
          "type": "number"
        },
        "failure": {
          "anyOf": [
            {
              "$ref": "#/$defs/ListenerFailure"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "listener_name": {
          "title": "Listener Name",
          "type": "string"
        },
        "observer": {
          "title": "Observer",
          "type": "boolean"
        },
        "owner": {
          "title": "Owner",
          "type": "string"
        },
        "status": {
          "default": "running",
          "enum": [
            "running",
            "completed",
            "failed",
            "timed_out",
            "cancelled"
          ],
          "title": "Status",
          "type": "string"
        },
        "subscription_id": {
          "title": "Subscription Id",
          "type": "string"
        }
      },
      "required": [
        "subscription_id",
        "owner",
        "observer",
        "listener_name"
      ],
      "title": "ListenerRecord",
      "type": "object"
    },
    "TaskDiagnostic": {
      "additionalProperties": false,
      "properties": {
        "cancellation_requested": {
          "default": false,
          "title": "Cancellation Requested",
          "type": "boolean"
        },
        "correlation_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Correlation Id"
        },
        "elapsed_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Elapsed Seconds"
        },
        "error_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Code"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "name": {
          "default": "background_task",
          "title": "Name",
          "type": "string"
        },
        "owner": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Owner"
        },
        "progress_percent": {
          "anyOf": [
            {
              "maximum": 100,
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Progress Percent"
        },
        "status": {
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "id",
        "status"
      ],
      "title": "TaskDiagnostic",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "correlation_id": {
      "title": "Correlation Id",
      "type": "string"
    },
    "events": {
      "anyOf": [
        {
          "$ref": "#/$defs/EventDiagnostics"
        },
        {
          "type": "null"
        }
      ]
    },
    "history": {
      "$ref": "#/$defs/DiagnosticHistory"
    },
    "tasks": {
      "items": {
        "$ref": "#/$defs/TaskDiagnostic"
      },
      "title": "Tasks",
      "type": "array"
    },
    "tasks_available": {
      "title": "Tasks Available",
      "type": "boolean"
    },
    "truncated": {
      "default": false,
      "title": "Truncated",
      "type": "boolean"
    }
  },
  "required": [
    "correlation_id",
    "events",
    "tasks",
    "tasks_available",
    "history"
  ],
  "title": "GetDiagnosticTraceResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.diagnostics.GetDiagnosticTraceRequest` | `REQUIRED` |

---


## `install.install_new_server`
```python
await self.api.install.install_new_server(request: bedrock_server_manager.api.models.install.InstallNewServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Installs a new server instance.

- **Returns:** `InstallNewServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import InstallNewServerRequest
payload = {'server_name': 'example'}
request = InstallNewServerRequest(**payload)
result = await self.api.install.install_new_server(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "server_zip_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Server Zip Path"
    },
    "target_version": {
      "default": "LATEST",
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Target Version",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "InstallNewServerRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "allOf": [
    {
      "if": {
        "properties": {
          "status": {
            "const": "success"
          }
        }
      },
      "then": {
        "properties": {
          "version": {
            "not": {
              "type": "null"
            }
          }
        },
        "required": [
          "version"
        ]
      }
    }
  ],
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    },
    "version": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Version"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "InstallNewServerResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.install.InstallNewServerRequest` | `REQUIRED` |

---


## `install.update_server`
```python
await self.api.install.update_server(request: bedrock_server_manager.api.models.install.UpdateServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Updates an existing server instance.

- **Returns:** `UpdateServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import UpdateServerRequest
payload = {'server_name': 'example'}
request = UpdateServerRequest(**payload)
result = await self.api.install.update_server(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "send_message": {
      "default": true,
      "title": "Send Message",
      "type": "boolean"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "UpdateServerRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "allOf": [
    {
      "if": {
        "properties": {
          "status": {
            "const": "success"
          }
        }
      },
      "then": {
        "properties": {
          "updated": {
            "not": {
              "type": "null"
            }
          }
        },
        "required": [
          "updated"
        ]
      }
    }
  ],
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "new_version": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "New Version"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    },
    "updated": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Updated"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "UpdateServerResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.install.UpdateServerRequest` | `REQUIRED` |

---


## `misc.prune_download_cache`
```python
await self.api.misc.prune_download_cache(request: bedrock_server_manager.api.models.misc.PruneDownloadCacheRequest)
```
- **Async (Requires await):** Yes

- **Description:** Prunes old downloaded server archives (.zip) in a directory.

- **Returns:** `PruneDownloadCacheResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import PruneDownloadCacheRequest
payload = {...}  # Supply required request fields below.
request = PruneDownloadCacheRequest(**payload)
result = await self.api.misc.prune_download_cache(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "download_dir": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Download Dir",
      "type": "string"
    },
    "keep_count": {
      "anyOf": [
        {
          "minimum": 0,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Keep Count"
    }
  },
  "required": [
    "download_dir"
  ],
  "title": "PruneDownloadCacheRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "CleanupResult": {
      "additionalProperties": false,
      "properties": {
        "deleted": {
          "items": {
            "type": "string"
          },
          "title": "Deleted",
          "type": "array"
        },
        "failures": {
          "additionalProperties": {
            "$ref": "#/$defs/FailureInfo"
          },
          "title": "Failures",
          "type": "object"
        },
        "outcome": {
          "default": "noop",
          "enum": [
            "completed",
            "partial",
            "failed",
            "noop"
          ],
          "title": "Outcome",
          "type": "string"
        },
        "retained": {
          "items": {
            "type": "string"
          },
          "title": "Retained",
          "type": "array"
        }
      },
      "title": "CleanupResult",
      "type": "object"
    },
    "FailureInfo": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "enum": [
            "validation_error",
            "not_found",
            "conflict",
            "forbidden",
            "unauthorized",
            "http_error",
            "operation_canceled",
            "invalid_server_name",
            "server_start_failed",
            "server_stop_failed",
            "server_error",
            "application_error",
            "internal_error",
            "unavailable",
            "operation_incomplete",
            "file_error",
            "storage_error",
            "configuration_error",
            "network_error",
            "system_error"
          ],
          "title": "Code",
          "type": "string"
        },
        "details": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Details",
          "type": "object"
        },
        "message": {
          "title": "Message",
          "type": "string"
        }
      },
      "required": [
        "code",
        "message"
      ],
      "title": "FailureInfo",
      "type": "object"
    },
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "result": {
      "$ref": "#/$defs/CleanupResult"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message"
  ],
  "title": "PruneDownloadCacheResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.misc.PruneDownloadCacheRequest` | `REQUIRED` |

---


## `permissions.get_permissions`
```python
await self.api.permissions.get_permissions(request: bedrock_server_manager.api.models.permissions.GetPermissionsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the permissions configuration for a server, formatted with player names.

- **Returns:** `GetPermissionsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetPermissionsRequest
payload = {'server_name': 'example'}
request = GetPermissionsRequest(**payload)
result = await self.api.permissions.get_permissions(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "GetPermissionsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "PlayerPermission": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "permission_level": {
          "title": "Permission Level",
          "type": "string"
        },
        "xuid": {
          "title": "Xuid",
          "type": "string"
        }
      },
      "required": [
        "xuid",
        "name",
        "permission_level"
      ],
      "title": "PlayerPermission",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "permissions": {
      "items": {
        "$ref": "#/$defs/PlayerPermission"
      },
      "title": "Permissions",
      "type": "array"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "permissions"
  ],
  "title": "GetPermissionsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.permissions.GetPermissionsRequest` | `REQUIRED` |

---


## `permissions.set_permissions`
```python
await self.api.permissions.set_permissions(request: bedrock_server_manager.api.models.permissions.SetPermissionsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Set a player's permission level for a given server.

- **Returns:** `SetPermissionsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SetPermissionsRequest
payload = {...}  # Supply required request fields below.
request = SetPermissionsRequest(**payload)
result = await self.api.permissions.set_permissions(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "permission": {
      "enum": [
        "visitor",
        "member",
        "operator"
      ],
      "title": "Permission",
      "type": "string"
    },
    "player_name": {
      "anyOf": [
        {
          "minLength": 1,
          "pattern": ".*\\S.*",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Player Name"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "xuid": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Xuid",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "xuid",
    "player_name",
    "permission"
  ],
  "title": "SetPermissionsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "SetPermissionsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.permissions.SetPermissionsRequest` | `REQUIRED` |

---


## `player.add_players_manually`
```python
await self.api.player.add_players_manually(request: bedrock_server_manager.api.models.player.AddPlayersManuallyRequest)
```
- **Async (Requires await):** Yes

- **Description:** Adds or updates player data in the database.

- **Returns:** `AddPlayersManuallyResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import AddPlayersManuallyRequest
payload = {...}  # Supply required request fields below.
request = AddPlayersManuallyRequest(**payload)
result = await self.api.player.add_players_manually(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "player_strings": {
      "items": {
        "minLength": 1,
        "pattern": ".*\\S.*",
        "type": "string"
      },
      "minItems": 1,
      "title": "Player Strings",
      "type": "array"
    }
  },
  "required": [
    "player_strings"
  ],
  "title": "AddPlayersManuallyRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "count": {
      "minimum": 0,
      "title": "Count",
      "type": "integer"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "parsed_count": {
      "minimum": 0,
      "title": "Parsed Count",
      "type": "integer"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    },
    "submitted_count": {
      "minimum": 0,
      "title": "Submitted Count",
      "type": "integer"
    },
    "unique_count": {
      "minimum": 0,
      "title": "Unique Count",
      "type": "integer"
    }
  },
  "required": [
    "count",
    "submitted_count",
    "parsed_count",
    "unique_count"
  ],
  "title": "AddPlayersManuallyResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.player.AddPlayersManuallyRequest` | `REQUIRED` |

---


## `player.get_all_known_players`
```python
await self.api.player.get_all_known_players(request: bedrock_server_manager.api.models.player.GetAllKnownPlayersRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return all player data from the database.

- **Returns:** `GetAllKnownPlayersResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetAllKnownPlayersRequest
payload = {}
request = GetAllKnownPlayersRequest(**payload)
result = await self.api.player.get_all_known_players(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetAllKnownPlayersRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "PlayerInfo": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "xuid": {
          "title": "Xuid",
          "type": "string"
        }
      },
      "required": [
        "name",
        "xuid"
      ],
      "title": "PlayerInfo",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "players": {
      "items": {
        "$ref": "#/$defs/PlayerInfo"
      },
      "title": "Players",
      "type": "array"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "players"
  ],
  "title": "GetAllKnownPlayersResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.player.GetAllKnownPlayersRequest` | `REQUIRED` |

---


## `player.scan_and_update_player_db`
```python
await self.api.player.scan_and_update_player_db(request: bedrock_server_manager.api.models.player.ScanAndUpdatePlayerDbRequest)
```
- **Async (Requires await):** Yes

- **Description:** Scans all server logs to discover and save player data.

- **Returns:** `ScanAndUpdatePlayerDbResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ScanAndUpdatePlayerDbRequest
payload = {}
request = ScanAndUpdatePlayerDbRequest(**payload)
result = await self.api.player.scan_and_update_player_db(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ScanAndUpdatePlayerDbRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "FailureInfo": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "enum": [
            "validation_error",
            "not_found",
            "conflict",
            "forbidden",
            "unauthorized",
            "http_error",
            "operation_canceled",
            "invalid_server_name",
            "server_start_failed",
            "server_stop_failed",
            "server_error",
            "application_error",
            "internal_error",
            "unavailable",
            "operation_incomplete",
            "file_error",
            "storage_error",
            "configuration_error",
            "network_error",
            "system_error"
          ],
          "title": "Code",
          "type": "string"
        },
        "details": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Details",
          "type": "object"
        },
        "message": {
          "title": "Message",
          "type": "string"
        }
      },
      "required": [
        "code",
        "message"
      ],
      "title": "FailureInfo",
      "type": "object"
    },
    "JsonValue": {},
    "PlayerScanDetails": {
      "additionalProperties": false,
      "properties": {
        "actually_saved_or_updated_in_db": {
          "minimum": 0,
          "title": "Actually Saved Or Updated In Db",
          "type": "integer"
        },
        "scan_errors": {
          "items": {
            "$ref": "#/$defs/PlayerScanError"
          },
          "title": "Scan Errors",
          "type": "array"
        },
        "total_entries_in_logs": {
          "minimum": 0,
          "title": "Total Entries In Logs",
          "type": "integer"
        },
        "unique_players_submitted_for_saving": {
          "minimum": 0,
          "title": "Unique Players Submitted For Saving",
          "type": "integer"
        }
      },
      "required": [
        "total_entries_in_logs",
        "unique_players_submitted_for_saving",
        "actually_saved_or_updated_in_db"
      ],
      "title": "PlayerScanDetails",
      "type": "object"
    },
    "PlayerScanError": {
      "additionalProperties": false,
      "properties": {
        "error": {
          "$ref": "#/$defs/FailureInfo"
        },
        "server": {
          "title": "Server",
          "type": "string"
        }
      },
      "required": [
        "server",
        "error"
      ],
      "title": "PlayerScanError",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "details": {
      "$ref": "#/$defs/PlayerScanDetails"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "details"
  ],
  "title": "ScanAndUpdatePlayerDbResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.player.ScanAndUpdatePlayerDbRequest` | `REQUIRED` |

---


## `plugins.get_plugin_setting`
```python
await self.api.plugins.get_plugin_setting(request: bedrock_server_manager.api.models.plugins.GetPluginSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read settings scoped to the bridge-injected plugin identity.

- **Returns:** `GetPluginSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetPluginSettingRequest
payload = {...}  # Supply required request fields below.
request = GetPluginSettingRequest(**payload)
result = await self.api.plugins.get_plugin_setting(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "key": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Key",
      "type": "string"
    }
  },
  "required": [
    "key"
  ],
  "title": "GetPluginSettingRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    },
    "value": {
      "$ref": "#/$defs/JsonValue"
    }
  },
  "required": [
    "value"
  ],
  "title": "GetPluginSettingResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.plugins.GetPluginSettingRequest` | `REQUIRED` |

---


## `plugins.get_plugin_statuses`
```python
await self.api.plugins.get_plugin_statuses(request: bedrock_server_manager.api.models.plugins.GetPluginStatusesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the statuses and metadata of all discovered plugins.

- **Returns:** `GetPluginStatusesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetPluginStatusesRequest
payload = {}
request = GetPluginStatusesRequest(**payload)
result = await self.api.plugins.get_plugin_statuses(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetPluginStatusesRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "PluginInfo": {
      "additionalProperties": false,
      "properties": {
        "author": {
          "default": "",
          "title": "Author",
          "type": "string"
        },
        "description": {
          "default": "",
          "title": "Description",
          "type": "string"
        },
        "enabled": {
          "title": "Enabled",
          "type": "boolean"
        },
        "has_settings": {
          "default": false,
          "title": "Has Settings",
          "type": "boolean"
        },
        "status": {
          "default": "UNKNOWN",
          "title": "Status",
          "type": "string"
        },
        "version": {
          "default": "N/A",
          "title": "Version",
          "type": "string"
        }
      },
      "required": [
        "enabled"
      ],
      "title": "PluginInfo",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "plugins": {
      "additionalProperties": {
        "$ref": "#/$defs/PluginInfo"
      },
      "title": "Plugins",
      "type": "object"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "plugins"
  ],
  "title": "GetPluginStatusesResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.plugins.GetPluginStatusesRequest` | `REQUIRED` |

---


## `plugins.set_plugin_setting`
```python
await self.api.plugins.set_plugin_setting(request: bedrock_server_manager.api.models.plugins.SetPluginSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Persist settings scoped to the bridge-injected plugin identity.

- **Returns:** `SetPluginSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SetPluginSettingRequest
payload = {...}  # Supply required request fields below.
request = SetPluginSettingRequest(**payload)
result = await self.api.plugins.set_plugin_setting(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "key": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Key",
      "type": "string"
    },
    "value": {
      "$ref": "#/$defs/JsonValue"
    }
  },
  "required": [
    "key",
    "value"
  ],
  "title": "SetPluginSettingRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message"
  ],
  "title": "SetPluginSettingResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.plugins.SetPluginSettingRequest` | `REQUIRED` |

---


## `properties.get_properties`
```python
await self.api.properties.get_properties(request: bedrock_server_manager.api.models.properties.GetPropertiesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the current server properties for a given server.

- **Returns:** `GetPropertiesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetPropertiesRequest
payload = {'server_name': 'example'}
request = GetPropertiesRequest(**payload)
result = await self.api.properties.get_properties(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "GetPropertiesRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "properties": {
      "additionalProperties": {
        "type": "string"
      },
      "title": "Properties",
      "type": "object"
    },
    "raw_content": {
      "title": "Raw Content",
      "type": "string"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "properties",
    "raw_content"
  ],
  "title": "GetPropertiesResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.properties.GetPropertiesRequest` | `REQUIRED` |

---


## `properties.get_raw_properties`
```python
await self.api.properties.get_raw_properties(request: bedrock_server_manager.api.models.properties.GetRawPropertiesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read the complete properties document without parsing its keys or comments.

- **Returns:** `GetRawPropertiesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetRawPropertiesRequest
payload = {'server_name': 'example'}
request = GetRawPropertiesRequest(**payload)
result = await self.api.properties.get_raw_properties(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "GetRawPropertiesRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "raw_content": {
      "title": "Raw Content",
      "type": "string"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "raw_content"
  ],
  "title": "GetRawPropertiesResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.properties.GetRawPropertiesRequest` | `REQUIRED` |

---


## `properties.set_properties`
```python
await self.api.properties.set_properties(request: bedrock_server_manager.api.models.properties.SetPropertiesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Set one or multiple server properties for a given server.

- **Returns:** `SetPropertiesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SetPropertiesRequest
payload = {...}  # Supply required request fields below.
request = SetPropertiesRequest(**payload)
result = await self.api.properties.set_properties(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "properties_to_update": {
      "additionalProperties": {
        "type": "string"
      },
      "title": "Properties To Update",
      "type": "object"
    },
    "restart_after_modify": {
      "default": false,
      "title": "Restart After Modify",
      "type": "boolean"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "properties_to_update"
  ],
  "title": "SetPropertiesRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "SetPropertiesResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.properties.SetPropertiesRequest` | `REQUIRED` |

---


## `properties.validate_property_value`
```python
self.api.properties.validate_property_value(request: bedrock_server_manager.api.models.properties.ValidatePropertyValueRequest)
```
- **Async (Requires await):** No

- **Description:** Validates a specific server property value before it gets applied.

- **Returns:** `ValidatePropertyValueResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ValidatePropertyValueRequest
payload = {...}  # Supply required request fields below.
request = ValidatePropertyValueRequest(**payload)
result = self.api.properties.validate_property_value(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "property_name": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Property Name",
      "type": "string"
    },
    "value": {
      "title": "Value",
      "type": "string"
    }
  },
  "required": [
    "property_name",
    "value"
  ],
  "title": "ValidatePropertyValueRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    },
    "valid": {
      "title": "Valid",
      "type": "boolean"
    }
  },
  "required": [
    "valid"
  ],
  "title": "ValidatePropertyValueResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.properties.ValidatePropertyValueRequest` | `REQUIRED` |

---


## `server.get_all_settings`
```python
await self.api.server.get_all_settings(request: bedrock_server_manager.api.models.server.GetAllServerSettingsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads the entire persisted configurationuration for a specific server from its

- **Returns:** `GetAllServerSettingsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetAllServerSettingsRequest
payload = {'server_name': 'example'}
request = GetAllServerSettingsRequest(**payload)
result = await self.api.server.get_all_settings(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "GetAllServerSettingsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "settings": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Settings",
      "type": "object"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "settings"
  ],
  "title": "GetAllServerSettingsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.GetAllServerSettingsRequest` | `REQUIRED` |

---


## `server.get_setting`
```python
await self.api.server.get_setting(request: bedrock_server_manager.api.models.server.GetServerSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads any value from a server's specific persisted configuration

- **Returns:** `GetServerSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetServerSettingRequest
payload = {...}  # Supply required request fields below.
request = GetServerSettingRequest(**payload)
result = await self.api.server.get_setting(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "key": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Key",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "key"
  ],
  "title": "GetServerSettingRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    },
    "value": {
      "$ref": "#/$defs/JsonValue"
    }
  },
  "required": [
    "value"
  ],
  "title": "GetServerSettingResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.GetServerSettingRequest` | `REQUIRED` |

---


## `server.get_summary`
```python
await self.api.server.get_summary(request: bedrock_server_manager.api.models.server.GetServerSummaryRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the summary information for a specific server.

- **Returns:** `GetServerSummaryResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetServerSummaryRequest
payload = {'server_name': 'example'}
request = GetServerSummaryRequest(**payload)
result = await self.api.server.get_summary(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "GetServerSummaryRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "PlayerInfo": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "xuid": {
          "title": "Xuid",
          "type": "string"
        }
      },
      "required": [
        "name",
        "xuid"
      ],
      "title": "PlayerInfo",
      "type": "object"
    },
    "ServerSummary": {
      "additionalProperties": false,
      "properties": {
        "epoch": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Epoch"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "player_count": {
          "default": 0,
          "minimum": 0,
          "title": "Player Count",
          "type": "integer"
        },
        "players": {
          "items": {
            "$ref": "#/$defs/PlayerInfo"
          },
          "title": "Players",
          "type": "array"
        },
        "players_available": {
          "default": true,
          "title": "Players Available",
          "type": "boolean"
        },
        "revision": {
          "anyOf": [
            {
              "maximum": 9007199254740991,
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Revision"
        },
        "status": {
          "title": "Status",
          "type": "string"
        },
        "version": {
          "title": "Version",
          "type": "string"
        }
      },
      "required": [
        "name",
        "status",
        "version"
      ],
      "title": "ServerSummary",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    },
    "summary": {
      "$ref": "#/$defs/ServerSummary"
    }
  },
  "required": [
    "summary"
  ],
  "title": "GetServerSummaryResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.GetServerSummaryRequest` | `REQUIRED` |

---


## `server.get_valid_names`
```python
await self.api.server.get_valid_names(request: bedrock_server_manager.api.models.server.GetValidServerNamesRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return current registered server names without sampling processes.

- **Returns:** `GetValidServerNamesResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetValidServerNamesRequest
payload = {}
request = GetValidServerNamesRequest(**payload)
result = await self.api.server.get_valid_names(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetValidServerNamesRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "server_names": {
      "items": {
        "examples": [
          "example"
        ],
        "minLength": 1,
        "pattern": "^[a-zA-Z0-9_-]+$",
        "type": "string"
      },
      "title": "Server Names",
      "type": "array"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "server_names"
  ],
  "title": "GetValidServerNamesResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.GetValidServerNamesRequest` | `REQUIRED` |

---


## `server.restart`
```python
await self.api.server.restart(request: bedrock_server_manager.api.models.server.RestartServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Orchestrate stop/start; abort on cancellation or either phase failing.

- **Returns:** `RestartServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import RestartServerRequest
payload = {'server_name': 'example'}
request = RestartServerRequest(**payload)
result = await self.api.server.restart(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "send_message": {
      "default": true,
      "title": "Send Message",
      "type": "boolean"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "RestartServerRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "outcome": {
      "enum": [
        "restarted",
        "started"
      ],
      "title": "Outcome",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "outcome",
    "message"
  ],
  "title": "RestartServerResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.RestartServerRequest` | `REQUIRED` |

---


## `server.send_command`
```python
await self.api.server.send_command(request: bedrock_server_manager.api.models.server.SendCommandRequest)
```
- **Async (Requires await):** Yes

- **Description:** Sends a command to a running Bedrock server.

- **Returns:** `SendCommandResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SendCommandRequest
payload = {...}  # Supply required request fields below.
request = SendCommandRequest(**payload)
result = await self.api.server.send_command(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "command": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Command",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "command"
  ],
  "title": "SendCommandRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "SendCommandResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.SendCommandRequest` | `REQUIRED` |

---


## `server.set_custom_value`
```python
await self.api.server.set_custom_value(request: bedrock_server_manager.api.models.server.SetServerCustomValueRequest)
```
- **Async (Requires await):** Yes

- **Description:** Writes a key-value pair to the 'custom' section of a server's specific

- **Returns:** `SetServerCustomValueResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SetServerCustomValueRequest
payload = {...}  # Supply required request fields below.
request = SetServerCustomValueRequest(**payload)
result = await self.api.server.set_custom_value(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "key": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Key",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "value": {
      "$ref": "#/$defs/JsonValue"
    }
  },
  "required": [
    "server_name",
    "key",
    "value"
  ],
  "title": "SetServerCustomValueRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "SetServerCustomValueResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.SetServerCustomValueRequest` | `REQUIRED` |

---


## `server.start`
```python
await self.api.server.start(request: bedrock_server_manager.api.models.server.StartServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Start a server, or report that it is already running; failures raise.

- **Returns:** `StartServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import StartServerRequest
payload = {'server_name': 'example'}
request = StartServerRequest(**payload)
result = await self.api.server.start(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "StartServerRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "outcome": {
      "enum": [
        "started",
        "already_running"
      ],
      "title": "Outcome",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "outcome",
    "message"
  ],
  "title": "StartServerResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.StartServerRequest` | `REQUIRED` |

---


## `server.stop`
```python
await self.api.server.stop(request: bedrock_server_manager.api.models.server.StopServerRequest)
```
- **Async (Requires await):** Yes

- **Description:** Stop a server, or report that it is already stopped; failures raise.

- **Returns:** `StopServerResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import StopServerRequest
payload = {'server_name': 'example'}
request = StopServerRequest(**payload)
result = await self.api.server.stop(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "StopServerRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "outcome": {
      "enum": [
        "stopped",
        "already_stopped"
      ],
      "title": "Outcome",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "outcome",
    "message"
  ],
  "title": "StopServerResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.server.StopServerRequest` | `REQUIRED` |

---


## `settings.get_all_global_settings`
```python
await self.api.settings.get_all_global_settings(request: bedrock_server_manager.api.models.settings.GetAllGlobalSettingsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads the entire global application settings configuration.

- **Returns:** `GetAllGlobalSettingsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetAllGlobalSettingsRequest
payload = {}
request = GetAllGlobalSettingsRequest(**payload)
result = await self.api.settings.get_all_global_settings(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetAllGlobalSettingsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "settings": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Settings",
      "type": "object"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "settings"
  ],
  "title": "GetAllGlobalSettingsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.settings.GetAllGlobalSettingsRequest` | `REQUIRED` |

---


## `settings.get_global_setting`
```python
await self.api.settings.get_global_setting(request: bedrock_server_manager.api.models.settings.GetGlobalSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Reads a single value from the global application settings.

- **Returns:** `GetGlobalSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetGlobalSettingRequest
payload = {...}  # Supply required request fields below.
request = GetGlobalSettingRequest(**payload)
result = await self.api.settings.get_global_setting(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "key": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Key",
      "type": "string"
    }
  },
  "required": [
    "key"
  ],
  "title": "GetGlobalSettingRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    },
    "value": {
      "$ref": "#/$defs/JsonValue"
    }
  },
  "required": [
    "value"
  ],
  "title": "GetGlobalSettingResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.settings.GetGlobalSettingRequest` | `REQUIRED` |

---


## `settings.set_custom_global_setting`
```python
await self.api.settings.set_custom_global_setting(request: bedrock_server_manager.api.models.settings.SetCustomGlobalSettingRequest)
```
- **Async (Requires await):** Yes

- **Description:** Writes a custom value to the global application settings.

- **Returns:** `SetCustomGlobalSettingResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SetCustomGlobalSettingRequest
payload = {...}  # Supply required request fields below.
request = SetCustomGlobalSettingRequest(**payload)
result = await self.api.settings.set_custom_global_setting(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "key": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Key",
      "type": "string"
    },
    "value": {
      "$ref": "#/$defs/JsonValue"
    }
  },
  "required": [
    "key",
    "value"
  ],
  "title": "SetCustomGlobalSettingRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message"
  ],
  "title": "SetCustomGlobalSettingResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.settings.SetCustomGlobalSettingRequest` | `REQUIRED` |

---


## `system.get_application_health`
```python
await self.api.system.get_application_health(request: bedrock_server_manager.api.models.health.GetApplicationHealthRequest)
```
- **Async (Requires await):** Yes

- **Description:** Read-only readiness checks; dependency errors never expose credentials.

- **Returns:** `GetApplicationHealthResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetApplicationHealthRequest
payload = {}
request = GetApplicationHealthRequest(**payload)
result = await self.api.system.get_application_health(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetApplicationHealthRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "HealthCheck": {
      "additionalProperties": false,
      "properties": {
        "healthy": {
          "title": "Healthy",
          "type": "boolean"
        },
        "message": {
          "title": "Message",
          "type": "string"
        },
        "status": {
          "const": "success",
          "default": "success",
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "message",
        "healthy"
      ],
      "title": "HealthCheck",
      "type": "object"
    },
    "LifecyclePhase": {
      "enum": [
        "starting",
        "ready",
        "stopping",
        "stopped",
        "failed"
      ],
      "title": "LifecyclePhase",
      "type": "string"
    }
  },
  "additionalProperties": false,
  "properties": {
    "checked_at": {
      "exclusiveMinimum": 0,
      "title": "Checked At",
      "type": "number"
    },
    "checks": {
      "additionalProperties": {
        "$ref": "#/$defs/HealthCheck"
      },
      "title": "Checks",
      "type": "object"
    },
    "health": {
      "enum": [
        "healthy",
        "degraded"
      ],
      "title": "Health",
      "type": "string"
    },
    "lifecycle": {
      "$ref": "#/$defs/LifecyclePhase"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "lifecycle",
    "health",
    "checks",
    "checked_at"
  ],
  "title": "GetApplicationHealthResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.health.GetApplicationHealthRequest` | `REQUIRED` |

---


## `system.get_application_metrics`
```python
await self.api.system.get_application_metrics(request: bedrock_server_manager.api.models.metrics.GetApplicationMetricsRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return shared, bounded performance history without sampling per request.

- **Returns:** `GetApplicationMetricsResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetApplicationMetricsRequest
payload = {}
request = GetApplicationMetricsRequest(**payload)
result = await self.api.system.get_application_metrics(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetApplicationMetricsRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "MetricsSample": {
      "additionalProperties": false,
      "properties": {
        "app_cpu_percent": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "App Cpu Percent"
        },
        "app_ram_mb": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "App Ram Mb"
        },
        "asyncio_task_count": {
          "minimum": 0,
          "title": "Asyncio Task Count",
          "type": "integer"
        },
        "background_task_count": {
          "minimum": 0,
          "title": "Background Task Count",
          "type": "integer"
        },
        "disk_read_kib_s": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Disk Read Kib S"
        },
        "disk_write_kib_s": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Disk Write Kib S"
        },
        "epoch": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Epoch"
        },
        "loop_lag_ms": {
          "minimum": 0,
          "title": "Loop Lag Ms",
          "type": "number"
        },
        "net_rx_kib_s": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Net Rx Kib S"
        },
        "net_tx_kib_s": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Net Tx Kib S"
        },
        "revision": {
          "anyOf": [
            {
              "maximum": 9007199254740991,
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Revision"
        },
        "servers": {
          "items": {
            "$ref": "#/$defs/ServerMetrics"
          },
          "title": "Servers",
          "type": "array"
        },
        "sys_cpu_percent": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sys Cpu Percent"
        },
        "sys_ram_mb": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sys Ram Mb"
        },
        "sys_ram_percent": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sys Ram Percent"
        },
        "sys_ram_total_mb": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sys Ram Total Mb"
        },
        "thread_count": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Thread Count"
        },
        "timestamp": {
          "exclusiveMinimum": 0,
          "title": "Timestamp",
          "type": "number"
        },
        "uptime_seconds": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Uptime Seconds"
        }
      },
      "required": [
        "timestamp",
        "asyncio_task_count",
        "background_task_count",
        "loop_lag_ms"
      ],
      "title": "MetricsSample",
      "type": "object"
    },
    "ServerMetrics": {
      "additionalProperties": false,
      "properties": {
        "cpu_percent": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Cpu Percent"
        },
        "memory_mb": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Memory Mb"
        },
        "pid": {
          "anyOf": [
            {
              "exclusiveMinimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Pid"
        },
        "server_name": {
          "title": "Server Name",
          "type": "string"
        }
      },
      "required": [
        "server_name"
      ],
      "title": "ServerMetrics",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "epoch": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Epoch"
    },
    "history": {
      "items": {
        "$ref": "#/$defs/MetricsSample"
      },
      "title": "History",
      "type": "array"
    },
    "history_limit": {
      "exclusiveMinimum": 0,
      "maximum": 180,
      "title": "History Limit",
      "type": "integer"
    },
    "interval_seconds": {
      "exclusiveMinimum": 0,
      "title": "Interval Seconds",
      "type": "number"
    },
    "latest": {
      "$ref": "#/$defs/MetricsSample"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "revision": {
      "anyOf": [
        {
          "maximum": 9007199254740991,
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Revision"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "latest",
    "history",
    "interval_seconds",
    "history_limit"
  ],
  "title": "GetApplicationMetricsResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.metrics.GetApplicationMetricsRequest` | `REQUIRED` |

---


## `system.get_bedrock_process_info`
```python
await self.api.system.get_bedrock_process_info(request: bedrock_server_manager.api.models.system.GetBedrockProcessInfoRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return resource usage for a running Bedrock server process.

- **Returns:** `GetBedrockProcessInfoResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetBedrockProcessInfoRequest
payload = {'server_name': 'example'}
request = GetBedrockProcessInfoRequest(**payload)
result = await self.api.system.get_bedrock_process_info(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "GetBedrockProcessInfoRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "ProcessInfo": {
      "additionalProperties": false,
      "properties": {
        "cpu_percent": {
          "title": "Cpu Percent",
          "type": "number"
        },
        "memory_mb": {
          "title": "Memory Mb",
          "type": "number"
        },
        "pid": {
          "title": "Pid",
          "type": "integer"
        },
        "uptime": {
          "title": "Uptime",
          "type": "string"
        }
      },
      "required": [
        "pid",
        "cpu_percent",
        "memory_mb",
        "uptime"
      ],
      "title": "ProcessInfo",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "epoch": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Epoch"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "process_info": {
      "anyOf": [
        {
          "$ref": "#/$defs/ProcessInfo"
        },
        {
          "type": "null"
        }
      ]
    },
    "revision": {
      "anyOf": [
        {
          "maximum": 9007199254740991,
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Revision"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "process_info"
  ],
  "title": "GetBedrockProcessInfoResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.system.GetBedrockProcessInfoRequest` | `REQUIRED` |

---


## `system.get_server_running_status`
```python
await self.api.system.get_server_running_status(request: bedrock_server_manager.api.models.system.GetServerRunningStatusRequest)
```
- **Async (Requires await):** Yes

- **Description:** Check if the server process is currently running.

- **Returns:** `GetServerRunningStatusResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetServerRunningStatusRequest
payload = {'server_name': 'example'}
request = GetServerRunningStatusRequest(**payload)
result = await self.api.system.get_server_running_status(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "GetServerRunningStatusRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "epoch": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Epoch"
    },
    "is_running": {
      "title": "Is Running",
      "type": "boolean"
    },
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "revision": {
      "anyOf": [
        {
          "maximum": 9007199254740991,
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Revision"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "is_running"
  ],
  "title": "GetServerRunningStatusResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.system.GetServerRunningStatusRequest` | `REQUIRED` |

---


## `websocket.websocket_broadcast`
```python
await self.api.websocket.websocket_broadcast(request: bedrock_server_manager.api.models.websocket.BroadcastRequest)
```
- **Async (Requires await):** Yes

- **Description:** Broadcasts a JSON payload to all WebSocket clients subscribed to a given topic.

- **Returns:** `BroadcastResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import BroadcastRequest
payload = {...}  # Supply required request fields below.
request = BroadcastRequest(**payload)
result = await self.api.websocket.websocket_broadcast(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "data": {
      "$ref": "#/$defs/JsonValue"
    },
    "topic": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Topic",
      "type": "string"
    }
  },
  "required": [
    "topic",
    "data"
  ],
  "title": "BroadcastRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "DeliveryResult": {
      "additionalProperties": false,
      "properties": {
        "failed": {
          "default": 0,
          "minimum": 0,
          "title": "Failed",
          "type": "integer"
        },
        "sent": {
          "default": 0,
          "minimum": 0,
          "title": "Sent",
          "type": "integer"
        },
        "targeted": {
          "default": 0,
          "minimum": 0,
          "title": "Targeted",
          "type": "integer"
        },
        "unavailable": {
          "default": 0,
          "minimum": 0,
          "title": "Unavailable",
          "type": "integer"
        }
      },
      "title": "DeliveryResult",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "delivery": {
      "$ref": "#/$defs/DeliveryResult"
    },
    "message": {
      "title": "Message",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message"
  ],
  "title": "BroadcastResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.websocket.BroadcastRequest` | `REQUIRED` |

---


## `websocket.websocket_publish_ws_event`
```python
await self.api.websocket.websocket_publish_ws_event(request: bedrock_server_manager.api.models.websocket.PublishWsEventRequest)
```
- **Async (Requires await):** Yes

- **Description:** Publishes a custom WebSocket event to topic 'ws_event:{event_name}'.

- **Returns:** `PublishWsEventResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import PublishWsEventRequest
payload = {...}  # Supply required request fields below.
request = PublishWsEventRequest(**payload)
result = await self.api.websocket.websocket_publish_ws_event(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "data": {
      "$ref": "#/$defs/JsonValue"
    },
    "event_name": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Event Name",
      "type": "string"
    }
  },
  "required": [
    "event_name",
    "data"
  ],
  "title": "PublishWsEventRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "DeliveryResult": {
      "additionalProperties": false,
      "properties": {
        "failed": {
          "default": 0,
          "minimum": 0,
          "title": "Failed",
          "type": "integer"
        },
        "sent": {
          "default": 0,
          "minimum": 0,
          "title": "Sent",
          "type": "integer"
        },
        "targeted": {
          "default": 0,
          "minimum": 0,
          "title": "Targeted",
          "type": "integer"
        },
        "unavailable": {
          "default": 0,
          "minimum": 0,
          "title": "Unavailable",
          "type": "integer"
        }
      },
      "title": "DeliveryResult",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "delivery": {
      "$ref": "#/$defs/DeliveryResult"
    },
    "message": {
      "title": "Message",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message"
  ],
  "title": "PublishWsEventResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.websocket.PublishWsEventRequest` | `REQUIRED` |

---


## `websocket.websocket_send_to_client`
```python
await self.api.websocket.websocket_send_to_client(request: bedrock_server_manager.api.models.websocket.SendToClientRequest)
```
- **Async (Requires await):** Yes

- **Description:** Sends a JSON payload directly to a specific connected WebSocket client ID.

- **Returns:** `SendToClientResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SendToClientRequest
payload = {...}  # Supply required request fields below.
request = SendToClientRequest(**payload)
result = await self.api.websocket.websocket_send_to_client(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "client_id": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Client Id",
      "type": "string"
    },
    "data": {
      "$ref": "#/$defs/JsonValue"
    }
  },
  "required": [
    "client_id",
    "data"
  ],
  "title": "SendToClientRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "DeliveryResult": {
      "additionalProperties": false,
      "properties": {
        "failed": {
          "default": 0,
          "minimum": 0,
          "title": "Failed",
          "type": "integer"
        },
        "sent": {
          "default": 0,
          "minimum": 0,
          "title": "Sent",
          "type": "integer"
        },
        "targeted": {
          "default": 0,
          "minimum": 0,
          "title": "Targeted",
          "type": "integer"
        },
        "unavailable": {
          "default": 0,
          "minimum": 0,
          "title": "Unavailable",
          "type": "integer"
        }
      },
      "title": "DeliveryResult",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "delivery": {
      "$ref": "#/$defs/DeliveryResult"
    },
    "message": {
      "title": "Message",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message"
  ],
  "title": "SendToClientResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.websocket.SendToClientRequest` | `REQUIRED` |

---


## `websocket.websocket_send_to_user`
```python
await self.api.websocket.websocket_send_to_user(request: bedrock_server_manager.api.models.websocket.SendToUserRequest)
```
- **Async (Requires await):** Yes

- **Description:** Sends a JSON payload to all active WebSocket connections belonging to a user.

- **Returns:** `SendToUserResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import SendToUserRequest
payload = {...}  # Supply required request fields below.
request = SendToUserRequest(**payload)
result = await self.api.websocket.websocket_send_to_user(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "properties": {
    "data": {
      "$ref": "#/$defs/JsonValue"
    },
    "username": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Username",
      "type": "string"
    }
  },
  "required": [
    "username",
    "data"
  ],
  "title": "SendToUserRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "$defs": {
    "DeliveryResult": {
      "additionalProperties": false,
      "properties": {
        "failed": {
          "default": 0,
          "minimum": 0,
          "title": "Failed",
          "type": "integer"
        },
        "sent": {
          "default": 0,
          "minimum": 0,
          "title": "Sent",
          "type": "integer"
        },
        "targeted": {
          "default": 0,
          "minimum": 0,
          "title": "Targeted",
          "type": "integer"
        },
        "unavailable": {
          "default": 0,
          "minimum": 0,
          "title": "Unavailable",
          "type": "integer"
        }
      },
      "title": "DeliveryResult",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "delivery": {
      "$ref": "#/$defs/DeliveryResult"
    },
    "message": {
      "title": "Message",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message"
  ],
  "title": "SendToUserResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.websocket.SendToUserRequest` | `REQUIRED` |

---


## `websocket.websocket_unregister_data_provider`
```python
await self.api.websocket.websocket_unregister_data_provider(request: bedrock_server_manager.api.models.websocket.UnregisterDataProviderRequest)
```
- **Async (Requires await):** Yes

- **Description:** Unregisters a data provider handler for a WebSocket topic.

- **Returns:** `UnregisterDataProviderResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import UnregisterDataProviderRequest
payload = {...}  # Supply required request fields below.
request = UnregisterDataProviderRequest(**payload)
result = await self.api.websocket.websocket_unregister_data_provider(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "topic": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Topic",
      "type": "string"
    }
  },
  "required": [
    "topic"
  ],
  "title": "UnregisterDataProviderRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "outcome": {
      "enum": [
        "removed",
        "already_absent"
      ],
      "title": "Outcome",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "outcome"
  ],
  "title": "UnregisterDataProviderResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.websocket.UnregisterDataProviderRequest` | `REQUIRED` |

---


## `world.export_world`
```python
await self.api.world.export_world(request: bedrock_server_manager.api.models.world.ExportWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Export the server's currently active world to a .mcworld archive.

- **Returns:** `ExportWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ExportWorldRequest
payload = {'server_name': 'example'}
request = ExportWorldRequest(**payload)
result = await self.api.world.export_world(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "export_dir": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Export Dir"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "ExportWorldRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "allOf": [
    {
      "if": {
        "properties": {
          "status": {
            "const": "success"
          }
        }
      },
      "then": {
        "properties": {
          "export_file": {
            "not": {
              "type": "null"
            }
          }
        },
        "required": [
          "export_file"
        ]
      }
    }
  ],
  "properties": {
    "export_file": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Export File"
    },
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "ExportWorldResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.world.ExportWorldRequest` | `REQUIRED` |

---


## `world.get_world_name`
```python
await self.api.world.get_world_name(request: bedrock_server_manager.api.models.world.GetWorldNameRequest)
```
- **Async (Requires await):** Yes

- **Description:** Return the configured world name (``level-name``) for a server.

- **Returns:** `GetWorldNameResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import GetWorldNameRequest
payload = {'server_name': 'example'}
request = GetWorldNameRequest(**payload)
result = await self.api.world.get_world_name(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    }
  },
  "required": [
    "server_name"
  ],
  "title": "GetWorldNameRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Message"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    },
    "world_name": {
      "title": "World Name",
      "type": "string"
    }
  },
  "required": [
    "world_name"
  ],
  "title": "GetWorldNameResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.world.GetWorldNameRequest` | `REQUIRED` |

---


## `world.import_world`
```python
await self.api.world.import_world(request: bedrock_server_manager.api.models.world.ImportWorldRequest)
```
- **Async (Requires await):** Yes

- **Description:** Import a world from a .mcworld file, replacing the active world.

- **Returns:** `ImportWorldResponse`

Runtime context and plugin identity are injected by the bridge. Failures raise application exceptions; plugin cancellation raises `APICancelledError`.

```python
from bedrock_server_manager.api.models import ImportWorldRequest
payload = {...}  # Supply required request fields below.
request = ImportWorldRequest(**payload)
result = await self.api.world.import_world(request)
data = result.model_dump(mode="json")
```

**Request schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "selected_file_path": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Selected File Path",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "stop_start_server": {
      "default": true,
      "title": "Stop Start Server",
      "type": "boolean"
    }
  },
  "required": [
    "server_name",
    "selected_file_path"
  ],
  "title": "ImportWorldRequest",
  "type": "object"
}
```

**Response schema:**

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "server_name": {
      "examples": [
        "example"
      ],
      "minLength": 1,
      "pattern": "^[a-zA-Z0-9_-]+$",
      "title": "Server Name",
      "type": "string"
    },
    "status": {
      "default": "success",
      "enum": [
        "success",
        "skipped",
        "partial"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "message",
    "server_name"
  ],
  "title": "ImportWorldResponse",
  "type": "object"
}
```

**Transport error schema:**

```json
{
  "$defs": {
    "JsonValue": {}
  },
  "additionalProperties": false,
  "description": "Safe serialized failure; Python callers receive exceptions.",
  "properties": {
    "code": {
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error"
      ],
      "title": "Code",
      "type": "string"
    },
    "details": {
      "additionalProperties": {
        "$ref": "#/$defs/JsonValue"
      },
      "title": "Details",
      "type": "object"
    },
    "message": {
      "title": "Message",
      "type": "string"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "APIErrorResponse",
  "type": "object"
}
```
**Parameters:**

| Name | Type | Default |
|------|------|---------|
| `request` | `bedrock_server_manager.api.models.world.ImportWorldRequest` | `REQUIRED` |
