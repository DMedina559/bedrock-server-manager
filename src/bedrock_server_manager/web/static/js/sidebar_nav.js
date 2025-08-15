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

    // Select all navigation links within the sidebar that have the data-target attribute
    const navLinks = document.querySelectorAll('.sidebar-nav .nav-link[data-target]');
    // Select all content sections that can be shown/hidden
    const contentSections = document.querySelectorAll('.main-content .content-section'); // Select based on class

    console.debug(`${functionName}: Found ${navLinks.length} navigation links with data-target.`);
    console.debug(`${functionName}: Found ${contentSections.length} content sections.`);

    if (navLinks.length === 0 || contentSections.length === 0) {
        console.warn(`${functionName}: No navigation links or content sections found. Sidebar navigation will not function.`);
        return; // Exit if essential elements are missing
    }

    /**
     * Handles the click event on a sidebar navigation link.
     * Deactivates all other links/sections and activates the target link/section.
     * @param {Event} event - The click event object.
     */
    function switchSection(event) {
        event.preventDefault(); // Prevent default anchor link jump/navigation

        const clickedLink = event.currentTarget; // The nav link that was clicked
        const targetId = clickedLink.dataset.target; // Get the target section's ID from the link's data-target

        console.log(`switchSection: Link clicked. Target section ID: #${targetId}`);
        console.debug(`switchSection: Clicked element:`, clickedLink);

        // Find the corresponding content section element
        const targetSection = document.getElementById(targetId);

        // Only proceed if the target section exists in the DOM
        if (targetSection) {
            console.debug(`switchSection: Found target section element:`, targetSection);

            // 1. Deactivate all navigation links (remove 'active' class)
            console.debug("switchSection: Deactivating all nav links.");
            navLinks.forEach(link => {
                link.classList.remove('active');
            });

            // 2. Deactivate all content sections (remove 'active' class to hide)
            console.debug("switchSection: Deactivating all content sections.");
            contentSections.forEach(section => {
                section.classList.remove('active');
            });

            // 3. Activate the clicked navigation link
            console.debug(`switchSection: Activating clicked link:`, clickedLink);
            clickedLink.classList.add('active');

            // 4. Activate (show) the target content section
            console.debug(`switchSection: Activating target section: #${targetId}`);
            targetSection.classList.add('active');

            // Optional: Scroll to the top of the main content area for better UX
            /*
            const mainContentArea = document.querySelector('.main-content'); // Or a more specific container
            if (mainContentArea) {
                console.debug("Scrolling main content area to top.");
                mainContentArea.scrollTo({ top: 0, behavior: 'smooth' }); // Smooth scroll if supported
            }
            */
             console.log(`switchSection: Successfully switched to section #${targetId}.`);

        } else {
            // Log a warning if the link points to a non-existent section ID
            console.warn(`switchSection: Target content section with ID "${targetId}" was not found in the DOM.`);
            // Optionally show a user message:
            // showStatusMessage(`Error: Content section '${targetId}' not found.`, 'error');
        }
    } // End of switchSection function

    // Attach the click event listener to each navigation link found
    navLinks.forEach((link, index) => {
        link.addEventListener('click', switchSection);
        console.debug(`${functionName}: Added click listener to nav link #${index + 1} (Target: ${link.dataset.target})`);
    });

    // Optional: Activate initial section based on URL hash (e.g., page.html#settings-section)
    /*
    if (window.location.hash) {
        const initialTargetId = window.location.hash.substring(1); // Remove leading '#'
        console.log(`${functionName}: Found URL hash: #${initialTargetId}. Attempting to activate initial section.`);
        const initialLink = document.querySelector(`.sidebar-nav .nav-link[data-target="${initialTargetId}"]`);
        if (initialLink) {
            console.debug(`${functionName}: Found matching link for initial hash. Simulating click.`);
            initialLink.click(); // Simulate click to activate the correct link and section
        } else {
            console.warn(`${functionName}: URL hash '#${initialTargetId}' detected, but no matching nav link found.`);
        }
    } else {
         console.debug(`${functionName}: No URL hash found. Default section will be active.`);
         // Ensure the first link/section is active by default if no hash is present
         if (navLinks.length > 0) {
              console.debug(`${functionName}: Activating first nav link as default.`);
              navLinks[0].click(); // Activate the first link found
         }
    }
    */

    console.log(`${functionName}: Sidebar navigation initialization complete.`);
}); // End of DOMContentLoaded listener