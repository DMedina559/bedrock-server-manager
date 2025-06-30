// bedrock_server_manager/web/static/js/auth.js
/**
 * @fileoverview Handles frontend authentication logic, specifically login.
 */

// Ensure utils.js is loaded, as we need sendServerActionRequest and showStatusMessage
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("CRITICAL ERROR: Missing required functions from utils.js. Ensure utils.js is loaded before auth.js.");
    // Optionally, display a more user-facing error if possible, though showStatusMessage itself might be missing.
    alert("A critical error occurred with page setup. Please try refreshing. If the problem persists, contact support.");
}

/**
 * Handles the login form submission.
 * Gathers credentials, calls the /api/login endpoint, and handles the response.
 * @param {HTMLButtonElement} buttonElement - The login button element.
 */
async function handleLoginAttempt(buttonElement) {
    const functionName = 'handleLoginAttempt';
    console.log(`${functionName}: Initiated.`);

    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const form = document.getElementById('login-form'); // Get the form itself

    if (!usernameInput || !passwordInput || !form) {
        console.error(`${functionName}: Login form elements (username, password, or form itself) not found.`);
        showStatusMessage("Internal page error: Login form elements missing.", "error");
        return;
    }

    const username = usernameInput.value.trim();
    const password = passwordInput.value; // Passwords should not be trimmed usually

    // Basic frontend validation (though backend will also validate)
    if (!username) {
        showStatusMessage("Username is required.", "warning");
        usernameInput.focus();
        return;
    }
    if (!password) {
        showStatusMessage("Password is required.", "warning");
        passwordInput.focus();
        return;
    }

    const requestBody = {
        username: username,
        password: password
    };

    console.debug(`${functionName}: Attempting login for user '${username}'.`);

    // Disable button during request
    if (buttonElement) buttonElement.disabled = true;
    showStatusMessage("Attempting login...", "info"); // Provide immediate feedback

    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    try {
        const response = await fetch('/auth/token', { // Updated URL
            method: 'POST',
            body: formData, // Send as form data
            headers: {
                'Accept': 'application/json', // We still want JSON response from this endpoint
            }
        });

        const responseData = await response.json();

        if (response.ok && responseData.access_token) { // FastAPI route returns access_token in body too
            console.log(`${functionName}: Login successful. Token received (server also sets HttpOnly cookie).`);

            // Store JWT in localStorage for other API calls that might use Bearer token via utils.js
            // The HttpOnly cookie will be used automatically by the browser for navigation.
            if (responseData.access_token) {
                localStorage.setItem('jwt_token', responseData.access_token);
            }

            showStatusMessage(responseData.message || "Login successful! Redirecting...", "success");

            const currentUrlParams = new URLSearchParams(window.location.search);
            const nextUrl = currentUrlParams.get('next');

            if (nextUrl) {
                console.log(`${functionName}: Redirecting to 'next' URL: ${nextUrl}`);
                setTimeout(() => { window.location.href = nextUrl; }, 500);
            } else {
                console.log(`${functionName}: Redirecting to dashboard ('/').`);
                setTimeout(() => { window.location.href = '/'; }, 500);
            }
        } else {
            // Handle errors (e.g., 401 Unauthorized, or other errors from the server)
            const errorMessage = responseData.detail || responseData.message || "Login failed. Please check your credentials.";
            console.error(`${functionName}: Login failed. Status: ${response.status}, Message: "${errorMessage}"`, responseData);
            showStatusMessage(errorMessage, "error");
            if (passwordInput) passwordInput.value = ''; // Clear password on failed attempt
            if (buttonElement) buttonElement.disabled = false; // Re-enable button
        }
    } catch (error) {
        // Network errors or other issues with fetch itself
        const errorMsg = `Network or processing error during login: ${error.message}`;
        console.error(`${functionName}: ${errorMsg}`, error);
        showStatusMessage(errorMsg, "error");
        if (passwordInput) passwordInput.value = '';
        if (buttonElement) buttonElement.disabled = false;
    }
}
