from bedrock_server_manager import PluginBase
from mcstatus import BedrockServer as mc


class UpdateVersionOnStartPlugin(PluginBase):
    version = "1.0.0"

    def on_load(self):
        self.logger.info("Plugin loaded. Will check server version on start.")

    def after_server_start(self, **kwargs):
        server_name = kwargs.get("server_name")
        app_context = kwargs.get("app_context")

        if not app_context:
            self.logger.warning(
                "app_context not available, cannot check server version."
            )
            return

        server = app_context.get_server(server_name)

        try:
            bedrock_server = mc.lookup(
                f"127.0.0.1:{server.get_server_property('server-port')}"
            )
            status = bedrock_server.status()
            live_version = status.version.name
            config_version = server.get_version()

            if live_version != config_version:
                self.logger.info(
                    f"Server '{server_name}' version mismatch. Live: {live_version}, Config: {config_version}. Updating config."
                )
                server.set_version(live_version)
            else:
                self.logger.debug(
                    f"Server '{server_name}' version is up to date. Live: {live_version}, Config: {config_version}."
                )

        except Exception as e:
            self.logger.error(f"Error checking version for server '{server_name}': {e}")
