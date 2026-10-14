# Theming

Bedrock Server Manager lets you customize the web UI through **Appearance**. Choose a built-in theme, create a personal color palette, or install a shared CSS theme on the server.

The theme engine uses semantic CSS variables for backgrounds, text, controls, borders, status colors, and other shared styles. Plugins can use the same variables to follow the selected theme.

## Appearance settings

Open **Appearance** from the navigation menu to adjust the following settings:

| Setting | What it changes | Default |
| --- | --- | --- |
| Account theme | The built-in or server-installed CSS theme associated with your account. | Bedrock Emerald, described as **BSM Default** |
| Display mode | Use the theme default, force Light or Dark, or follow your system preference. | Use theme default |
| Density | Comfortable or Compact sizing for text, cards, spacing, and controls. Mobile controls retain accessible touch targets. | Comfortable |
| Panorama | Show the server-provided panorama behind the interface. | Off |
| Panorama visibility | Adjust how prominent the panorama appears when enabled. | 18% |
| Sidebar transparency | Adjust the sidebar background while keeping its text and controls opaque. | 0% |

The account theme is saved through the backend. Display preferences and personal palettes are stored in the current browser; they do not automatically follow your account to another device.

**Reset appearance** restores the default account theme, removes the active palette override, and restores the defaults above. Your saved personal palettes remain available. If the account theme cannot be saved, the reset reports an error and leaves your display preferences in place.

## Built-in themes

Each built-in theme has its own colors for page backgrounds, panels, and accents, with support for light and dark modes.

| Theme | CSS identifier |
| --- | --- |
| Bedrock Emerald — BSM Default | `default` |
| Daylight | `light` |
| Midnight | `black` |
| Aurora | `gradient` |
| Forest | `green` |
| Ocean | `blue` |
| Ember | `red` |
| Orchid | `pink` |
| Gold | `yellow` |

With **Use theme default**, Daylight uses light mode and the other built-in themes use dark mode. **System** follows your operating system's light or dark preference.

## Creating a personal palette

You can create a palette without writing CSS:

1. Open **Appearance** and choose **Create palette**.
2. Enter a name and an optional description.
3. Choose the accent, page background, panel background, text, and secondary text colors.
4. Review the contrast feedback and choose **Save and apply palette**.

Names can contain up to 60 characters and descriptions up to 160 characters. Colors use six-digit hex values such as `#00ed95`. Up to 30 palettes can be stored in the browser. Saving with an existing name updates that palette.

Use a saved palette's card to apply it, **Edit** to change it, or **Remove** to delete it. **Use account theme** turns off the palette override. Selecting a built-in or installed CSS theme also turns off the active palette.

An active personal palette takes priority over the account theme's colors in every display mode. Switching to Light or Dark does not generate a different version of that palette.

### Importing and exporting

- **Export palette** downloads JSON for sharing or backup. Use **Import palette** to load it in another browser, then review and save it. Imported JSON files must be smaller than 20 KB.
- **Export CSS theme** downloads a CSS file that an administrator can install as a shared server theme.

Palette JSON contains the following fields:

```json
{
  "name": "My Emerald",
  "description": "Deep teal surfaces with a bright emerald accent.",
  "accent": "#00ed95",
  "page": "#030b0d",
  "surface": "#082223",
  "text": "#edfff8",
  "muted": "#a8c3bc"
}
```

Personal palette names and descriptions belong to the browser's saved palette. Exported CSS contains the color rules; it does not register that palette description with the server.

## Installing a shared CSS theme

Place a CSS file in the backend's `themes` directory in your application data directory. The exact application data path depends on your installation.

For example, `my-theme.css` uses the theme identifier `my-theme`. Prefer a simple filename and avoid the built-in identifiers listed above, because the frontend loads those identifiers from its bundled stylesheets.

The backend must list the identifier through `GET /api/info/themes` and serve the stylesheet at `/themes/my-theme.css`. Reload Appearance after installing the file, then select the theme from **Built-in and installed CSS themes**.

Selecting the theme saves its identifier through `POST /api/account/theme`. Appearance does not upload CSS files to the server; installation is an administrator task.

## Writing a CSS theme

Use the `--bsm-*` semantic variables for new themes. You only need to override the values you want to change; unspecified variables retain the application's defaults.

The root element exposes the selected theme, resolved display mode, and density:

```html
<html data-theme="my-theme" data-mode="dark" data-density="comfortable">
```

Use these attributes in your selectors so your rules take priority over the application's mode defaults. The theme identifier in the selector must match the CSS filename without `.css`.

The following example defines a shared accent and separate light and dark surfaces:

```css
/* Save as themes/my-theme.css. */
:root[data-theme="my-theme"][data-mode][data-density] {
  --bsm-accent: #00ed95;
  --bsm-accent-strong: #087b57;
  --bsm-accent-hover: #066447;
  --bsm-on-accent: #ffffff;
  --bsm-focus: var(--bsm-accent-strong);
  --sidebar-bg-custom: var(--bsm-surface);
}

:root[data-theme="my-theme"][data-mode="dark"][data-density] {
  --bsm-page: #030b0d;
  --bsm-surface: #082223;
  --bsm-surface-raised: #0c2e2b;
  --bsm-input: #101f22;
  --bsm-text: #edfff8;
  --bsm-muted: #a8c3bc;
  --bsm-border: #215548;
}

:root[data-theme="my-theme"][data-mode="light"][data-density] {
  --bsm-page: #f3f6f4;
  --bsm-surface: #ffffff;
  --bsm-surface-raised: #e9f0ec;
  --bsm-input: #f8faf9;
  --bsm-text: #16291e;
  --bsm-muted: #50685b;
  --bsm-border: #bdcec3;
}
```

For a theme that deliberately uses the same colors in every mode, place its color values in the first selector instead. CSS exported from the palette editor follows that approach and includes compatibility aliases.

## Theme variables

The frontend's `src/styles/tokens.css` defines the shared token contract. The following variables are useful for custom themes and plugin pages.

### Colors and surfaces

| Variable | Purpose |
| --- | --- |
| `--bsm-accent` | Accent for links, icons, and highlights. |
| `--bsm-accent-strong` | Filled primary control background. |
| `--bsm-accent-hover` | Primary control hover and active background. |
| `--bsm-on-accent` | Text on filled primary controls. |
| `--bsm-accent-soft` | Subtle accent surface, derived from the accent and panel colors by default. |
| `--bsm-page` | Page background. |
| `--bsm-surface` | Cards and panels. |
| `--bsm-surface-raised` | Elevated surfaces and secondary controls. |
| `--bsm-input` | Input background. |
| `--bsm-text` | Main text. |
| `--bsm-muted` | Secondary text. |
| `--bsm-border` | Shared borders. |
| `--bsm-focus` | Keyboard focus color. |
| `--sidebar-bg-custom` | Sidebar background before the user's transparency setting is applied. |
| `--bsm-overlay` | Dialog and overlay shading. |
| `--bsm-shadow` | Shared box shadow. |
| `--bsm-console` | Monitor output background. |
| `--bsm-console-text` | Monitor output text. |

### Status and chart colors

| Variable | Purpose |
| --- | --- |
| `--bsm-success` | Success indicators and text. |
| `--bsm-danger` | Error indicators and text. |
| `--bsm-danger-solid` | Filled destructive control background. |
| `--bsm-warning` | Warning indicators and the default splash text color. |
| `--bsm-info` | Informational indicators. |
| `--bsm-chart-1`, `--bsm-chart-2`, `--bsm-chart-3` | Chart series colors. |

### Typography and shape

| Variable | Purpose |
| --- | --- |
| `--bsm-font` | Main font stack. |
| `--bsm-mono` | Monospace font stack. |
| `--bsm-radius-sm`, `--bsm-radius-md`, `--bsm-radius-lg`, `--bsm-radius-xl` | Shared corner radii. |
| `--bsm-space-1` through `--bsm-space-6` | Shared spacing scale. |

Density also controls layout and typography tokens in `src/styles/density.css`. Prefer those shared rules over hardcoded sizes when extending the interface, and check both Comfortable and Compact layouts on desktop and mobile.

## Migrating older themes

Legacy variables remain available for existing styles and plugin pages, but changing one legacy variable may only affect the components that still use it. New shared components use semantic tokens directly. Migrate the underlying colors to `--bsm-*` variables for a consistent result across the interface.

| Older variable | Recommended variable |
| --- | --- |
| `--bg-color` | `--bsm-page` |
| `--text-color`, `--header-text-color` | `--bsm-text` |
| `--text-color-secondary` | `--bsm-muted` |
| `--container-background-color`, `--server-card-background-color` | `--bsm-surface` |
| `--border-color` | `--bsm-border` |
| `--button-background-color` | `--bsm-surface-raised` |
| `--primary-button-background-color` | `--bsm-accent-strong` |
| `--primary-button-text-color` | `--bsm-on-accent` |
| `--form-input-background-color` | `--bsm-input` |
| `--monitor-output-background-color` | `--bsm-console` |
| `--monitor-output-text-color` | `--bsm-console-text` |
| `--sidebar-background-color` | `--sidebar-bg-custom` |

For example, replace a text-only legacy override:

```css
:root {
  --text-color: red;
}
```

with a semantic override scoped to your theme:

```css
:root[data-theme="my-theme"][data-mode][data-density] {
  --bsm-text: #ffb4b4;
}
```

Use Appearance's panorama settings for background imagery and visibility. Older background-image variables are not the primary control for the new panorama feature.

## Plugin theming

Plugin pages should use the shared variables so they follow account themes, personal palettes, and display modes:

```css
.my-plugin-panel {
  background: var(--bsm-surface);
  color: var(--bsm-text);
  border: 1px solid var(--bsm-border);
  border-radius: var(--bsm-radius-md);
  padding: var(--bsm-panel-padding);
}

.my-plugin-help {
  color: var(--bsm-muted);
}

.my-plugin-action {
  background: var(--bsm-accent-strong);
  color: var(--bsm-on-accent);
}

.my-plugin-action:focus-visible {
  outline: 2px solid var(--bsm-focus);
  outline-offset: 2px;
}
```

Check text contrast, focus visibility, error states, light and dark modes, both density settings, and mobile layouts when creating a theme or plugin page. Avoid reducing opacity on entire containers: it also fades their text and controls.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| A custom theme does not appear. | Confirm the backend lists its filename without `.css` in `/api/info/themes`, then reload Appearance. |
| A selected stylesheet fails to load. | Check that `/themes/NAME.css` returns CSS and that its name matches the listed identifier. |
| Colors stay unchanged. | Turn off the personal palette override and check that your CSS selectors match the selected theme. |
| Light mode overrides custom colors. | Define mode-specific selectors as shown above, or explicitly define fixed colors for every mode. |
| A palette is missing on another device. | Personal palettes are browser-local. Export and import the JSON, or install exported CSS as a server theme. |
| A theme reverts after reload. | Check the account theme save and refreshed account response. The backend must keep its in-memory account state synchronized with the committed database theme. |
