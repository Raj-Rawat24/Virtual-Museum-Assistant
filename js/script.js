document.addEventListener("DOMContentLoaded", () => {
    // Login Form Handling
    const loginForm = document.getElementById("loginForm");
    if (loginForm) {
        loginForm.addEventListener("submit", async function(e) {
            e.preventDefault();

            const username = document.getElementById("username")?.value.trim();
            const password = document.getElementById("password")?.value.trim();
            const submitButton = this.querySelector("button");
            const errorElement = this.querySelector(".error-message") || document.createElement("div");
            errorElement.className = "error-message";

            if (!username || !password) {
                showError("Please enter both username and password.", errorElement, submitButton);
                return;
            }

            // UI Feedback
            submitButton.disabled = true;
            const originalContent = submitButton.innerHTML;
            submitButton.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Logging in...`;

            try {
                const response = await fetch("/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: new URLSearchParams({ username, password })
                });

                if (response.redirected) {
                    submitButton.innerHTML = `<i class="fas fa-check-circle"></i> Success!`;
                    setTimeout(() => {
                        window.location.href = response.url;
                    }, 1000);
                } else {
                    const data = await response.json();
                    showError(data.message || "Login failed. Please try again.", errorElement, submitButton, originalContent);
                }
            } catch (error) {
                console.error("Login error:", error);
                showError("Network error. Please try again.", errorElement, submitButton, originalContent);
            }
        });
    }

    // Artifact Loading with Improved Error Handling
    if (window.location.pathname === "/museum") {
        loadArtifacts();
    }

    // Particle Background Animation
    if (!document.body.classList.contains('login-page') && 
        !document.body.classList.contains('signup-page') && 
        !document.body.classList.contains('payment-page') &&
        !document.body.classList.contains('error-page')) {
        createParticles();
    }
});

// Load Artifacts with Loading States
async function loadArtifacts() {
    const grid = document.getElementById("artifact-grid");
    const detailsDiv = document.getElementById("artifact-details");

    if (!grid) return;

    // Show loading state
    grid.innerHTML = `<div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i> Loading artifacts...</div>`;

    try {
        const response = await fetch("/api/artifacts");

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const artifacts = await response.json();

        // Clear loading state
        grid.innerHTML = "";

        if (!artifacts || artifacts.length === 0) {
            grid.innerHTML = `<div class="no-items">No artifacts found</div>`;
            return;
        }

        artifacts.forEach(item => {
            if (!item || !item.name || !item.image_path) {
                console.warn("Invalid artifact item:", item);
                return;
            }

            const artifactItem = document.createElement("div");
            artifactItem.className = "artifact-item";
            artifactItem.innerHTML = `
                <img src="${item.image_path}" alt="${item.name}" loading="lazy">
                <p>${item.name}</p>
            `;

            artifactItem.addEventListener("click", () => {
                showDetails({
                    name: item.name,
                    description: item.description || "No description available",
                    modelPath: item.model_path
                });

                // Highlight selected artifact
                document.querySelectorAll(".artifact-item").forEach(el => {
                    el.classList.remove("active");
                });
                artifactItem.classList.add("active");
            });

            grid.appendChild(artifactItem);
        });

    } catch (error) {
        console.error("Failed to load artifacts:", error);
        grid.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i>
                Failed to load artifacts. 
                <button onclick="loadArtifacts()">Retry</button>
            </div>
        `;
    }
}

// Show Artifact Details with Improved UI
function showDetails({ name, description, modelPath }) {
    const detailsDiv = document.getElementById("artifact-details");
    if (!detailsDiv) return;

    detailsDiv.style.display = "block";
    detailsDiv.innerHTML = `
        <div class="details-content">
            <h2>${escapeHtml(name)}</h2>
            <p>${escapeHtml(description)}</p>
            <button onclick="handleViewModel('${modelPath}', '${name}', '${description}')">
                <i class="fas fa-eye"></i> View 3D Model
            </button>
        </div>
    `;

    // Smooth scroll to details
    detailsDiv.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// Updated View Model Handler with Payment Verification
async function handleViewModel(modelPath, name, description) {
    if (!modelPath || !name) {
        console.error("Missing parameters for viewModel");
        showNotification("Error: Missing model information", "error");
        return;
    }

    try {
        // Check payment status first
        const response = await fetch("/check_payment", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ modelPath, name })
        });

        const data = await response.json();

        if (data.has_access) {
            // Directly open viewer if already paid
            window.location.href = `/viewer?model=${encodeURIComponent(modelPath)}&name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}`;
        } else {
            // Redirect to payment page if not paid
            window.location.href = `/payment?model=${encodeURIComponent(modelPath)}&name=${encodeURIComponent(name)}`;
        }
    } catch (error) {
        console.error("Error checking payment status:", error);
        showNotification("Error verifying payment status", "error");
    }
}

// Helper Functions
function showError(message, container, button, originalContent) {
    const errorElement = document.createElement("div");
    errorElement.className = "error-message";
    errorElement.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;

    if (!container.parentNode) {
        button.parentNode.insertBefore(errorElement, button.nextSibling);
    } else {
        container.replaceWith(errorElement);
    }

    if (button && originalContent) {
        button.disabled = false;
        button.innerHTML = originalContent;
    }

    setTimeout(() => {
        errorElement.style.opacity = "0";
        setTimeout(() => errorElement.remove(), 300);
    }, 5000);
}

function escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function showNotification(message, type = "success") {
    const notification = document.createElement("div");
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === "success" ? "check" : "exclamation"}-circle"></i>
        ${message}
    `;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.opacity = "0";
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Particle Background Animation
function createParticles() {
    const particlesContainer = document.createElement('div');
    particlesContainer.className = 'particles';
    document.body.insertBefore(particlesContainer, document.body.firstChild);

    const particleCount = window.innerWidth < 768 ? 30 : 100;

    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';

        // Random properties
        const size = Math.random() * 5 + 1;
        const posX = Math.random() * window.innerWidth;
        const posY = Math.random() * window.innerHeight;
        const delay = Math.random() * 5;
        const duration = Math.random() * 10 + 10;
        const opacity = Math.random() * 0.5 + 0.1;

        // Apply styles
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        particle.style.left = `${posX}px`;
        particle.style.top = `${posY}px`;
        particle.style.opacity = opacity;
        particle.style.animation = `float ${duration}s ease-in-out ${delay}s infinite`;

        particlesContainer.appendChild(particle);
    }
}
