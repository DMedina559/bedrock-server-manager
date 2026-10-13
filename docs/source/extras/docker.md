# Run BSM in Docker

Official images are available as `dmedina559/bedrock-server-manager` and `ghcr.io/dmedina559/bedrock-server-manager`. Choose `stable` for a stable release or pin a published version tag for repeatable upgrades. Check the image's release notes before replacing a running installation.

## Persist configuration and data

Set explicit paths and mount both directories. This avoids depending on the image account's platform defaults:

```yaml
services:
  bsm:
    image: dmedina559/bedrock-server-manager:stable
    ports:
      - "11325:11325"
      - "19132:19132/udp"
      - "19133:19133/udp"
    environment:
      BSM_CONFIG_DIR: /config
      BSM_DATA_DIR: /data
      HOST: 0.0.0.0
      PORT: "11325"
    volumes:
      - bsm_config:/config
      - bsm_data:/data
    stop_grace_period: 180s
    restart: on-failure
volumes:
  bsm_config:
  bsm_data:
```

Start with `docker compose up -d` and inspect `docker compose logs bsm`. Open the host's port 11325 to reach BSM. The HTTP port is separate from Minecraft's UDP game ports; publish the configured game ports for each server. Review firewall exposure before using this example on a public host.

The image starts the web host using `HOST` and `PORT`. Its backend installation includes external-database extras; `BSM_DB_URL` selects another database. Database storage outside these volumes needs its own backup policy.

## Stop and upgrade

Use `docker compose stop` to stop the container deliberately. BSM handles graceful process shutdown, but Docker's deadline must allow cleanup to complete. HTTP shutdown can be restarted by external policies such as `always` or `unless-stopped`; BSM does not rewrite those policies.

Back up volumes and any external database before upgrading. Pull the chosen image and recreate the container while retaining its mounts. Deleting a container differs from deleting its volumes; avoid volume removal unless you intend to discard persisted data.

See [runtime supervision](web_runtime.md), [backups](../features/backups.md) and [troubleshooting](../general/troubleshooting.md).
