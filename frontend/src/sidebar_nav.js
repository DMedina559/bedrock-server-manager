// frontend/src/sidebar_nav.js
/**
 * @fileoverview Handles client-side navigation within a single page using a sidebar.
 */

export function initializeSidebarNav() {
  const navLinks = document.querySelectorAll('.sidebar-nav .nav-link');
  const contentSections = document.querySelectorAll('.main-content .content-section');
  const submenuLinks = document.querySelectorAll('.sidebar-nav .has-submenu');

  if (navLinks.length === 0) {
    console.warn('Sidebar navigation links not found.');
    return;
  }

  function switchSection(event) {
    event.preventDefault();
    const clickedLink = event.currentTarget;
    const targetId = clickedLink.dataset.target;
    if (!targetId) return;

    const targetSection = document.getElementById(targetId);
    if (targetSection) {
      navLinks.forEach((link) => link.classList.remove('active'));
      contentSections.forEach((section) => section.classList.remove('active'));

      clickedLink.classList.add('active');
      targetSection.classList.add('active');

      const parentSubmenu = clickedLink.closest('.submenu');
      if (parentSubmenu) {
        parentSubmenu.style.maxHeight = parentSubmenu.scrollHeight + 'px';
        const parentLink = parentSubmenu.previousElementSibling;
        if (parentLink && parentLink.classList.contains('has-submenu')) {
          parentLink.classList.add('active');
        }
      }
    }
  }

  function toggleSubmenu(event) {
    event.preventDefault();
    const clickedLink = event.currentTarget;
    const submenu = clickedLink.nextElementSibling;
    if (submenu && submenu.classList.contains('submenu')) {
      submenu.style.maxHeight = submenu.style.maxHeight ? null : submenu.scrollHeight + 'px';
    }
  }

  navLinks.forEach((link) => {
    if (link.dataset.target) {
      link.addEventListener('click', switchSection);
    }
  });

  submenuLinks.forEach((link) => {
    link.addEventListener('click', toggleSubmenu);
  });

  // Activate the first link if it's a section link
  if (navLinks.length > 0 && navLinks[0].dataset.target) {
    navLinks[0].click();
  }

  console.log('Sidebar navigation initialized.');
}
