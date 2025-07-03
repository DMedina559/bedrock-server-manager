# Extras

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Icon
:width: 200px
:align: center
```

## Installation: Stable, Beta, and Development

There are three ways to install Bedrock Server Manager, depending on your needs. For most users, the stable version is recommended.

---

### 1. Stable Version (Recommended)

This is the latest official, stable release. It has been tested and is suitable for most use cases.

```bash
pip install bedrock-server-manager
```

To upgrade to the latest stable version:

```bash
pip install --upgrade bedrock-server-manager
```

**Installing a Specific Version**

If you need to install a specific version, you can do so by specifying the version with `==`.

```bash
# Example: Install exactly version 3.2.5
pip install bedrock-server-manager==3.2.5
```

You can find a list of all available versions in the [**Release History on PyPI**](https://pypi.org/project/bedrock-server-manager/#history).

---

### 2. Beta / Pre-Release Versions (For Testers)

Occasionally, pre-release versions will be published to PyPI for testing. These versions contain new features and are generally stable but may contain minor bugs.

To install the latest pre-release version, use the `--pre` flag with pip:

```bash
pip install --pre bedrock-server-manager
```

If you wish to return to the stable version later, you can run:
`pip install --force-reinstall bedrock-server-manager`

**Previewing the Next Release**

The `dev` branch is where all beta developments are merged before being bundled into a new stable release. To see the latest changes that are being prepared, you can browse the code and documentation on the [**`dev` branch**](https://github.com/DMedina559/bedrock-server-manager/tree/dev).

---

### 3. Development Versions (For Advanced Users & Contributors)

These versions are at the cutting edge and reflect the latest code, but they are not guaranteed to be stable. Use them if you want to test a specific new feature that isn't in a beta yet, or if you are contributing to the project.

There are two ways to get a development version:

**Option A: Install Directly from a GitHub Branch**

This is the easiest way to test the code from a specific branch.

```bash
# Install the latest code from the 'main' branch
pip install git+https://github.com/DMedina559/bedrock-server-manager.git@main

# Or install from a specific feature branch
pip install git+https://github.com/DMedina559/bedrock-server-manager.git@name-of-the-branch
```

**Option B: Download from CI Artifacts**

Every time code is pushed to a branch, our Continuous Integration (CI) server builds a development package. These are useful for testing the result of a specific pull request or commit.

1.  Go to the [**Actions tab**](https://github.com/DMedina559/bedrock-server-manager/actions) in the GitHub repository.
2.  Find the workflow run for the branch or commit you want to test. Click on it to go to its summary page.
3.  Scroll down to the **Artifacts** section. You will see a file named something like `bedrock-server-manager-3.3.0.a1b2c3d`.
4.  Download and unzip the artifact. Inside, you will find a `.whl` (wheel) file.
5.  Install the package directly from the downloaded wheel file:
    ```bash
    # Navigate your terminal to the directory where you unzipped the files
    pip install bedrock_server_manager-3.3.0+a1b2c3d-py3-none-any.whl
    ```
    *(Note: The exact filename will be different. Just use the `.whl` file you downloaded.)*

## Web Server Extras

### Custom Web Server Panorama

You can personalize the background panorama displayed on the main web server page.

**Steps:**

1.  Choose your desired background image. It **must** be a JPEG file (with a `.jpeg` extension).
2.  Navigate to the Bedrock Server Manager's configuration directory, typically located at `./.config/` relative to the manager's installation path.
3.  Place your chosen image file into this `./.config/` directory.
4.  Rename the image file to `panorama.jpeg`.
5.  Refresh the web server page in your browser. The new panorama should now be displayed.

**Default Behavior:**

If the file `./.config/panorama.jpeg` is not found or is not a valid JPEG image, the default Bedrock Server Manager icon will be used as the background panorama.

---

### World Icons

The "Servers List" within the web interface can display unique icons for each of your Minecraft worlds, making them easier to identify at a glance.

**How it Works:**

The server manager looks for a file named `world_icon.jpeg` inside each world's specific folder.

**Adding Icons:**

*   **Imported Worlds / Client-Created Worlds:** Worlds that were imported or originally created using the Minecraft client (Bedrock Edition) often already include a `world_icon.jpeg` file within their folder structure. No extra steps may be needed.
*   **Dedicated Server-Created Worlds:** Worlds generated directly by the Bedrock Dedicated Server software usually *do not* have this icon file by default. You can add one manually:
    1.  Obtain or create an image you want to use as the icon (JPEG format, `.jpeg`). A square aspect ratio often looks best.
    2.  Locate the specific world folder for the server you want to customize. This is typically found within the server's directory structure (e.g., `./servers/your_server_name/worlds/your_world_name/`).
    3.  Copy your chosen image file into this specific world folder.
    4.  Rename the image file exactly to `world_icon.jpeg`.
    5.  The icon should appear the next time the server list is loaded or refreshed in the web interface.

**Default Behavior:**

If a `world_icon.jpeg` file is not found within a specific world's directory, the default Bedrock Server Manager icon will be displayed for that world in the server list.

## Home Assistant Integration

If you use Home Assistant, check out the [**Bedrock Server Manager integration**](https://github.com/DMedina559/bsm-home-assistant-integration).