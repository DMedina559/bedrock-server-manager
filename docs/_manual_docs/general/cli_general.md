# CLI Usage

<div style="text-align: left;">
    <img src="https://raw.githubusercontent.com/DMedina559/bedrock-server-manager/main/docs/images/cli_menu.png" alt="CLI Menu" width="300" height="200">
</div>

For a complete list of commands, see [CLI Commands](../../cli.rst).

>Note: If you are using a version of the app prior to 3.3.0, you must run `bedrock-server-manager --help` to see the list of commands for your version.

## Examples:

### Open Main Menu:

```bash
bedrock-server-manager
```

### Send Command:
```bash
bedrock-server-manager server send-command --server server_name "tell @a hello"
```

### Export World:

```bash
bedrock-server-manager world export --server server_name
```
