# Web Usage

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Icon
:width: 200px
:align: center
```

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/docs/images/main_index.png
:alt: Web Interface
:width: 400px
:align: center
```

Bedrock Server Manager 3.1.0 includes a Web server you can run to easily manage your bedrock servers in your web browser, and is also mobile friendly!

With the web server you can:

- Install New Server
- Configure various server config files such as allowlist and permissions
- Start/Stop/Restart Bedrock server
- Update/Delete Bedrock server
- Monitor resource usage
- Install world/addons
- Backup and Restore all or individual files/worlds
- Manage Plugins

## Hosts:

```{note}
As of BSM 3.5.0, the web server will only accept one host at a time, if multiple hosts are specified, the first one will be used.
```

By Default Bedrock Server Manager will only listen to local host only interfaces `127.0.0.1`

To change which host to listen to start the web server with the specified host

Example: specify local host only ipv4:

```bash
bedrock-server-manager web start --host 127.0.0.1
```

Example: specify all ipv4:

```bash
bedrock-server-manager web start --host 0.0.0.0
```

You can also change the host by running the `setup` command, which will prompt you for the host to use.

```bash
bedrock-server-manager setup
```

### Port:

By default Bedrock Server Manager will use port `11325`. This can be change with the `setup` command.

### HTTP API:

```{note}
As of BSM 3.5.0, the HTTP API docs are now integrated in the web server using FastAPIs Swagger UI.
Visit: `http(s)://<bsm_host:port>/docs` after starting the web server.
```

An HTTP API is provided allowing tools like `curl` or `Invoke-RestMethod` to interact with server.

#### Obtaining a JWT token:

```{note}
The API relies on Bearer tokens for authentication using the `Authorization` header.
```

The API endpoints require authentication using a JSON Web Token (JWT).
How: Obtain a token by sending a POST request to the `/auth/token` endpoint.
Request Body: Include a JSON payload with username, password, and an optional `remember_me` key (default is `false`). Setting `remember_me` to `true` extends the token expiration.

```json
{
    "username": "username",
    "password": "password",
    "remember_me": true
}
```

Response: On success, the API returns a JSON object containing the access_token:
```
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "message": "Successfully authenticated."
}
```

Tokens expiration is configurable via web ui (default: 4 weeks).

##### `curl` Example (Bash):

Extract the token from the response. You can use tools like `jq` to parse the JSON output.

```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"username": "your_username", "password": "your_password", "remember_me": true}' \
     http://<your-manager-host>:<port>/auth/token
```

##### PowerShell Example:

Store the authentication token in a variable.

```powershell
$body = @{ username = 'your_username'; password = 'your_password'; remember_me = $true } | ConvertTo-Json
$response = Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/auth/token" -Body $body -ContentType 'application/json'
$token = $response.access_token
```

#### Using the API

Endpoints requiring authentication will need the obtained `access_token` included in the `Authorization` header as a Bearer token.

For requests sending data (like POST or PUT), set the Content-Type header to `application/json`.

#### Examples:

- Start/Stop server:

##### `curl` Example (Bash):

Using `-H "Authorization: Bearer <token>"` to pass the token.

```bash
curl -X POST -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
     http://<your-manager-host>:<port>/api/server/<server_name>/stop
```

##### PowerShell Example:

Using the previously saved authentication token in the Headers.

```powershell
$headers = @{ 'Authorization' = "Bearer $token" }
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/stop" -Headers $headers
```

- Send Command:

##### `curl` Example (Bash):
```bash
curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
     -d '{"command": "say Hello from API!"}' \
     http://<your-manager-host>:<port>/api/server/<server_name>/send_command
```

##### PowerShell Example:
```powershell
$headers = @{ 'Content-Type' = 'application/json'; 'Authorization' = "Bearer $token" }
$body = @{ command = 'say Hello from API!' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://<your-manager-host>:<port>/api/server/<server_name>/send_command" -Headers $headers -Body $body
```
