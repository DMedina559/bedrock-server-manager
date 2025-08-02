// bedrock-server-manager/web/static/js/sidebar_nav.js
/**
 * @fileoverview Handles client-side navigation within a single page using a sidebar.
 * It listens for clicks on sidebar navigation links (`.sidebar-nav .nav-link`)
 * that have a `data-target` attribute pointing to the ID of a content section
 * (`.main-content .content-section`). Clicking a link shows the target section
 * and hides others, while visually activating the clicked link.
 */

document.addEventListener('DOMContentLoaded', () => {
    const functionName = 'DOMContentLoaded (Sidebar Nav)';
    console.log(`${functionName}: Initializing sidebar navigation logic.`);

    const navLinks = document.querySelectorAll('.sidebar-nav .nav-link');
    const contentSections = document.querySelectorAll('.main-content .content-section');
    const submenuLinks = document.querySelectorAll('.sidebar-nav .has-submenu');

    if (navLinks.length === 0) {
        console.warn(`${functionName}: No navigation links found. Sidebar will not function.`);
        return;
    }

    function switchSection(event) {
        const clickedLink = event.currentTarget;
        const targetId = clickedLink.dataset.target;

        if (!targetId) {
            return;
        }

        event.preventDefault();
        console.log(`switchSection: Link clicked. Target section ID: #${targetId}`);

        const targetSection = document.getElementById(targetId);

        if (targetSection) {
            navLinks.forEach(link => link.classList.remove('active'));
            contentSections.forEach(section => section.classList.remove('active'));

            clickedLink.classList.add('active');
            targetSection.classList.add('active');

            // Handle parent menu activation
            const parentItem = clickedLink.closest('.nav-item');
            if (parentItem) {
                const parentLink = parentItem.querySelector('.has-submenu');
                if (parentLink) {
                    parentLink.classList.add('active');
                }
            }

            console.log(`switchSection: Successfully switched to section #${targetId}.`);
        } else {
            console.warn(`switchSection: Target content section with ID "${targetId}" was not found.`);
        }
    }

    function toggleSubmenu(event) {
        event.preventDefault();
        const clickedLink = event.currentTarget;
        const submenu = clickedLink.nextElementSibling;

        if (submenu && submenu.classList.contains('submenu')) {
            if (submenu.style.maxHeight) {
                submenu.style.maxHeight = null;
            } else {
                submenu.style.maxHeight = submenu.scrollHeight + "px";
            }
        }
    }

    navLinks.forEach(link => {
        if (link.dataset.target) {
            link.addEventListener('click', switchSection);
        }
    });

    submenuLinks.forEach(link => {
        link.addEventListener('click', toggleSubmenu);
    });

    if (navLinks.length > 0 && navLinks[0].dataset.target) {
        navLinks[0].click();
    }

    console.log(`${functionName}: Sidebar navigation initialization complete.`);
});