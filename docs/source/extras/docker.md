# Docker Install

This project includes a `Dockerfile` that allows you to build and run the Bedrock Server Manager in a containerized environment. This allows for easy deployment and management of the application.

## Image Location

The official Docker image is hosted on both the GitHub Container Registry and Docker Hub.

* **Docker Hub**: `dmedina559/bedrock-server-manager:stable`
* **GitHub Container Registry**: `ghcr.io/dmedina559/bedrock-server-manager:stable`

You can pull it using the following command:

```bash
docker pull dmedina559/bedrock-server-manager:stable
```

## Image Tags and Versioning

The Docker images for Bedrock Server Manager are tagged to help you choose the right version for your needs. Understanding the tagging strategy will help you manage your deployments effectively.

### Available Tags

*   **`latest`**: This tag always points to the most recent release, including stable, beta, and release candidates. It is a convenient way to stay up-to-date with the latest features and fixes, but it may not always be the most stable. Use this tag if you want the newest version and are comfortable with potentially running pre-release software.

*   **`stable`**: This tag points to the most recent stable release. It does not include beta versions or release candidates. This is the recommended tag for most users, as it provides a balance of new features and stability. Use this tag for production environments or if you prefer to avoid pre-release versions.

*   **Version Tags (e.g., `3.7.0`, `3.7.0b5`)**: Every release, whether stable or pre-release, has its own version-specific tag. These tags are useful for pinning your deployment to a specific version of the application, which ensures that your environment is predictable and does not change unexpectedly. This is a common practice for production deployments where stability and control are critical.

### How to Use the Tags

To pull a specific tag, simply append it to the image name. For example:

*   To pull the latest stable version:
    ```bash
    docker pull dmedina559/bedrock-server-manager:stable
    ```

*   To pull a specific version:
    ```bash
    docker pull dmedina559/bedrock-server-manager:3.7.0
    ```

By choosing the right tag, you can control when and how you update your Bedrock Server Manager instance, ensuring a smooth and stable experience.

## Running the Container

The Docker image is configured to run the web server by default. To run the container, you need to map the port and, most importantly, provide volumes for persistent data storage.

### Data Persistence

The application uses two main directories to store its data. To prevent data loss when the container is removed, you **must** mount volumes for both of these locations.

1.  **Configuration Directory:** This directory stores the main `bedrock_server_manager.json` file, which contains the path to the data directory and the database URL.
    -   Container Path: `/root/.config/bedrock-server-manager`

2.  **Data Directory:** This directory stores everything else, including server files, plugins, backups, and the application's database.
    -   Default Container Path: `/root/bedrock-server-manager`

#### Using a Named Volume (Recommended)

This is the easiest and most recommended way to manage the data. Docker will manage the volumes for you.

```bash
docker run -d \
  -p 11325:11325 \
  -p 19132:19132/udp \
  -p 19133:19133/udp \
  --name bsm-container \
  -v bsm_config:/root/.config/bedrock-server-manager \
  -v bsm_data:/root/bedrock-server-manager \
  dmedina559/bedrock-server-manager:stable
```

This command creates two named volumes, `bsm_config` and `bsm_data`, and mounts them to the correct locations.

#### Using Bind Mounts

Alternatively, you can mount directories from your host machine.

```bash
docker run -d \
  -p 11325:11325 \
  -p 19132:19132/udp \
  -p 19133:19133/udp \
  --name bsm-container \
  -v /path/on/host/bsm_config:/root/.config/bedrock-server-manager \
  -v /path/on/host/bsm_data:/root/bedrock-server-manager \
  dmedina559/bedrock-server-manager:stable
```

### Overriding Environment Variables

You can configure the application by passing environment variables to the container.

*   `HOST`: The host for the web server (default: `0.0.0.0`).
*   `PORT`: The port for the web server (default: `11325`).
*   `BSM_DATA_DIR`: The path to the data directory within the container (default: `/root/bedrock-server-manager`). **Note**: If you change this, make sure to update your volume mounts accordingly.
*   `BSM_DB_URL`: The database connection URL. Setting this overrides the value in the configuration file.

For example, to change the web server port to `8080` and use a custom database:

```bash
docker run -d \
  -p 8080:8080 \
  -p 19132:19132/udp \
  -p 19133:19133/udp \
  --name bsm-container \
  -e PORT=8080 \
  -e HOST=0.0.0.0 \
  -e BSM_DB_URL="mysql://user:pass@host/db" \
  -v bsm_config:/root/.config/bedrock-server-manager \
  -v bsm_data:/root/bedrock-server-manager \
  dmedina559/bedrock-server-manager:stable
```

### Exposing Minecraft Server Ports

For players to be able to connect to your Minecraft servers, you must expose the corresponding UDP ports from the container. The default Minecraft Bedrock ports are `19132/udp` (IPv4) and `19133/udp` (IPv6).

If you run multiple servers, you will need to map a port for each one. See the example above for how to add more `-p` flags.

**Note on LAN Discovery (Broadcast):**
By default, Docker containers run in a bridge network which isolates broadcast traffic. This means servers running in Docker **will not appear in the "Worlds" tab** (LAN games) of Minecraft clients on the same network, even if the ports are mapped correctly. Players will need to add the server manually using the "Servers" tab -> "Add Server" button and entering the host's IP address and port.

#### Alternative: Host Networking (Required for LAN Discovery)

To enable automatic LAN discovery (so the server appears in the Worlds list), you must use **Host Networking**. This bypasses Docker's network isolation and allows broadcast packets to reach the LAN.

A simpler, but less isolated, approach is to use host networking by adding `--network host` to your `docker run` command. Note that when using host networking, you do not need to map individual ports.

## Using Docker Compose

For an even easier setup, you can use Docker Compose. Create a `docker-compose.yml` file and add the following content:

```yaml
version: '3.8'
services:
  bedrock-server-manager:
    image: dmedina559/bedrock-server-manager:stable     # Use desired tag here (e.g., stable, latest, 3.7.0)
    container_name: bsm-container                       # Name of the container
    restart: unless-stopped                             # Restart policy
    ports:
      - "11325:11325"                                   # Web server port
      - "19132:19132/udp"                               # Default Minecraft Bedrock server port (IPv4)
      - "19133:19133/udp"                               # Default Minecraft Bedrock server port (IPv6)
      # - "19132:19132/udp"                             # Add more ports as needed for additional servers
    environment: # Optional
      - HOST=0.0.0.0                                    # Which host to bind the web server to
      - PORT=11325                                      # Port for the web server
      # - BSM_DB_URL=mysql://user:pass@host/db          # Custom database URL
    volumes:
      - bsm_config:/root/.config/bedrock-server-manager
      - bsm_data:/root/bedrock-server-manager

volumes:
  bsm_config:
  bsm_data:
```

You can then start the application with a single command: `docker-compose up -d`.

## Advanced Usage

### Accessing the CLI

You can access the `bedrock-server-manager` CLI using `docker exec`.

To run a single command:
```bash
docker exec bsm-container bedrock-server-manager <command>
```

To get an interactive shell:
```bash
docker exec -it bsm-container /bin/bash
```

### Changing the Database URL

The easiest way to change the database URL is to set the `BSM_DB_URL` environment variable as described in the **Overriding Environment Variables** section.

Alternatively, you can edit the configuration file stored in the `bsm_config` volume:
1.  Stop the container: `docker stop bsm-container`
2.  Locate and edit the `bedrock_server_manager.json` file inside the `bsm_config` volume. The exact location on your host will depend on your Docker setup. You can use `docker volume inspect bsm_config` to find the mountpoint.
3.  Change the `db_url` value in the JSON file.
4.  Start the container again: `docker start bsm-container`
