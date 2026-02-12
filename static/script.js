document.addEventListener("DOMContentLoaded", function() {
    const authContainer = document.getElementById("auth-container");
    const controlContainer = document.getElementById("control-container");
    const upButton = document.getElementById("up-button");
    const downButton = document.getElementById("down-button");
    const statusText = document.getElementById("status-text");
    const garageDoor = document.getElementById("svg-garage-door");

    let statusInterval;

    function hapticFeedback() {
        if (navigator.vibrate) {
            navigator.vibrate(50); // Vibrate for 50ms
        }
    }

    function handleApiRequest(endpoint) {
        hapticFeedback();
        garageDoor.classList.add('in_transition');
        statusText.textContent = 'Moving...';
        
        fetch(endpoint, { method: "POST" })
            .then(response => response.json())
            .then(data => {
                console.log(data);
                // Immediately poll for status after a command is sent
                updateStatus();
            })
            .catch(error => {
                console.error('Error:', error);
                statusText.textContent = 'Error';
            });
    }

    function updateStatus() {
        fetch("/api/door/status")
            .then(response => {
                if (response.status === 401 || response.redirected) {
                    showLogin();
                    return;
                }
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {
                if (data) {
                    showControls();
                    statusText.textContent = data.status.replace('_', ' ');
                    
                    // Remove all state classes
                    garageDoor.classList.remove('open', 'closed', 'in_transition');
                    // Add the current state class
                    if (data.status === 'up') {
                        garageDoor.classList.add('open');
                    } else if (data.status === 'down') {
                        garageDoor.classList.add('closed');
                    } else {
                        garageDoor.classList.add('in_transition');
                    }

                    upButton.disabled = (data.status === 'up' || data.status === 'in_transition');
                    downButton.disabled = (data.status === 'down' || data.status === 'in_transition');
                }
            })
            .catch(error => {
                console.error('Failed to fetch status:', error);
                statusText.textContent = 'Offline';
                if (statusInterval) clearInterval(statusInterval);
            });
    }

    function showLogin() {
        authContainer.style.display = "block";
        controlContainer.style.display = "none";
        if (statusInterval) clearInterval(statusInterval);
    }

    function showControls() {
        authContainer.style.display = "none";
        controlContainer.style.display = "block";
    }

    // Initial check to see if user is logged in
    fetch("/api/door/status")
        .then(response => {
            if (response.status === 401 || response.redirected) {
                showLogin();
            } else {
                showControls();
                updateStatus();
                statusInterval = setInterval(updateStatus, 3000); // Poll every 3 seconds
            }
        })
        .catch(() => showLogin());

    upButton.addEventListener("click", () => handleApiRequest("/api/door/up"));
    downButton.addEventListener("click", () => handleApiRequest("/api/door/down"));
});
