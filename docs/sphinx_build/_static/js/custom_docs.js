/**
 * Bedrock Server Manager - Modern Documentation Enhancements
 * Interactive JS features for Sphinx / ReadTheDocs
 */

document.addEventListener("DOMContentLoaded", function () {
  // --- 1. Modern Copy Buttons for Code Blocks ---
  const codeBlocks = document.querySelectorAll("div.highlight, pre");

  codeBlocks.forEach(function (block) {
    // Avoid duplicate buttons or nested pre wrappers
    if (block.querySelector(".bsm-copy-btn") || block.tagName === "PRE" && block.parentElement.classList.contains("highlight")) {
      return;
    }

    const container = block.tagName === "PRE" ? block.parentElement : block;
    container.style.position = "relative";

    const copyBtn = document.createElement("button");
    copyBtn.className = "bsm-copy-btn";
    copyBtn.setAttribute("type", "button");
    copyBtn.setAttribute("aria-label", "Copy code to clipboard");
    copyBtn.innerHTML = `
      <svg class="copy-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
      <span>Copy</span>
    `;

    copyBtn.addEventListener("click", function (e) {
      e.preventDefault();
      const codeElement = block.querySelector("code") || block.querySelector("pre") || block;
      const textToCopy = codeElement.innerText.replace(/^\$\s+/gm, "").trim();

      navigator.clipboard.writeText(textToCopy).then(
        function () {
          copyBtn.classList.add("copied");
          copyBtn.innerHTML = `
            <svg class="check-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--bsm-accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            <span style="color: var(--bsm-accent);">Copied!</span>
          `;
          setTimeout(function () {
            copyBtn.classList.remove("copied");
            copyBtn.innerHTML = `
              <svg class="copy-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              <span>Copy</span>
            `;
          }, 2000);
        },
        function (err) {
          console.error("Could not copy text: ", err);
        }
      );
    });

    container.appendChild(copyBtn);
  });

  // --- 2. Search Shortcut (Ctrl/Cmd + K or /) ---
  document.addEventListener("keydown", function (e) {
    if (
      (e.key === "/" || (e.key === "k" && (e.metaKey || e.ctrlKey))) &&
      !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)
    ) {
      const searchInput = document.querySelector("#rtd-search-form input[type='text']");
      if (searchInput) {
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
      }
    }
  });

  // --- 3. Click-to-Zoom Image Modal for Screenshots ---
  const docImages = document.querySelectorAll(".rst-content img:not(.no-lightbox)");

  if (docImages.length > 0) {
    const lightbox = document.createElement("div");
    lightbox.id = "bsm-lightbox";
    lightbox.style.cssText = `
      display: none;
      position: fixed;
      z-index: 9999;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(3, 11, 13, 0.94);
      backdrop-filter: blur(12px);
      align-items: center;
      justify-content: center;
      cursor: zoom-out;
      opacity: 0;
      transition: opacity 0.25s ease;
    `;

    const imgHolder = document.createElement("img");
    imgHolder.style.cssText = `
      max-width: 92%;
      max-height: 92%;
      border-radius: 12px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.85), 0 0 30px rgba(0, 237, 149, 0.2);
      border: 1px solid rgba(0, 237, 149, 0.3);
      transition: transform 0.25s ease;
      transform: scale(0.95);
    `;

    lightbox.appendChild(imgHolder);
    document.body.appendChild(lightbox);

    docImages.forEach(function (img) {
      img.style.cursor = "zoom-in";
      img.title = "Click to enlarge";

      img.addEventListener("click", function () {
        imgHolder.src = img.src;
        lightbox.style.display = "flex";
        setTimeout(function () {
          lightbox.style.opacity = "1";
          imgHolder.style.transform = "scale(1)";
        }, 10);
      });
    });

    lightbox.addEventListener("click", function () {
      lightbox.style.opacity = "0";
      imgHolder.style.transform = "scale(0.95)";
      setTimeout(function () {
        lightbox.style.display = "none";
      }, 250);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && lightbox.style.display === "flex") {
        lightbox.click();
      }
    });
  }
});
