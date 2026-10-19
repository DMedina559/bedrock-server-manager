# Plugin contract models

Schemas are listed once. Local `$defs` references identify other models on this page; assemble them under `$defs` when using a schema validator.

## APIErrorResponse

```json
{
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

## AddPlayersManuallyRequest

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

## AddPlayersManuallyResponse

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

## AddServerBanRequest

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

## AddServerBanResponse

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

## AddToAllowlistRequest

```json
{
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

## AddToAllowlistResponse

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

## AllowlistPlayer

```json
{
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
```

## AllowlistRemovalDetails

```json
{
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
```

## BackupAllRequest

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

## BackupAllResponse

```json
{
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

## BackupConfigFileRequest

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

## BackupConfigFileResponse

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

## BackupFile

```json
{
  "additionalProperties": false,
  "properties": {
    "component": {
      "enum": [
        "world",
        "server.properties",
        "allowlist.json",
        "permissions.json",
        "script_config",
        "bsm_settings"
      ],
      "title": "Component",
      "type": "string"
    },
    "path": {
      "title": "Path",
      "type": "string"
    },
    "sha256": {
      "pattern": "^[a-f0-9]{64}$",
      "title": "Sha256",
      "type": "string"
    },
    "size": {
      "minimum": 0,
      "title": "Size",
      "type": "integer"
    }
  },
  "required": [
    "path",
    "component",
    "size",
    "sha256"
  ],
  "title": "BackupFile",
  "type": "object"
}
```

## BackupManifest

```json
{
  "additionalProperties": false,
  "properties": {
    "backup_id": {
      "format": "uuid",
      "title": "Backup Id",
      "type": "string"
    },
    "bedrock_version": {
      "title": "Bedrock Version",
      "type": "string"
    },
    "bsm_version": {
      "title": "Bsm Version",
      "type": "string"
    },
    "capture_finished_at": {
      "format": "date-time",
      "title": "Capture Finished At",
      "type": "string"
    },
    "capture_method": {
      "enum": [
        "offline",
        "live"
      ],
      "title": "Capture Method",
      "type": "string"
    },
    "capture_started_at": {
      "format": "date-time",
      "title": "Capture Started At",
      "type": "string"
    },
    "components": {
      "additionalProperties": {
        "enum": [
          "included",
          "absent"
        ],
        "type": "string"
      },
      "propertyNames": {
        "enum": [
          "world",
          "server.properties",
          "allowlist.json",
          "permissions.json",
          "script_config",
          "bsm_settings"
        ]
      },
      "title": "Components",
      "type": "object"
    },
    "created_at": {
      "format": "date-time",
      "title": "Created At",
      "type": "string"
    },
    "directories": {
      "items": {
        "type": "string"
      },
      "title": "Directories",
      "type": "array"
    },
    "files": {
      "items": {
        "$ref": "#/$defs/BackupFile"
      },
      "title": "Files",
      "type": "array"
    },
    "format": {
      "const": "bsmbackup",
      "default": "bsmbackup",
      "title": "Format",
      "type": "string"
    },
    "format_version": {
      "const": 1,
      "default": 1,
      "title": "Format Version",
      "type": "integer"
    },
    "reason": {
      "default": "manual",
      "enum": [
        "manual",
        "pre_start",
        "pre_update"
      ],
      "title": "Reason",
      "type": "string"
    },
    "source_server": {
      "title": "Source Server",
      "type": "string"
    },
    "source_world": {
      "title": "Source World",
      "type": "string"
    },
    "warnings": {
      "items": {
        "type": "string"
      },
      "title": "Warnings",
      "type": "array"
    }
  },
  "required": [
    "backup_id",
    "created_at",
    "capture_started_at",
    "capture_finished_at",
    "bsm_version",
    "bedrock_version",
    "source_server",
    "source_world",
    "capture_method",
    "components",
    "files"
  ],
  "title": "BackupManifest",
  "type": "object"
}
```

## BackupSummary

```json
{
  "additionalProperties": false,
  "properties": {
    "backup_id": {
      "title": "Backup Id",
      "type": "string"
    },
    "encrypted": {
      "title": "Encrypted",
      "type": "boolean"
    },
    "error": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Error"
    },
    "filename": {
      "title": "Filename",
      "type": "string"
    },
    "key_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Key Id"
    },
    "manifest": {
      "anyOf": [
        {
          "$ref": "#/$defs/BackupManifest"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "size": {
      "title": "Size",
      "type": "integer"
    }
  },
  "required": [
    "backup_id",
    "filename",
    "size",
    "encrypted"
  ],
  "title": "BackupSummary",
  "type": "object"
}
```

## BackupWorldRequest

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

## BackupWorldResponse

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

## BanInfo

```json
{
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
```

## BroadcastRequest

```json
{
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

## BroadcastResponse

```json
{
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

## CleanupResult

```json
{
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
}
```

## CollectionDiagnostics

```json
{
  "additionalProperties": false,
  "properties": {
    "active": {
      "default": false,
      "title": "Active",
      "type": "boolean"
    },
    "cache_age_seconds": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Cache Age Seconds"
    },
    "cache_hits": {
      "default": 0,
      "title": "Cache Hits",
      "type": "integer"
    },
    "collections": {
      "default": 0,
      "title": "Collections",
      "type": "integer"
    },
    "failures": {
      "default": 0,
      "title": "Failures",
      "type": "integer"
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
    "last_periodic_error_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Last Periodic Error Type"
    },
    "last_periodic_success_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Last Periodic Success At"
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
    "periodic_cycles": {
      "default": 0,
      "title": "Periodic Cycles",
      "type": "integer"
    },
    "periodic_enabled": {
      "default": false,
      "title": "Periodic Enabled",
      "type": "boolean"
    },
    "periodic_failures": {
      "default": 0,
      "title": "Periodic Failures",
      "type": "integer"
    },
    "periodic_status": {
      "default": "disabled",
      "enum": [
        "disabled",
        "not_started",
        "running",
        "stopped",
        "failed"
      ],
      "title": "Periodic Status",
      "type": "string"
    },
    "requests": {
      "default": 0,
      "title": "Requests",
      "type": "integer"
    },
    "status": {
      "default": "ok",
      "enum": [
        "ok",
        "degraded",
        "unavailable"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "title": "CollectionDiagnostics",
  "type": "object"
}
```

## CompareDiagnosticSnapshotsRequest

```json
{
  "additionalProperties": false,
  "properties": {
    "after": {
      "$ref": "#/$defs/DiagnosticSnapshot"
    },
    "before": {
      "$ref": "#/$defs/DiagnosticSnapshot"
    }
  },
  "required": [
    "before",
    "after"
  ],
  "title": "CompareDiagnosticSnapshotsRequest",
  "type": "object"
}
```

## CompareDiagnosticSnapshotsResponse

```json
{
  "additionalProperties": false,
  "properties": {
    "after_snapshot_id": {
      "title": "After Snapshot Id",
      "type": "string"
    },
    "before_snapshot_id": {
      "title": "Before Snapshot Id",
      "type": "string"
    },
    "changes": {
      "items": {
        "$ref": "#/$defs/DiagnosticChange"
      },
      "maxItems": 200,
      "title": "Changes",
      "type": "array"
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
      "title": "Elapsed Seconds"
    },
    "same_instance": {
      "title": "Same Instance",
      "type": "boolean"
    },
    "truncated": {
      "default": false,
      "title": "Truncated",
      "type": "boolean"
    }
  },
  "required": [
    "before_snapshot_id",
    "after_snapshot_id",
    "same_instance",
    "elapsed_seconds"
  ],
  "title": "CompareDiagnosticSnapshotsResponse",
  "type": "object"
}
```

## CompletedItem

```json
{
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
}
```

## ComponentResults

```json
{
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
}
```

## CreateSnapshotRequest

```json
{
  "additionalProperties": false,
  "properties": {
    "encrypted": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Encrypted"
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
  "title": "CreateSnapshotRequest",
  "type": "object"
}
```

## CreateSnapshotResponse

```json
{
  "additionalProperties": false,
  "properties": {
    "backup": {
      "$ref": "#/$defs/BackupSummary"
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
    "server_name",
    "backup"
  ],
  "title": "CreateSnapshotResponse",
  "type": "object"
}
```

## DeliveryResult

```json
{
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
```

## DiagnosticChange

```json
{
  "additionalProperties": false,
  "properties": {
    "after": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "integer"
        },
        {
          "type": "boolean"
        },
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "After"
    },
    "before": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "integer"
        },
        {
          "type": "boolean"
        },
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Before"
    },
    "counter_reset": {
      "default": false,
      "title": "Counter Reset",
      "type": "boolean"
    },
    "delta": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Delta"
    },
    "field": {
      "title": "Field",
      "type": "string"
    },
    "subsystem": {
      "title": "Subsystem",
      "type": "string"
    }
  },
  "required": [
    "subsystem",
    "field",
    "before",
    "after"
  ],
  "title": "DiagnosticChange",
  "type": "object"
}
```

## DiagnosticEnvironment

```json
{
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
}
```

## DiagnosticFinding

```json
{
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
}
```

## DiagnosticHealthSample

```json
{
  "additionalProperties": false,
  "properties": {
    "ready": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "title": "Ready"
    },
    "sections": {
      "additionalProperties": {
        "enum": [
          "ok",
          "degraded",
          "unavailable",
          "unknown"
        ],
        "type": "string"
      },
      "maxProperties": 1000,
      "title": "Sections",
      "type": "object"
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
    }
  },
  "required": [
    "status",
    "ready",
    "sections"
  ],
  "title": "DiagnosticHealthSample",
  "type": "object"
}
```

## DiagnosticHistory

```json
{
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
}
```

## DiagnosticIssue

```json
{
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
}
```

## DiagnosticRecord

```json
{
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
    "health": {
      "anyOf": [
        {
          "$ref": "#/$defs/DiagnosticHealthSample"
        },
        {
          "type": "null"
        }
      ],
      "default": null
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
```

## DiagnosticRun

```json
{
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
```

## DiagnosticRuns

```json
{
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
}
```

## DiagnosticSection

```json
{
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
}
```

## DiagnosticSnapshot

```json
{
  "additionalProperties": false,
  "properties": {
    "collected_at": {
      "title": "Collected At",
      "type": "number"
    },
    "collection": {
      "$ref": "#/$defs/CollectionDiagnostics"
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
    "recent": {
      "anyOf": [
        {
          "$ref": "#/$defs/RecentDiagnosticWindow"
        },
        {
          "type": "null"
        }
      ],
      "default": null
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
      "maxItems": 1000,
      "title": "Sections",
      "type": "array"
    },
    "snapshot_id": {
      "title": "Snapshot Id",
      "type": "string"
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
}
```

## DiagnosticSummary

```json
{
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
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "title": "Ready"
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
}
```

## DisableAddonRequest

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

## DisableAddonResponse

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

## EnableAddonRequest

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

## EnableAddonResponse

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

## EventDelivery

```json
{
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
}
```

## EventDiagnostics

```json
{
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
    "active_truncated": {
      "default": false,
      "title": "Active Truncated",
      "type": "boolean"
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
    "recent_truncated": {
      "default": false,
      "title": "Recent Truncated",
      "type": "boolean"
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
}
```

## EventOptions

```json
{
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
}
```

## EventRecord

```json
{
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
}
```

## EventsDiagnostics

```json
{
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
    },
    "truncated": {
      "default": false,
      "title": "Truncated",
      "type": "boolean"
    }
  },
  "required": [
    "activity",
    "capacity"
  ],
  "title": "EventsDiagnostics",
  "type": "object"
}
```

## ExportWorldRequest

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

## ExportWorldResponse

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

## FailedItem

```json
{
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
}
```

## FailureInfo

```json
{
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
}
```

## GetAllGlobalSettingsRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetAllGlobalSettingsRequest",
  "type": "object"
}
```

## GetAllGlobalSettingsResponse

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

## GetAllKnownPlayersRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetAllKnownPlayersRequest",
  "type": "object"
}
```

## GetAllKnownPlayersResponse

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

## GetAllServerSettingsRequest

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

## GetAllServerSettingsResponse

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

## GetAllServersDataRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetAllServersDataRequest",
  "type": "object"
}
```

## GetAllServersDataResponse

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

## GetAllowlistRequest

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

## GetAllowlistResponse

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

## GetApplicationDiagnosticsRequest

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

## GetApplicationDiagnosticsResponse

```json
{
  "additionalProperties": false,
  "properties": {
    "collected_at": {
      "title": "Collected At",
      "type": "number"
    },
    "collection": {
      "$ref": "#/$defs/CollectionDiagnostics"
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
    "recent": {
      "anyOf": [
        {
          "$ref": "#/$defs/RecentDiagnosticWindow"
        },
        {
          "type": "null"
        }
      ],
      "default": null
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
      "maxItems": 1000,
      "title": "Sections",
      "type": "array"
    },
    "snapshot_id": {
      "title": "Snapshot Id",
      "type": "string"
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

## GetApplicationHealthRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetApplicationHealthRequest",
  "type": "object"
}
```

## GetApplicationHealthResponse

```json
{
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
    "instance_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Instance Id"
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
    "pid": {
      "exclusiveMinimum": 0,
      "title": "Pid",
      "type": "integer"
    },
    "ready": {
      "title": "Ready",
      "type": "boolean"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    },
    "version": {
      "title": "Version",
      "type": "string"
    }
  },
  "required": [
    "pid",
    "version",
    "ready",
    "lifecycle",
    "health",
    "checks",
    "checked_at"
  ],
  "title": "GetApplicationHealthResponse",
  "type": "object"
}
```

## GetApplicationMetricsRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetApplicationMetricsRequest",
  "type": "object"
}
```

## GetApplicationMetricsResponse

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

## GetBedrockProcessInfoRequest

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

## GetBedrockProcessInfoResponse

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

## GetDiagnosticHistoryRequest

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

## GetDiagnosticHistoryResponse

```json
{
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

## GetDiagnosticReportRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetDiagnosticReportRequest",
  "type": "object"
}
```

## GetDiagnosticReportResponse

```json
{
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

## GetDiagnosticRunsRequest

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

## GetDiagnosticRunsResponse

```json
{
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

## GetDiagnosticTraceRequest

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

## GetDiagnosticTraceResponse

```json
{
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
    "events_available": {
      "default": false,
      "title": "Events Available",
      "type": "boolean"
    },
    "history": {
      "$ref": "#/$defs/DiagnosticHistory"
    },
    "issues": {
      "items": {
        "$ref": "#/$defs/DiagnosticIssue"
      },
      "maxItems": 3,
      "title": "Issues",
      "type": "array"
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

## GetGlobalSettingRequest

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

## GetGlobalSettingResponse

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

## GetPermissionsRequest

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

## GetPermissionsResponse

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

## GetPluginSettingRequest

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

## GetPluginSettingResponse

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

## GetPluginStatusesRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetPluginStatusesRequest",
  "type": "object"
}
```

## GetPluginStatusesResponse

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

## GetPropertiesRequest

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

## GetPropertiesResponse

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

## GetRawPropertiesRequest

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

## GetRawPropertiesResponse

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

## GetServerBansRequest

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

## GetServerBansResponse

```json
{
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

## GetServerRunningStatusRequest

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

## GetServerRunningStatusResponse

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

## GetServerSettingRequest

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

## GetServerSettingResponse

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

## GetServerSummaryRequest

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

## GetServerSummaryResponse

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

## GetSystemAndAppInfoRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetSystemAndAppInfoRequest",
  "type": "object"
}
```

## GetSystemAndAppInfoResponse

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

## GetValidServerNamesRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "GetValidServerNamesRequest",
  "type": "object"
}
```

## GetValidServerNamesResponse

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

## GetWorldNameRequest

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

## GetWorldNameResponse

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

## HealthCheck

```json
{
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
}
```

## ImportAddonRequest

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

## ImportAddonResponse

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

## ImportWorldRequest

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

## ImportWorldResponse

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

## InspectSnapshotRequest

```json
{
  "additionalProperties": false,
  "properties": {
    "backup_id": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Backup Id",
      "type": "string"
    },
    "recovery_key": {
      "anyOf": [
        {
          "format": "password",
          "type": "string",
          "writeOnly": true
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Recovery Key"
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
    "backup_id"
  ],
  "title": "InspectSnapshotRequest",
  "type": "object"
}
```

## InspectSnapshotResponse

```json
{
  "additionalProperties": false,
  "properties": {
    "backup": {
      "$ref": "#/$defs/BackupSummary"
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
    "backup"
  ],
  "title": "InspectSnapshotResponse",
  "type": "object"
}
```

## InstallNewServerRequest

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

## InstallNewServerResponse

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

## InstalledAddon

```json
{
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
}
```

## InstalledAddons

```json
{
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
}
```

## JsonValue

```json
{}
```

## LifecyclePhase

```json
{
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
```

## ListAvailableAddonsRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ListAvailableAddonsRequest",
  "type": "object"
}
```

## ListAvailableAddonsResponse

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

## ListAvailableWorldsRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ListAvailableWorldsRequest",
  "type": "object"
}
```

## ListAvailableWorldsResponse

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

## ListBackupFilesRequest

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

## ListBackupFilesResponse

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

## ListInstalledAddonsRequest

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

## ListInstalledAddonsResponse

```json
{
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

## ListSnapshotsRequest

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
  "title": "ListSnapshotsRequest",
  "type": "object"
}
```

## ListSnapshotsResponse

```json
{
  "additionalProperties": false,
  "properties": {
    "backups": {
      "items": {
        "$ref": "#/$defs/BackupSummary"
      },
      "title": "Backups",
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
    "backups"
  ],
  "title": "ListSnapshotsResponse",
  "type": "object"
}
```

## ListenerFailure

```json
{
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
}
```

## ListenerRecord

```json
{
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
}
```

## MetricsDiagnostics

```json
{
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
}
```

## MetricsSample

```json
{
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
}
```

## PersistenceDiagnostics

```json
{
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
    "last_read_error_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Last Read Error Type"
    },
    "last_read_success_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Last Read Success At"
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
    "queue_limit": {
      "title": "Queue Limit",
      "type": "integer"
    },
    "queued": {
      "title": "Queued",
      "type": "integer"
    },
    "read_failures": {
      "default": 0,
      "title": "Read Failures",
      "type": "integer"
    },
    "retention_days": {
      "title": "Retention Days",
      "type": "integer"
    },
    "write_failures": {
      "title": "Write Failures",
      "type": "integer"
    },
    "writer_status": {
      "default": "not_started",
      "enum": [
        "not_started",
        "running",
        "failed",
        "closed"
      ],
      "title": "Writer Status",
      "type": "string"
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
}
```

## PlanSnapshotRestoreRequest

```json
{
  "additionalProperties": false,
  "properties": {
    "backup_id": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Backup Id",
      "type": "string"
    },
    "components": {
      "items": {
        "enum": [
          "world",
          "server.properties",
          "allowlist.json",
          "permissions.json",
          "script_config",
          "bsm_settings"
        ],
        "type": "string"
      },
      "minItems": 1,
      "title": "Components",
      "type": "array"
    },
    "recovery_key": {
      "anyOf": [
        {
          "format": "password",
          "type": "string",
          "writeOnly": true
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Recovery Key"
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
    "backup_id",
    "components"
  ],
  "title": "PlanSnapshotRestoreRequest",
  "type": "object"
}
```

## PlanSnapshotRestoreResponse

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
    "plan": {
      "$ref": "#/$defs/RestorePlan"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "plan"
  ],
  "title": "PlanSnapshotRestoreResponse",
  "type": "object"
}
```

## PlayerInfo

```json
{
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
```

## PlayerPermission

```json
{
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
```

## PlayerScanDetails

```json
{
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
}
```

## PlayerScanError

```json
{
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
```

## PluginDiagnostic

```json
{
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
}
```

## PluginInfo

```json
{
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
```

## PluginValues

```json
{
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
}
```

## PluginsDiagnostics

```json
{
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
}
```

## ProcessDiagnostic

```json
{
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
}
```

## ProcessInfo

```json
{
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
```

## ProcessesDiagnostics

```json
{
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
}
```

## PruneDownloadCacheRequest

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

## PruneDownloadCacheResponse

```json
{
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

## PruneOldBackupsRequest

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

## PruneOldBackupsResponse

```json
{
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

## PublishWsEventRequest

```json
{
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

## PublishWsEventResponse

```json
{
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

## RecentDiagnosticCounts

```json
{
  "additionalProperties": false,
  "properties": {
    "cancelled": {
      "default": 0,
      "title": "Cancelled",
      "type": "integer"
    },
    "failed": {
      "default": 0,
      "title": "Failed",
      "type": "integer"
    },
    "timeouts": {
      "default": 0,
      "title": "Timeouts",
      "type": "integer"
    }
  },
  "title": "RecentDiagnosticCounts",
  "type": "object"
}
```

## RecentDiagnosticWindow

```json
{
  "additionalProperties": false,
  "properties": {
    "bucket_seconds": {
      "const": 10,
      "default": 10,
      "title": "Bucket Seconds",
      "type": "integer"
    },
    "by_subsystem": {
      "additionalProperties": {
        "$ref": "#/$defs/RecentDiagnosticCounts"
      },
      "title": "By Subsystem",
      "type": "object"
    },
    "cancelled": {
      "default": 0,
      "title": "Cancelled",
      "type": "integer"
    },
    "failures": {
      "default": 0,
      "title": "Failures",
      "type": "integer"
    },
    "observed_since": {
      "title": "Observed Since",
      "type": "number"
    },
    "timeouts": {
      "default": 0,
      "title": "Timeouts",
      "type": "integer"
    },
    "window_seconds": {
      "const": 300,
      "default": 300,
      "title": "Window Seconds",
      "type": "integer"
    }
  },
  "required": [
    "observed_since"
  ],
  "title": "RecentDiagnosticWindow",
  "type": "object"
}
```

## RegistryDiagnostics

```json
{
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
}
```

## RemoveFromAllowlistRequest

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

## RemoveFromAllowlistResponse

```json
{
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

## ReorderAddonsRequest

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

## ReorderAddonsResponse

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

## ResourceFailure

```json
{
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
}
```

## RestartServerRequest

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

## RestartServerResponse

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

## RestoreAllRequest

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

## RestoreAllResponse

```json
{
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

## RestoreConfigFileRequest

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
    "component": {
      "anyOf": [
        {
          "enum": [
            "server.properties",
            "allowlist.json",
            "permissions.json"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Component"
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

## RestoreConfigFileResponse

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

## RestorePlan

```json
{
  "additionalProperties": false,
  "properties": {
    "backup_id": {
      "title": "Backup Id",
      "type": "string"
    },
    "components": {
      "items": {
        "enum": [
          "world",
          "server.properties",
          "allowlist.json",
          "permissions.json",
          "script_config",
          "bsm_settings"
        ],
        "type": "string"
      },
      "title": "Components",
      "type": "array"
    },
    "destinations": {
      "additionalProperties": {
        "type": "string"
      },
      "propertyNames": {
        "enum": [
          "world",
          "server.properties",
          "allowlist.json",
          "permissions.json",
          "script_config",
          "bsm_settings"
        ]
      },
      "title": "Destinations",
      "type": "object"
    },
    "required_bytes": {
      "title": "Required Bytes",
      "type": "integer"
    },
    "token": {
      "title": "Token",
      "type": "string"
    },
    "warnings": {
      "items": {
        "type": "string"
      },
      "title": "Warnings",
      "type": "array"
    }
  },
  "required": [
    "backup_id",
    "token",
    "components",
    "destinations",
    "warnings",
    "required_bytes"
  ],
  "title": "RestorePlan",
  "type": "object"
}
```

## RestoreRecoveryResponse

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
    "recovery": {
      "$ref": "#/$defs/RestoreRecoveryState"
    },
    "status": {
      "const": "success",
      "default": "success",
      "title": "Status",
      "type": "string"
    }
  },
  "required": [
    "recovery"
  ],
  "title": "RestoreRecoveryResponse",
  "type": "object"
}
```

## RestoreRecoveryState

```json
{
  "additionalProperties": false,
  "properties": {
    "active": {
      "title": "Active",
      "type": "boolean"
    },
    "committed": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Committed"
    },
    "error": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Error"
    }
  },
  "required": [
    "active"
  ],
  "title": "RestoreRecoveryState",
  "type": "object"
}
```

## RestoreResult

```json
{
  "additionalProperties": false,
  "properties": {
    "cleanup_warning": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Cleanup Warning"
    },
    "committed": {
      "default": true,
      "title": "Committed",
      "type": "boolean"
    },
    "restart_error": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Restart Error"
    },
    "restarted": {
      "default": false,
      "title": "Restarted",
      "type": "boolean"
    },
    "restored": {
      "items": {
        "enum": [
          "world",
          "server.properties",
          "allowlist.json",
          "permissions.json",
          "script_config",
          "bsm_settings"
        ],
        "type": "string"
      },
      "title": "Restored",
      "type": "array"
    }
  },
  "required": [
    "restored"
  ],
  "title": "RestoreResult",
  "type": "object"
}
```

## RestoreSnapshotRequest

```json
{
  "additionalProperties": false,
  "properties": {
    "backup_id": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Backup Id",
      "type": "string"
    },
    "components": {
      "items": {
        "enum": [
          "world",
          "server.properties",
          "allowlist.json",
          "permissions.json",
          "script_config",
          "bsm_settings"
        ],
        "type": "string"
      },
      "minItems": 1,
      "title": "Components",
      "type": "array"
    },
    "recovery_key": {
      "anyOf": [
        {
          "format": "password",
          "type": "string",
          "writeOnly": true
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Recovery Key"
    },
    "restart": {
      "default": true,
      "title": "Restart",
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
    "stop_running": {
      "default": true,
      "title": "Stop Running",
      "type": "boolean"
    },
    "token": {
      "minLength": 1,
      "pattern": ".*\\S.*",
      "title": "Token",
      "type": "string"
    }
  },
  "required": [
    "server_name",
    "backup_id",
    "components",
    "token"
  ],
  "title": "RestoreSnapshotRequest",
  "type": "object"
}
```

## RestoreSnapshotResponse

```json
{
  "additionalProperties": false,
  "properties": {
    "message": {
      "title": "Message",
      "type": "string"
    },
    "result": {
      "$ref": "#/$defs/RestoreResult"
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
    "server_name",
    "result"
  ],
  "title": "RestoreSnapshotResponse",
  "type": "object"
}
```

## RestoreWorldRequest

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

## RestoreWorldResponse

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

## RuntimeDiagnostics

```json
{
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
}
```

## ScanAndUpdatePlayerDbRequest

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "ScanAndUpdatePlayerDbRequest",
  "type": "object"
}
```

## ScanAndUpdatePlayerDbResponse

```json
{
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

## SendCommandRequest

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

## SendCommandResponse

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

## SendToClientRequest

```json
{
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

## SendToClientResponse

```json
{
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

## SendToUserRequest

```json
{
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

## SendToUserResponse

```json
{
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

## ServerMetrics

```json
{
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
```

## ServerSummary

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
```

## SetCustomGlobalSettingRequest

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

## SetCustomGlobalSettingResponse

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

## SetPermissionsRequest

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

## SetPermissionsResponse

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

## SetPluginSettingRequest

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

## SetPluginSettingResponse

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

## SetPropertiesRequest

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

## SetPropertiesResponse

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

## SetServerCustomValueRequest

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

## SetServerCustomValueResponse

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

## SkippedItem

```json
{
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
```

## StartServerRequest

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

## StartServerResponse

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

## StateDiagnostics

```json
{
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
}
```

## StopServerRequest

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

## StopServerResponse

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

## StorageDiagnostics

```json
{
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
}
```

## Subpack

```json
{
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
```

## TaskDiagnostic

```json
{
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
```

## TasksDiagnostics

```json
{
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
}
```

## TransportDiagnostics

```json
{
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
```

## UnregisterDataProviderRequest

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

## UnregisterDataProviderResponse

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

## UpdateServerRequest

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

## UpdateServerResponse

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

## ValidatePropertyValueRequest

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

## ValidatePropertyValueResponse

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
