/* Sphinx enhancements styled with the BSM frontend's semantic tokens. */
"use strict";
document.addEventListener("DOMContentLoaded", () => {
  for (const block of document.querySelectorAll(
    "div.highlight, pre.literal-block",
  )) {
    const code = block.matches("pre") ? block : block.querySelector("pre");
    if (!code) continue;
    let container = block;
    if (block.matches("pre")) {
      container = document.createElement("div");
      container.className = "bsm-code-block";
      block.before(container);
      container.append(block);
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "bsm-copy-btn";
    button.textContent = "Copy";
    button.setAttribute("aria-label", "Copy code to clipboard");
    button.setAttribute("aria-live", "polite");
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(
          code.textContent.replace(/^\$\s+/gm, "").trimEnd(),
        );
        button.textContent = "Copied!";
        button.classList.add("copied");
      } catch {
        button.textContent = "Copy unavailable";
      }
      setTimeout(() => {
        button.textContent = "Copy";
        button.classList.remove("copied");
      }, 2000);
    });
    container.append(button);
  }

  document.addEventListener("keydown", (event) => {
    const active = document.activeElement;
    if (
      active?.isContentEditable ||
      ["INPUT", "TEXTAREA", "SELECT"].includes(active?.tagName)
    )
      return;
    if (
      event.key === "/" ||
      (event.key === "k" && (event.metaKey || event.ctrlKey))
    ) {
      const search = document.querySelector(
        "#rtd-search-form input[type='text']",
      );
      if (!search) return;
      event.preventDefault();
      search.focus();
      search.select();
    }
  });

  const images = [
    ...document.querySelectorAll(".rst-content img:not(.no-lightbox)"),
  ].filter((image) => {
    const link = image.closest("a");
    return !link || /\.(png|jpe?g|gif|webp|svg)(?:[?#]|$)/i.test(link.href);
  });
  if (!images.length) return;
  const dialog = document.createElement("dialog");
  dialog.id = "bsm-lightbox";
  dialog.setAttribute("aria-label", "Documentation image preview");
  const close = document.createElement("button");
  close.type = "button";
  close.className = "btn bsm-lightbox-close";
  close.textContent = "Close preview";
  close.addEventListener("click", () => dialog.close());
  const preview = document.createElement("img");
  dialog.append(close, preview);
  document.body.append(dialog);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  for (const image of images) {
    const link = image.closest("a");
    const trigger = link || document.createElement("button");
    if (!link) trigger.type = "button";
    trigger.classList.add("bsm-image-button");
    trigger.setAttribute(
      "aria-label",
      `Enlarge ${image.alt || "documentation image"}`,
    );
    trigger.setAttribute("aria-haspopup", "dialog");
    if (!link) {
      image.before(trigger);
      trigger.append(image);
    }
    trigger.addEventListener("click", (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)
        return;
      event.preventDefault();
      preview.src = image.src;
      preview.alt = image.alt;
      dialog.showModal();
    });
  }
});
