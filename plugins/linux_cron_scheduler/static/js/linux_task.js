// bedrock-server-manager/web/static/js/linux_task.js
/**
 * @fileoverview Frontend JavaScript for managing Linux cron jobs via the web UI.
 * Depends on functions defined in utils.js (showStatusMessage, sendServerActionRequest).
 */

// Ensure utils.js is loaded
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("CRITICAL ERROR: Missing required functions from utils.js. Ensure utils.js is loaded first.");
}

/**
 * Hides and resets the cron job form.
 */
function cancelCronForm() {
    const cronFormSection = document.getElementById('add-modify-cron-section');
    const cronForm = document.getElementById('cron-form');
    const formTitle = document.getElementById('cron-form-title');
    const submitBtn = document.getElementById('cron-submit-btn');

    if (cronFormSection) cronFormSection.style.display = 'none';
    if (cronForm) cronForm.reset();
    if (document.getElementById('original_cron_string')) {
        document.getElementById('original_cron_string').value = '';
    }
    if (formTitle) formTitle.textContent = 'Add New Cron Job';
    if (submitBtn) submitBtn.textContent = 'Add Job';
    showStatusMessage('Operation cancelled.', 'info');
}

/**
 * Prepares and shows the form for adding a new cron job.
 */
function prepareNewCronForm() {
    const cronFormSection = document.getElementById('add-modify-cron-section');
    cancelCronForm(); // Reset form first
    if (cronFormSection) {
        cronFormSection.style.display = 'block';
        cronFormSection.scrollIntoView({ behavior: 'smooth' });
    }
}

/**
 * Populates the cron job form fields with an existing job for modification.
 * @param {string} originalCronString - The full, original cron job line.
 */
function fillModifyForm(originalCronString) {
    console.log(`Populating form to modify: '${originalCronString}'`);

    const cronFormSection = document.getElementById('add-modify-cron-section');
    const formTitle = document.getElementById('cron-form-title');
    const submitBtn = document.getElementById('cron-submit-btn');
    const originalStringInput = document.getElementById('original_cron_string');

    // Parse the cron string into its components
    const parts = originalCronString.trim().split(/\s+/);
    if (parts.length < 6) {
        showStatusMessage("Error: Could not parse the selected cron job.", "error");
        return;
    }
    const [minute, hour, day, month, weekday, ...commandParts] = parts;
    const fullCommand = commandParts.join(' ');

    // Populate time fields
    document.getElementById('minute').value = minute;
    document.getElementById('hour').value = hour;
    document.getElementById('day').value = day;
    document.getElementById('month').value = month;
    document.getElementById('weekday').value = weekday;

    // Store original string in hidden field
    if (originalStringInput) originalStringInput.value = originalCronString;

    // --- Select Command in Dropdown ---
    const commandSelect = document.getElementById('command');
    const expath = document.getElementById('cron-form')?.dataset.expath || '';
    let commandSlug = '';
    let tempCommand = fullCommand;
    if (expath && tempCommand.startsWith(expath)) {
        tempCommand = tempCommand.substring(expath.length).trim();
    }
    commandSlug = tempCommand.split(/\s+/)[0];

    let found = false;
    for (let i = 0; i < commandSelect.options.length; i++) {
        if (commandSelect.options[i].value === commandSlug) {
            commandSelect.value = commandSlug;
            found = true;
            break;
        }
    }
    if (!found) {
        console.warn(`Could not find matching command option for slug '${commandSlug}'.`);
        commandSelect.value = "";
    }

    // --- Update UI for Modify mode ---
    if (cronFormSection) {
        cronFormSection.style.display = 'block';
        cronFormSection.scrollIntoView({ behavior: 'smooth' });
    }
    if (formTitle) formTitle.textContent = 'Modify Cron Job';
    if (submitBtn) submitBtn.textContent = 'Update Job';
}

/**
 * Prompts for confirmation and initiates a request to delete a cron job.
 * @param {string} cronString - The exact cron job string to be deleted.
 * @param {string} serverName - The server context name for the API path.
 */
async function confirmDelete(cronString, serverName) {
    const trimmedCronString = cronString.trim();
    if (!trimmedCronString || !serverName) {
        showStatusMessage("Internal error: Missing cron string or server name for deletion.", "error");
        return;
    }

    if (!confirm(`Are you sure you want to delete this cron job?\n\n${trimmedCronString}`)) {
        showStatusMessage('Deletion cancelled.', 'info');
        return;
    }

    const actionPath = `cron_scheduler/delete?cron_string=${encodeURIComponent(trimmedCronString)}`;
    const response = await sendServerActionRequest(serverName, actionPath, 'DELETE', null, null);

    if (response && response.status === 'success') {
        showStatusMessage(response.message, 'success');
        setTimeout(() => window.location.reload(), 1500);
    } // Error is handled by sendServerActionRequest
}

// --- Add/Modify Form Submission Handler ---
document.addEventListener('DOMContentLoaded', () => {
    const cronForm = document.getElementById('cron-form');
    if (!cronForm) return;

    cronForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        const serverName = cronForm.dataset.serverName;
        const EXPATH = cronForm.dataset.expath;
        const submitButton = document.getElementById('cron-submit-btn');

        const command = document.getElementById('command').value;
        const minute = document.getElementById('minute').value.trim();
        const hour = document.getElementById('hour').value.trim();
        const day = document.getElementById('day').value.trim();
        const month = document.getElementById('month').value.trim();
        const weekday = document.getElementById('weekday').value.trim();
        const originalCronString = document.getElementById('original_cron_string').value.trim();

        if (!command || !minute || !hour || !day || !month || !weekday) {
            showStatusMessage("Please fill in all command and time fields.", "warning");
            return;
        }

        // Construct the full command part of the cron job
        const commandArg = (command !== "scan-players") ? `--server "${serverName}"` : "";
        const fullCommand = `${EXPATH} ${command} ${commandArg}`.trim();
        const newCronString = `${minute} ${hour} ${day} ${month} ${weekday} ${fullCommand}`;

        let actionPath;
        let requestBody;
        const method = 'POST'; // Both Add and Modify use POST

        if (originalCronString) { // MODIFY
            actionPath = 'cron_scheduler/modify';
            requestBody = { old_cron_job: originalCronString, new_cron_job: newCronString };
        } else { // ADD
            actionPath = 'cron_scheduler/add';
            requestBody = { new_cron_job: newCronString };
        }

        const response = await sendServerActionRequest(serverName, actionPath, method, requestBody, submitButton);

        if (response && response.status === 'success') {
            showStatusMessage(response.message, "success");
            cancelCronForm();
            setTimeout(() => window.location.reload(), 1500);
        } // Error message is handled by sendServerActionRequest
    });
});