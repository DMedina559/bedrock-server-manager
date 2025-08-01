| Endpoint | Type | Admin | Moderator | User |
|---|---|---|---|---|
| `GET /` | HTML | Full Access | Full Access | Full Access |
| `GET /server/{server_name}/monitor` | HTML | Full Access | Full Access | Full Access |
| `GET /auth/login` | HTML | Public | Public | Public |
| `POST /auth/token` | API | Public | Public | Public |
| `GET /auth/logout` | API | Full Access | Full Access | Full Access |
| `POST /register/generate-token` | API | Full Access | No Access | No Access |
| `GET /register/{token}` | HTML | Public | Public | Public |
| `POST /register/{token}` | API | Public | Public | Public |
| `GET /account` | HTML | Full Access | Full Access | Full Access |
| `GET /api/account` | API | Full Access | Full Access | Full Access |
| `POST /api/account/theme` | API | Full Access | Full Access | Full Access |
| `GET /settings` | HTML | Full Access | No Access | No Access |
| `GET /api/settings` | API | Full Access | No Access | No Access |
| `POST /api/settings` | API | Full Access | No Access | No Access |
| `GET /api/themes` | API | Full Access | Full Access | Full Access |
| `POST /api/settings/reload` | API | Full Access | No Access | No Access |
| `GET /users` | HTML | Full Access | Read-only | No Access |
| `POST /users/create` | API | Full Access | No Access | No Access |
| `POST /users/{user_id}/delete` | API | Full Access | No Access | No Access |
| `POST /api/server/{server_name}/start` | API | Full Access | Full Access | No Access |
| `POST /api/server/{server_name}/stop` | API | Full Access | Full Access | No Access |
| `POST /api/server/{server_name}/restart` | API | Full Access | Full Access | No Access |
| `POST /api/server/{server_name}/send_command` | API | Full Access | Full Access | No Access |
| `POST /api/server/{server_name}/update` | API | Full Access | No Access | No Access |
| `DELETE /api/server/{server_name}/delete` | API | Full Access | No Access | No Access |
| `GET /api/server/{server_name}/status` | API | Full Access | Full Access | Full Access |
| `GET /api/server/{server_name}/config_status` | API | Full Access | Full Access | Full Access |
| `GET /api/server/{server_name}/version` | API | Full Access | Full Access | Full Access |
| `GET /api/server/{server_name}/validate` | API | Full Access | Full Access | Full Access |
| `GET /api/server/{server_name}/process_info` | API | Full Access | Full Access | Full Access |
| `POST /api/players/scan` | API | Full Access | Full Access | No Access |
| `GET /api/players/get` | API | Full Access | Full Access | No Access |
| `POST /api/downloads/prune` | API | Full Access | No Access | No Access |
| `GET /api/servers` | API | Full Access | Full Access | Full Access |
| `GET /api/info` | API | Public | Public | Public |
| `POST /api/players/add` | API | Full Access | Full Access | No Access |
| `GET /server/{server_name}/backup` | HTML | Full Access | Full Access | No Access |
| `GET /server/{server_name}/backup/select` | HTML | Full Access | Full Access | No Access |
| `GET /server/{server_name}/restore` | HTML | Full Access | Full Access | No Access |
| `GET /server/{server_name}/restore/{restore_type}/select_file` | HTML | Full Access | Full Access | No Access |
| `POST /api/server/{server_name}/restore/select_backup_type` | API | Full Access | Full Access | No Access |
| `POST /api/server/{server_name}/backups/prune` | API | Full Access | Full Access | No Access |
| `GET /api/server/{server_name}/backup/list/{backup_type}` | API | Full Access | Full Access | No Access |
| `POST /api/server/{server_name}/backup/action` | API | Full Access | Full Access | No Access |
| `POST /api/server/{server_name}/restore/action` | API | Full Access | Full Access | No Access |
| `GET /server/{server_name}/install_world` | HTML | Full Access | No Access | No Access |
| `GET /server/{server_name}/install_addon` | HTML | Full Access | No Access | No Access |
| `GET /api/content/worlds` | API | Full Access | Full Access | No Access |
| `GET /api/content/addons` | API | Full Access | Full Access | No Access |
| `POST /api/server/{server_name}/world/install` | API | Full Access | No Access | No Access |
| `POST /api/server/{server_name}/world/export` | API | Full Access | No Access | No Access |
| `DELETE /api/server/{server_name}/world/reset` | API | Full Access | No Access | No Access |
| `POST /api/server/{server_name}/addon/install` | API | Full Access | No Access | No Access |
| `GET /plugins` | HTML | Full Access | No Access | No Access |
| `GET /api/plugins` | API | Full Access | No Access | No Access |
| `POST /api/plugins/trigger_event` | API | Full Access | No Access | No Access |
| `POST /api/plugins/{plugin_name}` | API | Full Access | No Access | No Access |
| `PUT /api/plugins/reload` | API | Full Access | No Access | No Access |
| `GET /api/downloads/list` | API | Full Access | Full Access | No Access |
| `GET /install` | HTML | Full Access | No Access | No Access |
| `POST /api/server/install` | API | Full Access | No Access | No Access |
| `GET /server/{server_name}/configure_properties` | HTML | Full Access | Full Access | No Access |
| `GET /server/{server_name}/configure_allowlist` | HTML | Full Access | Full Access | No Access |
| `GET /server/{server_name}/configure_permissions` | HTML | Full Access | Full Access | No Access |
| `GET /server/{server_name}/configure_service` | HTML | Full Access | No Access | No Access |
| `POST /api/server/{server_name}/properties/set` | API | Full Access | Full Access | No Access |
| `GET /api/server/{server_name}/properties/get` | API | Full Access | Full Access | No Access |
| `POST /api/server/{server_name}/allowlist/add` | API | Full Access | Full Access | No Access |
| `GET /api/server/{server_name}/allowlist/get` | API | Full Access | Full Access | No Access |
| `DELETE /api/server/{server_name}/allowlist/remove` | API | Full Access | Full Access | No Access |
| `PUT /api/server/{server_name}/permissions/set` | API | Full Access | Full Access | No Access |
| `GET /api/server/{server_name}/permissions/get` | API | Full Access | Full Access | No Access |
| `POST /api/server/{server_name}/service/update` | API | Full Access | No Access | No Access |
| `GET /setup` | HTML | Public | Public | Public |
| `POST /setup` | API | Public | Public | Public |
| `GET /api/tasks/status/{task_id}` | API | Full Access | Full Access | Full Access |
| `GET /api/panorama` | API | Public | Public | Public |
| `GET /api/server/{server_name}/world/icon` | API | Full Access | Full Access | Full Access |
| `GET /favicon.ico` | API | Public | Public | Public |
| `GET /{full_path:path}` | HTML | Full Access | Full Access | Full Access |
