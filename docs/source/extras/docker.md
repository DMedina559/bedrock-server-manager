# Running with Docker

This project includes a `Dockerfile` that allows you to build and run the Bedrock Server Manager in a containerized environment. This allows for easy deployment and management of the application.

## Image Location

The official Docker image is hosted on both the GitHub Container Registry and Docker Hub. 

* **Docker Hub**: `dmedina559/bedrock-server-manager:latest`
* **GitHub Container Registry**: `ghcr.io/dmedina559/bedrock-server-manager:latest`

You can pull it using the following command:

```bash
docker pull dmedina559/bedrock-server-manager:latest
```

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
  --name bsm-container \
  -v bsm_config:/root/.config/bedrock-server-manager \
  -v bsm_data:/root/bedrock-server-manager \
  dmedina559/bedrock-server-manager:latest
```

This command creates two named volumes, `bsm_config` and `bsm_data`, and mounts them to the correct locations.

#### Using Bind Mounts

Alternatively, you can mount directories from your host machine.

```bash
docker run -d \
  -p 11325:11325 \
  -p 19132:19132/udp \
  --name bsm-container \
  -v /path/on/host/bsm_config:/root/.config/bedrock-server-manager \
  -v /path/on/host/bsm_data:/root/bedrock-server-manager \
  dmedina559/bedrock-server-manager:latest
```

### Overriding Environment Variables

You can override the default `HOST` and `PORT` for the web server by passing environment variables to the container. If these variables are not set, the application will use the default values (`HOST=0.0.0.0`, `PORT=11325`). For example, to change the web server port to `8080`:

```bash
docker run -d \
  -p 8080:8080 \
  -p 19132:19132/udp \
  --name bsm-container \
  -e PORT=8080 \
  -e HOST=0.0.0.0 \
  -v bsm_config:/root/.config/bedrock-server-manager \
  -v bsm_data:/root/bedrock-server-manager \
  dmedina559/bedrock-server-manager:latest
```

### Exposing Minecraft Server Ports

For players to be able to connect to your Minecraft servers, you must expose the corresponding UDP ports from the container. The default Minecraft Bedrock port is `19132/udp`.

If you run multiple servers, you will need to map a port for each one. See the example above for how to add more `-p` flags.

#### Alternative: Host Networking

A simpler, but less isolated, approach is to use host networking by adding `--network host` to your `docker run` command. Note that when using host networking, you do not need to map individual ports.

## Using Docker Compose

For an even easier setup, you can use Docker Compose. Create a `docker-compose.yml` file and add the following content:

```yaml
version: '3.8'
services:
  bedrock-server-manager:
    image: dmedina559/bedrock-server-manager:latest
    container_name: bsm-container
    restart: unless-stopped
    ports:
      - "11325:11325"
      - "19132:19132/udp" # Add more ports here for additional servers
    environment: # Optional
      - HOST=0.0.0.0
      - PORT=11325
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

The database URL is stored in the configuration file. If you are using the recommended volume setup, you can find the file in the `bsm_config` volume.

To change the database URL:
1.  Stop the container: `docker stop bsm-container`
2.  Locate and edit the `bedrock_server_manager.json` file inside the `bsm_config` volume. The exact location on your host will depend on your Docker setup. You can use `docker volume inspect bsm_config` to find the mountpoint.
3.  Change the `db_url` value in the JSON file.
4.  Start the container again: `docker start bsm-container`
