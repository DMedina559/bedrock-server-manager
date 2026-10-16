/* Apply the BSM frontend appearance contract before first paint. */
"use strict";
(() => {
  const root = document.documentElement;
  const system = window.matchMedia("(prefers-color-scheme: light)");
  const preferences = { mode: "system", density: "comfort" };
  root.dataset.theme = "default";
  try {
    const saved = JSON.parse(localStorage.getItem("bsm-docs-appearance"));
    if (["system", "dark", "light"].includes(saved?.mode))
      preferences.mode = saved.mode;
    if (["comfort", "compact"].includes(saved?.density))
      preferences.density = saved.density;
  } catch {
    /* Appearance persistence is optional. */
  }
  function apply() {
    root.dataset.mode =
      preferences.mode === "system"
        ? system.matches
          ? "light"
          : "dark"
        : preferences.mode;
    root.dataset.density = preferences.density;
  }
  apply();
  system.addEventListener("change", apply);
  document.addEventListener("DOMContentLoaded", () => {
    for (const name of ["mode", "density"]) {
      const control = document.getElementById(`bsm-docs-${name}`);
      if (!control) continue;
      control.value = preferences[name];
      control.addEventListener("change", () => {
        preferences[name] = control.value;
        apply();
        try {
          localStorage.setItem(
            "bsm-docs-appearance",
            JSON.stringify(preferences),
          );
        } catch {
          /* Storage may be denied. */
        }
      });
    }
  });
})();
