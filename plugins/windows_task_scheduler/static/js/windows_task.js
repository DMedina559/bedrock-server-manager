// bedrock_server_manager/web/static/js/windows_task.js
/**
 * @fileoverview Frontend JavaScript for managing Windows Scheduled Tasks via the web UI.
 * Handles dynamic form creation for triggers, populating the form for modification,
 * validating user input, confirming deletions, and interacting with the backend API.
 */

// Ensure utils.js is loaded
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("CRITICAL ERROR: Missing required functions from utils.js. Ensure utils.js is loaded first.");
}

/**
 * Gets references to essential DOM elements for the task scheduler UI.
 * @returns {object|null} An object containing references to elements, or null if critical elements are missing.
 */
function getTaskSchedulerDOMElements() {
    const elements = {
        taskForm: document.getElementById('task-form'),
        formSection: document.getElementById('add-modify-task-section'),
        formTitle: document.getElementById('form-title'),
        commandSelect: document.getElementById('command'),
        originalTaskNameInput: document.getElementById('original_task_name'),
        triggersContainer: document.getElementById('triggers-container'),
        submitButton: document.getElementById('submit-task-btn'),
        addTriggerButton: document.getElementById('add-trigger-btn')
    };

    if (!elements.taskForm || !elements.formSection || !elements.triggersContainer) {
        console.error("Critical task scheduler elements missing:", elements);
        showStatusMessage("Internal page error: Task form structure incomplete.", "error");
        return null;
    }
    return elements;
}

/**
 * Prompts user and initiates the deletion of a Windows task via API.
 * @param {string} taskName - The name of the task to delete.
 * @param {string} serverName - The server context name for the API path.
 */
async function confirmDeleteWindows(taskName, serverName) {
    if (!taskName || !serverName) {
        showStatusMessage("Internal error: Task name and Server name are required for deletion.", "error");
        return;
    }

    const confirmationMessage = `Are you sure you want to delete the scheduled task '${taskName}'?\n\nThis action cannot be undone.`;
    if (!confirm(confirmationMessage)) {
        showStatusMessage(`Deletion of task '${taskName}' cancelled.`, 'info');
        return;
    }

    // New API endpoint uses the task name in the URL path
    const actionPath = `task_scheduler/task/${encodeURIComponent(taskName)}`;
    const method = 'DELETE';

    console.log(`Calling API to ${method} ${actionPath} for server '${serverName}'...`);
    const response = await sendServerActionRequest(serverName, actionPath, method, null, null);

    if (response && response.status === 'success') {
        showStatusMessage(response.message || `Task '${taskName}' deleted successfully. Reloading...`, 'success');
        setTimeout(() => window.location.reload(), 1500);
    } // Error is handled by sendServerActionRequest
}

/**
 * Prepares the form for modifying an existing task.
 * It does NOT fetch detailed trigger data; modification is a "replace" operation.
 * @param {string} taskName - The name of the task to modify.
 * @param {string} command - The existing command of the task to pre-select.
 */
function prepareModifyFormWindows(taskName, command) {
    console.log(`Preparing form to modify task '${taskName}' with existing command '${command}'.`);
    const elements = getTaskSchedulerDOMElements();
    if (!elements) return;

    elements.formSection.style.display = 'block';
    elements.formTitle.textContent = `Modify Task: ${taskName}`;
    elements.originalTaskNameInput.value = taskName; // Store original name to signal "modify" mode
    elements.triggersContainer.innerHTML = ''; // Clear previous triggers
    triggerCounter = 0; // Reset trigger counter

    // Pre-select the existing command in the dropdown
    if (elements.commandSelect) {
        elements.commandSelect.value = command;
    }

    addTrigger(); // Add one blank trigger group for the user to define the new schedule

    elements.formSection.scrollIntoView({ behavior: 'smooth' });
    showStatusMessage(`Define the new command and schedule for task '${taskName}'. The existing task will be replaced.`, 'info');
}

/**
 * Resets and displays the add/modify form for adding a NEW task.
 */
function prepareNewTaskForm() {
    console.log("Preparing form for adding a new Windows task.");
    const elements = getTaskSchedulerDOMElements();
    if (!elements) return;

    elements.formSection.style.display = 'block';
    elements.formTitle.textContent = 'Add New Scheduled Task';
    elements.taskForm.reset();
    elements.originalTaskNameInput.value = ''; // Empty value signals "add" mode
    elements.triggersContainer.innerHTML = '';
    triggerCounter = 0;

    addTrigger(); // Add one blank trigger group to start

    elements.formSection.scrollIntoView({ behavior: 'smooth' });
    showStatusMessage("Enter details for the new task.", "info");
}

/**
 * Hides and resets the add/modify task form.
 */
function cancelTaskForm() {
    const elements = getTaskSchedulerDOMElements();
    if (!elements) return;

    elements.formSection.style.display = 'none';
    elements.taskForm.reset();
    elements.originalTaskNameInput.value = '';
    elements.triggersContainer.innerHTML = '';
    triggerCounter = 0;

    showStatusMessage("Task operation cancelled.", "info");
}

/**
 * Adds a new UI group for defining a task trigger.
 */
function addTrigger() {
    triggerCounter++;
    const triggerNum = triggerCounter;
    const elements = getTaskSchedulerDOMElements();
    if (!elements?.triggersContainer) return;

    const div = document.createElement('div');
    div.className = 'trigger-group';
    div.id = `trigger-group-${triggerNum}`;
    div.style.border = '1px solid #ccc';
    div.style.padding = '10px';
    div.style.marginBottom = '15px';

    div.innerHTML = `
        <button type="button" class="remove-trigger-btn" onclick="removeTrigger(${triggerNum})" title="Remove This Trigger">×</button>
        <h4>Trigger ${triggerNum}</h4>
        <div class="form-group">
            <label for="trigger_type_${triggerNum}" class="form-label">Trigger Type:</label>
            <select id="trigger_type_${triggerNum}" name="trigger_type_${triggerNum}" class="form-input" onchange="showTriggerFields(${triggerNum})">
                <option value="">-- Select Type --</option>
                <option value="Daily">Daily</option>
                <option value="Weekly">Weekly</option>
            </select>
        </div>
        <div id="trigger_fields_${triggerNum}" class="trigger-fields-container"></div>
    `;
    elements.triggersContainer.appendChild(div);
    showTriggerFields(triggerNum);
}

/**
 * Removes a trigger group UI element.
 * @param {number} triggerNum - The unique number of the trigger group to remove.
 */
function removeTrigger(triggerNum) {
    const triggerGroup = document.getElementById(`trigger-group-${triggerNum}`);
    if (triggerGroup) {
        triggerGroup.remove();
        const elements = getTaskSchedulerDOMElements();
        if (elements?.triggersContainer.querySelectorAll('.trigger-group').length === 0) {
            addTrigger();
        }
    }
}

/**
 * Dynamically displays input fields based on the selected trigger type.
 * @param {number} triggerNum - The unique number of the trigger group.
 */
function showTriggerFields(triggerNum) {
    const typeSelect = document.getElementById(`trigger_type_${triggerNum}`);
    const fieldsDiv = document.getElementById(`trigger_fields_${triggerNum}`);
    if (!typeSelect || !fieldsDiv) return;

    const selectedType = typeSelect.value;
    fieldsDiv.innerHTML = ''; // Clear previous fields

    if (!selectedType) return; // Don't show fields if no type is selected

    fieldsDiv.innerHTML += `
        <div class="form-group">
            <label for="start_${triggerNum}" class="form-label">Start Time:</label>
            <input type="time" id="start_${triggerNum}" name="start_${triggerNum}" class="form-input trigger-field" required>
            <small>The time of day the trigger runs.</small>
        </div>
    `;

    if (selectedType === 'Weekly') {
        const daysOfWeekOptions = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        let checkboxesHTML = daysOfWeekOptions.map(dayName => `
            <label class="checkbox-label" style="margin-right: 15px;">
                <input type="checkbox" class="trigger-field" name="days_of_week_${triggerNum}" value="${dayName}"> ${dayName}
            </label>`).join('');

        fieldsDiv.innerHTML += `
            <div class="form-group">
                <label class="form-label">Run on Days:</label><br>
                <div class="checkbox-group">${checkboxesHTML}</div>
            </div>
        `;
    }
}

// --- Form Submission Event Listener ---
document.addEventListener('DOMContentLoaded', () => {
    const elements = getTaskSchedulerDOMElements();
    if (!elements?.taskForm) return;

    const serverName = elements.taskForm.dataset.serverName;

    elements.taskForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const submitButton = elements.submitButton;
        const originalTaskName = elements.originalTaskNameInput.value.trim();
        const command = elements.commandSelect.value;

        if (!command) {
            showStatusMessage("Please select a command.", "warning");
            return;
        }

        let triggers = [];
        let formIsValid = true;
        const triggerGroups = elements.triggersContainer.querySelectorAll('.trigger-group');

        if (triggerGroups.length === 0) {
            showStatusMessage("Please add at least one trigger.", "warning");
            return;
        }

        triggerGroups.forEach((group, index) => {
            if (!formIsValid) return;

            const triggerNum = group.id.split('-').pop();
            const triggerType = group.querySelector(`#trigger_type_${triggerNum}`).value;
            const startTime = group.querySelector(`#start_${triggerNum}`).value; // HH:MM

            if (!triggerType || !startTime) {
                formIsValid = false;
                showStatusMessage(`Trigger ${index + 1}: Please select a type and start time.`, "warning");
                return;
            }

            // Set date part to today to create a valid ISO string
            const now = new Date();
            const [hours, minutes] = startTime.split(':');
            now.setHours(hours, minutes, 0, 0);

            let triggerData = { type: triggerType, start: now.toISOString() };

            if (triggerType === 'Weekly') {
                const dayCheckboxes = group.querySelectorAll(`input[name="days_of_week_${triggerNum}"]:checked`);
                triggerData.days = Array.from(dayCheckboxes).map(cb => cb.value);
                if (triggerData.days.length === 0) {
                    formIsValid = false;
                    showStatusMessage(`Trigger ${index + 1}: Select at least one day for a weekly trigger.`, "warning");
                }
            } else if (triggerType === 'Daily') {
                triggerData.interval = 1; // Backend expects this
            }

            if (formIsValid) {
                triggers.push(triggerData);
            }
        });

        if (!formIsValid || triggers.length === 0) {
            showStatusMessage("Form submission failed: Please correct the trigger errors.", "error");
            return;
        }

        const method = originalTaskName ? 'PUT' : 'POST';
        const actionPath = originalTaskName ? `task_scheduler/task/${encodeURIComponent(originalTaskName)}` : 'task_scheduler/add';
        const requestBody = { command, triggers };

        const response = await sendServerActionRequest(serverName, actionPath, method, requestBody, submitButton);

        if (response && response.status === 'success') {
            const successMsg = response.message || `Task ${originalTaskName ? 'modified' : 'added'} successfully! Reloading...`;
            showStatusMessage(successMsg, 'success');
            cancelTaskForm();
            setTimeout(() => window.location.reload(), 1500);
        } // Error is handled by sendServerActionRequest
    });
});