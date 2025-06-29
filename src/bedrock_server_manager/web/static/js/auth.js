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

    // Call sendServerActionRequest to POST to /api/login
    // serverName is null because /api/login is an absolute path
    const responseData = await sendServerActionRequest(null, '/api/login', 'POST', requestBody, buttonElement);

    if (responseData && responseData.access_token) {
        console.log(`${functionName}: Login successful. Token received.`);
        // For simplicity in this step, storing JWT in localStorage.
        // For production, HttpOnly cookies set by the server are generally preferred for web apps.
        localStorage.setItem('jwt_token', responseData.access_token);

        // Redirect to dashboard or 'next' URL
        // Check if 'next' query parameter exists in the current URL
        const currentUrlParams = new URLSearchParams(window.location.search);
        const nextUrl = currentUrlParams.get('next');

        // showStatusMessage is now handled by sendServerActionRequest based on API response
        // showStatusMessage("Login successful! Redirecting...", "success"); 

        if (nextUrl) {
            console.log(`${functionName}: Redirecting to 'next' URL: ${nextUrl}`);
            // Small delay to allow user to see the success message from sendServerActionRequest
            setTimeout(() => { window.location.href = nextUrl; }, 500);
        } else {
            console.log(`${functionName}: Redirecting to dashboard ('/').`);
            // Small delay to allow user to see the success message from sendServerActionRequest
            setTimeout(() => { window.location.href = '/'; }, 500);
        }
    } else {
        // Error message should have been shown by sendServerActionRequest
        // based on the API's JSON error response.
        console.error(`${functionName}: Login failed. Response:`, responseData);
        // Ensure password field is cleared on failed attempt for security/UX
        passwordInput.value = '';
    }
}
