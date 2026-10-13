# Troubleshooting

Identify whether the failure belongs to the manager, a Bedrock server, a plugin or a client before changing configuration. Record the failing action and its error; restart or upgrade only after preserving the information needed to diagnose it.

## Startup or connection fails

Check the command's output, the active Python environment, selected configuration directory and operating-system account. A service can use different paths or permissions from an interactive terminal. Confirm the configured web address and port, and check whether another process owns the port or the same BSM configuration.

For Minecraft connections, check the Bedrock process and its UDP game ports separately from BSM's HTTP port. Inspect server logs for startup failure before changing network settings.

## Logs and background tasks

Inspect the task result when an operation was accepted but failed later. Manager log files have per-run names; locate the configured log directory rather than assuming a fixed filename. Use the local command's logging options shown by `bedrock-server-manager --help` to reproduce with more detail.

An HTTP 503 during shutdown indicates the host is stopping. Shutdown acceptance does not mean cleanup has completed. See [runtime control](../extras/web_runtime.md) for deadlines and service restart behavior.

## Plugin problems

Record the plugin name, version and event or task that failed. Disable the suspected plugin to isolate the issue, then re-enable it after correction. A timed-out synchronous callback can remain running; reload may be blocked until the old generation drains. Repeated reload attempts do not stop Python worker threads.

## Problems after upgrading

Check the release notes and verify that the frontend, API client and external plugins support the backend contract. Recreate service definitions when the runtime guide calls for it. Back up storage before changing versions or running migrations; database upgrades are not necessarily reversible by reinstalling an older package.

## Report an issue

Search the [issue tracker](https://github.com/DMedina559/bedrock-server-manager/issues), then use the appropriate report template. Include BSM/Python/OS versions, installation method, the action that failed, reproduction steps and relevant error output. Remove passwords, tokens and private connection strings from logs before sharing them.
