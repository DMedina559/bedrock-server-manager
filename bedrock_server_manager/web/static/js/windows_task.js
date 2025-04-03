// bedrock-server-manager/bedrock_server_manager/web/static/js/windows_task.js
// --- Constants ---
const serverName = pageConfig.serverName; // Get server name from Jinja2
let triggerCounter = 0; // Counter for unique trigger IDs

// --- DOM Elements ---
const taskForm = document.getElementById('task-form');
const formSection = document.getElementById('add-modify-task-section');
const formTitle = document.getElementById('form-title');
const commandSelect = document.getElementById('command');
const originalTaskNameInput = document.getElementById('original_task_name');
const triggersContainer = document.getElementById('triggers-container');
const submitButton = document.getElementById('submit-task-btn');

// --- Delete Task Function ---
async function confirmDeleteWindows(taskName) {
    if (confirm(`Are you sure you want to delete the task '${taskName}'? This action cannot be undone.`)) {
        console.log(`Attempting to delete task: ${taskName}`);
        // Construct the relative API path, encoding the task name for URL safety
        const actionPath = `tasks/delete/${encodeURIComponent(taskName)}`;
        const method = 'DELETE'; // Use DELETE HTTP method

        // Call the utility function to send the request
        const responseData = await sendServerActionRequest(serverName, actionPath, method, null, null); // No body needed, no specific button

        if (responseData && responseData.status === 'success') {
            console.log(`Task '${taskName}' deletion successful. Reloading page.`);
            showStatusMessage(responseData.message || `Task '${taskName}' deleted.`, 'success');
            // Reload the page after a short delay to show the message
            setTimeout(() => { window.location.reload(); }, 1500);
        } else {
            // Error message is handled by sendServerActionRequest, just log a warning here
            console.warn(`Task '${taskName}' deletion failed or reported non-success.`);
        }
    } else {
        console.log("User cancelled task deletion.");
    }
}

/**
 * Fetches details for a specific Windows task via API and populates the
 * add/modify form for editing.
 *
 * @param {string} taskName The name of the task to modify.
 */
async function fillModifyFormWindows(taskName) {
    // Log entry and task name
    console.log(`Preparing form to modify task: ${taskName}`);
    // Show immediate feedback to the user
    showStatusMessage(`Loading data for task '${taskName}'...`, 'info');

    // --- Ensure form elements are accessible ---
    const formSection = document.getElementById('add-modify-task-section');
    const formTitle = document.getElementById('form-title');
    const taskForm = document.getElementById('task-form'); // Get the form itself for reset later if needed
    const commandSelect = document.getElementById('command');
    const originalTaskNameInput = document.getElementById('original_task_name');
    const triggersContainer = document.getElementById('triggers-container');

    if (!formSection || !formTitle || !taskForm || !commandSelect || !originalTaskNameInput || !triggersContainer) {
         console.error("One or more required form elements not found. Cannot proceed with modify.");
         showStatusMessage("Form error: Required elements missing. Please refresh.", "error");
         return;
    }

    // --- Prepare the form UI ---
    formSection.style.display = 'block'; // Show the form section
    formTitle.textContent = `Modify Task: ${taskName}`; // Update form title
    originalTaskNameInput.value = taskName; // Store original name in hidden field
    triggersContainer.innerHTML = ''; // Clear any previous triggers
    triggerCounter = 0; // Reset trigger counter
    commandSelect.disabled = true; // Disable command select while loading

    // --- Fetch existing task details using the API ---
    const actionPath = `tasks/details/${encodeURIComponent(taskName)}`; // Encode name for URL safety
    const method = 'GET';

    // Call utility function to make the API request
    const taskData = await sendServerActionRequest(serverName, actionPath, method, null, null);

    // --- Handle API Response ---
    // Check if fetching data was successful (sendServerActionRequest handles basic errors)
    if (!taskData || taskData.status !== 'success') {
        // sendServerActionRequest should have already shown an error message
        console.error(`Failed to load task data for '${taskName}'. API response:`, taskData);
        showStatusMessage(`Error loading task data for '${taskName}'. Cannot modify. ${taskData?.message || 'Check console.'}`, 'error');
        cancelTaskForm(); // Hide form again if data loading fails
        commandSelect.disabled = false; // Re-enable command select on failure
        return;
    }

    // --- Populate form fields with fetched data ---
    console.log("Successfully fetched task data:", taskData);

    // 1. Set Command Dropdown
    let commandFound = false;
    // Use 'base_command' field expected from the enhanced details handler
    const fetchedBaseCommand = taskData.base_command;
    console.log("Fetched base_command for dropdown:", fetchedBaseCommand);

    if (fetchedBaseCommand) {
        for (let i = 0; i < commandSelect.options.length; i++) {
            // Case-insensitive comparison for robustness
            if (commandSelect.options[i].value.toLowerCase() === fetchedBaseCommand.toLowerCase()) {
                commandSelect.value = commandSelect.options[i].value; // Set dropdown value
                commandFound = true;
                console.log(`Set command dropdown to: ${commandSelect.value}`);
                break;
            }
        }
    }
    // Warn if the fetched command doesn't match any dropdown option
    if (!commandFound) {
        console.warn(`Fetched base command '${fetchedBaseCommand}' not found in dropdown options. Leaving dropdown unselected.`);
        commandSelect.value = ""; // Reset to default "-- Select Command --"
    }
    // Re-enable the command dropdown after populating
    commandSelect.disabled = false;


    // 2. Populate Triggers
    // Clear container again just in case (should be empty already)
    triggersContainer.innerHTML = '';
    triggerCounter = 0; // Reset counter before adding

    if (taskData.triggers && Array.isArray(taskData.triggers)) {
         if (taskData.triggers.length === 0) {
            // If the task exists but has no triggers (unlikely but possible)
            console.warn("Task data loaded successfully but contains no triggers. Adding one blank trigger group.");
            addTrigger(); // Add a blank one so user can define one
         } else {
            // Iterate through the triggers array from the API response
            taskData.triggers.forEach(trigger => {
                console.log("Populating trigger group for:", trigger);
                // Call addTrigger, passing the data for this specific trigger
                // addTrigger will handle creating the group and calling showTriggerFields
                addTrigger(trigger);
            });
         }
    } else {
        // Handle case where 'triggers' key is missing or not an array
        console.warn("API response missing 'triggers' array or it's invalid. Adding one blank trigger group.");
        addTrigger(); // Add at least one blank trigger group
    }
    // --- End Form Population ---

    // Final feedback and UI adjustment
    showStatusMessage(`Task data loaded for '${taskName}'. Ready to modify.`, 'info');
    formSection.scrollIntoView({ behavior: 'smooth' }); // Scroll form into view
}

// --- Prepare Form for New Task Function ---
function prepareNewTaskForm() {
    console.log("Preparing form for new task.");
    formSection.style.display = 'block'; // Show the form section
    formTitle.textContent = 'Add New Task'; // Set title
    taskForm.reset(); // Reset standard form fields (like command dropdown)
    originalTaskNameInput.value = ''; // Ensure hidden field is empty for 'add' mode
    triggersContainer.innerHTML = ''; // Clear any previous trigger UI
    triggerCounter = 0; // Reset trigger counter
    addTrigger(); // Add one blank trigger group to start with
    formSection.scrollIntoView({ behavior: 'smooth' }); // Scroll form into view
     commandSelect.disabled = false; // Ensure command select is enabled
}

// --- Cancel/Hide Form Function ---
function cancelTaskForm() {
    formSection.style.display = 'none'; // Hide the form section
    taskForm.reset(); // Reset fields
    originalTaskNameInput.value = ''; // Clear hidden field
    triggersContainer.innerHTML = ''; // Clear triggers UI
    triggerCounter = 0; // Reset counter
    showStatusMessage("Operation cancelled.", "info"); // Optional feedback
}

// --- Dynamic Trigger Logic ---

// Adds a new trigger group UI (optionally populated with existing data)
function addTrigger(existingTriggerData = null) {
    triggerCounter++;
    const triggerNum = triggerCounter;
    const div = document.createElement('div');
    div.className = 'trigger-group';
    div.id = `trigger-group-${triggerNum}`;
    // Basic structure with remove button and type selector
    div.innerHTML = `
        <button type="button" class="remove-trigger-btn" onclick="removeTrigger(${triggerNum})" title="Remove Trigger">×</button>
        <h3>Trigger ${triggerNum}</h3>
        <div class="form-group">
            <label for="trigger_type_${triggerNum}" class="form-label">Trigger Type:</label>
            <select id="trigger_type_${triggerNum}" name="trigger_type_${triggerNum}" class="form-input" onchange="showTriggerFields(${triggerNum})">
                <option value="">-- Select Trigger Type --</option>
                <option value="TimeTrigger">One Time</option>
                <option value="Daily">Daily</option>
                <option value="Weekly">Weekly</option>
                <option value="Monthly">Monthly</option>
                <!-- Add other supported trigger types here -->
            </select>
        </div>
        <div id="trigger_fields_${triggerNum}">
            <!-- Dynamic fields based on type selection -->
        </div>
    `;
    triggersContainer.appendChild(div);

    // If modifying, select the type and populate the specific fields
    if (existingTriggerData) {
        const typeSelect = div.querySelector(`#trigger_type_${triggerNum}`);
        if(existingTriggerData.type && typeSelect){
            // Find the option matching the type (case-insensitive check might be good)
            let foundType = false;
            for(let i=0; i < typeSelect.options.length; i++) {
                if(typeSelect.options[i].value.toLowerCase() === existingTriggerData.type.toLowerCase()){
                    typeSelect.value = typeSelect.options[i].value;
                    foundType = true;
                    break;
                }
            }
            if (!foundType) {
                 console.warn(`Trigger ${triggerNum}: Existing trigger type '${existingTriggerData.type}' not found in dropdown.`)
            }
            // Call showTriggerFields AFTER setting the select value to populate correctly
            showTriggerFields(triggerNum, existingTriggerData);
        } else {
             console.warn(`Trigger ${triggerNum}: Existing trigger data missing 'type' or typeSelect element not found.`, existingTriggerData);
             showTriggerFields(triggerNum); // Show default fields for blank type
        }
    } else {
         showTriggerFields(triggerNum); // Show default fields for new trigger
    }
}

// Removes a trigger group UI
function removeTrigger(triggerNum) {
    const triggerGroup = document.getElementById(`trigger-group-${triggerNum}`);
    if (triggerGroup) {
        triggerGroup.remove();
        console.log(`Removed trigger group ${triggerNum}`);
    } else {
         console.warn(`Could not find trigger group ${triggerNum} to remove.`);
    }
    // Optional: Check if last trigger was removed and add a blank one back?
     if (triggersContainer.querySelectorAll('.trigger-group').length === 0) {
         console.log("Last trigger removed, adding a new blank one.");
         addTrigger();
     }
}

// Shows/updates the specific fields based on the selected trigger type
function showTriggerFields(triggerNum, data = null) {
    const typeSelect = document.getElementById(`trigger_type_${triggerNum}`);
    const fieldsDiv = document.getElementById(`trigger_fields_${triggerNum}`);
    if (!typeSelect || !fieldsDiv) {
         console.error(`Could not find elements for trigger ${triggerNum} in showTriggerFields.`);
         return;
    }
    const type = typeSelect.value;
    fieldsDiv.innerHTML = ''; // Clear previous fields

    // --- Always add Start Time/Date field ---
    // Backend handler provides date in YYYY-MM-DDTHH:MM format, suitable for datetime-local
    const startValueRaw = data?.start || '';
    fieldsDiv.innerHTML += `
        <div class="form-group">
            <label for="start_${triggerNum}" class="form-label">Start Date & Time:</label>
            <input type="datetime-local" id="start_${triggerNum}" name="start_${triggerNum}" class="form-input" value="${startValueRaw}" required>
        </div>
    `;
    console.debug(`Trigger ${triggerNum}: Type='${type}'. Setting start value: '${startValueRaw}'`);

    // --- Add Type-Specific Fields ---
    if (type === 'Daily') {
         const intervalValue = data?.interval || '1'; // Default to 1 day
        fieldsDiv.innerHTML += `
            <div class="form-group">
                <label for="interval_${triggerNum}" class="form-label">Repeat Every (Days):</label>
                <input type="number" id="interval_${triggerNum}" name="interval_${triggerNum}" class="form-input" value="${intervalValue}" min="1" required>
            </div>
        `;
    } else if (type === 'Weekly') {
        const intervalValue = data?.interval || '1'; // Default to 1 week
        // Handler returns days_of_week as comma-separated string ("Mon,Wed,Fri")
        const daysValueString = data?.days_of_week || '';
        const daysValueArray = daysValueString ? daysValueString.split(',').map(d => d.trim().toLowerCase()) : [];
        console.debug(`Trigger ${triggerNum} Weekly: Raw days='${daysValueString}', Parsed days=`, daysValueArray);

        // Use full day names for consistency in value and display
        const daysOfWeekOptions = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

        let checkboxesHTML = daysOfWeekOptions.map(dayName => {
            // Check if the parsed array includes the current day name (case-insensitive)
            const isChecked = daysValueArray.includes(dayName.toLowerCase());
             return `
                <label style="margin-right: 10px; display: inline-block;">
                    <input type="checkbox" name="days_of_week_${triggerNum}" value="${dayName}" ${isChecked ? 'checked' : ''}> ${dayName}
                </label>
            `;
        }).join('\n'); // Add newline for slightly better source readability

        fieldsDiv.innerHTML += `
            <div class="form-group">
                <label for="interval_${triggerNum}" class="form-label">Repeat Every (Weeks):</label>
                <input type="number" id="interval_${triggerNum}" name="interval_${triggerNum}" class="form-input" value="${intervalValue}" min="1" required>
            </div>
            <div class="form-group">
                <label class="form-label">Run on Days:</label><br>
                ${checkboxesHTML}
            </div>
        `;
    } else if (type === 'Monthly') {
         // Handler returns days_of_month and months as comma-separated strings
         const daysValue = data?.days_of_month || '';
         const monthsValue = data?.months || '';
         console.debug(`Trigger ${triggerNum} Monthly: Raw days='${daysValue}', Raw months='${monthsValue}'`);

         fieldsDiv.innerHTML += `
             <div class="form-group">
                 <label for="days_of_month_${triggerNum}" class="form-label">Days of Month (comma-separated):</label>
                 <input type="text" id="days_of_month_${triggerNum}" name="days_of_month_${triggerNum}" class="form-input" value="${daysValue}" placeholder="e.g., 1,15,31">
             </div>
             <div class="form-group">
                 <label for="months_${triggerNum}" class="form-label">Months (comma-separated):</label>
                 <input type="text" id="months_${triggerNum}" name="months_${triggerNum}" class="form-input" value="${monthsValue}" placeholder="e.g., Jan,Feb,Mar or 1,2,3">
                 <small>Leave blank for all months if days are specified.</small>
             </div>
         `;
    }

} // --- End of showTriggerFields ---


// --- Form Submission Event Listener ---
taskForm.addEventListener('submit', async function(event) {
    event.preventDefault(); // Stop default browser form submission
    console.log("Task form submitted via JavaScript.");

    const originalTaskName = originalTaskNameInput.value; // Original name if modifying
    const command = commandSelect.value; // Selected command

    // Basic validation
    if (!command) {
        showStatusMessage("Please select a command.", "error");
        commandSelect.focus();
        return;
    }

    // --- Parse Triggers from Form ---
    let triggers = []; // Array to hold trigger data objects
    const triggerGroups = triggersContainer.querySelectorAll('.trigger-group');
    let formIsValid = true; // Flag to track validation status

    // Check if at least one trigger group exists
    if (triggerGroups.length === 0) {
         showStatusMessage("At least one trigger must be added to the task.", "error");
         // Optionally call addTrigger() here? Or just let user add one.
         return;
    }

    // Loop through each trigger group UI element
    triggerGroups.forEach(group => {
        if (!formIsValid) return; // Stop processing if an earlier trigger failed validation

        const triggerNum = group.id.split('-').pop(); // Get the number suffix
        const triggerTypeSelect = group.querySelector(`#trigger_type_${triggerNum}`);
        const triggerType = triggerTypeSelect ? triggerTypeSelect.value : null;
        const startInput = group.querySelector(`#start_${triggerNum}`);
        const startValue = startInput ? startInput.value : null; // YYYY-MM-DDTHH:MM

        // Validate common fields
        if (!triggerType) {
             showStatusMessage(`Please select a trigger type for Trigger ${triggerNum}.`, "error");
             triggerTypeSelect.focus();
             formIsValid = false;
             return;
        }
         if (!startValue) {
             showStatusMessage(`Please select a start date/time for Trigger ${triggerNum}.`, "error");
             startInput.focus();
             formIsValid = false;
              return;
         }

        // --- Create base trigger data object ---
        let triggerData = {
            type: triggerType,
            // Convert datetime-local string to ISO 8601 UTC string for backend/JSON
            start: new Date(startValue).toISOString()
        };
        console.debug(`Trigger ${triggerNum}: Parsed type='${triggerType}', start='${triggerData.start}'`);

        // --- Add type-specific data and validation ---
         if (triggerType === 'Daily') {
             const intervalInput = group.querySelector(`#interval_${triggerNum}`);
             const intervalValue = intervalInput ? parseInt(intervalInput.value, 10) : NaN;
             if (isNaN(intervalValue) || intervalValue < 1) {
                 showStatusMessage(`Invalid daily interval for Trigger ${triggerNum}. Must be 1 or greater.`, "error");
                 intervalInput.focus();
                 formIsValid = false; return;
             }
             triggerData.interval = intervalValue;
         } else if (triggerType === 'Weekly') {
              const intervalInput = group.querySelector(`#interval_${triggerNum}`);
              const intervalValue = intervalInput ? parseInt(intervalInput.value, 10) : NaN;
              if (isNaN(intervalValue) || intervalValue < 1) {
                  showStatusMessage(`Invalid weekly interval for Trigger ${triggerNum}. Must be 1 or greater.`, "error");
                  intervalInput.focus();
                  formIsValid = false; return;
              }
              triggerData.interval = intervalValue;

              // Get selected days
              const dayCheckboxes = group.querySelectorAll(`input[name="days_of_week_${triggerNum}"]:checked`);
               triggerData.days = Array.from(dayCheckboxes).map(cb => cb.value); // Get array of selected day names/values
               if (triggerData.days.length === 0) {
                    showStatusMessage(`Select at least one day for weekly Trigger ${triggerNum}.`, "error");
                    // Find first checkbox to highlight area conceptually
                    const firstCheckbox = group.querySelector(`input[name="days_of_week_${triggerNum}"]`);
                    if(firstCheckbox) firstCheckbox.focus(); // Focus might not be ideal, consider highlighting parent div
                    formIsValid = false; return;
               }
         } else if (triggerType === 'Monthly') {
             const daysInput = group.querySelector(`#days_of_month_${triggerNum}`);
             const monthsInput = group.querySelector(`#months_${triggerNum}`);
             // Basic parsing, backend should perform more robust validation
              triggerData.days = daysInput ? daysInput.value.split(',').map(d => d.trim()).filter(Boolean) : [];
              triggerData.months = monthsInput ? monthsInput.value.split(',').map(m => m.trim()).filter(Boolean) : [];
         }
         // Add parsing logic for other trigger types here

        // If validation passed for this trigger, add it to the list
        if (formIsValid) {
            triggers.push(triggerData);
        }
    }); // --- End loop through trigger groups ---

    // If validation failed at any point, stop submission
    if (!formIsValid) {
        console.warn("Form submission stopped due to validation errors in triggers.");
        return;
    }

    // Double-check if triggers array is populated after loop (should be if validation passed)
     if (triggers.length === 0) {
          showStatusMessage("Could not parse any valid triggers. Please check your trigger configurations.", "error");
          return;
     }

    console.log("Final parsed triggers to be sent:", triggers);

    // --- Prepare API Request ---
    let method;
    let actionPath;
    // Body contains the selected command and the parsed triggers array
    const requestBody = {
        command: command,
        triggers: triggers
    };

    if (originalTaskName) {
        // This is a MODIFY operation
        method = 'PUT'; // Use PUT for update/replace
        actionPath = `tasks/modify/${encodeURIComponent(originalTaskName)}`; // Include original name in path
        console.log(`Preparing MODIFY request to: ${actionPath} with body:`, requestBody);
    } else {
        // This is an ADD operation
        method = 'POST'; // Use POST for create
        actionPath = 'tasks/add';
         console.log(`Preparing ADD request to: ${actionPath} with body:`, requestBody);
    }

    // --- Send API Request using utility function ---
     const responseData = await sendServerActionRequest(serverName, actionPath, method, requestBody, submitButton);

     // --- Handle API Response ---
     if (responseData && responseData.status === 'success') {
          console.log(`Task add/modify successful. Response:`, responseData);
          showStatusMessage(responseData.message || `Task saved successfully!`, 'success');
          cancelTaskForm(); // Hide and reset the form on success
          // Reload the page to show the updated task list
          setTimeout(() => { window.location.reload(); }, 1500);
      } else {
           // Error message is handled by sendServerActionRequest
           console.warn(`Task add/modify failed or reported non-success. Response:`, responseData);
           // Button is re-enabled automatically by the utility function on failure/error.
      }

}); // --- End form submit event listener ---

