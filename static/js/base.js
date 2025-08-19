/**
 * MindgenomeImage - Optimized Base JavaScript
 * Lightweight core functionality for maximum performance
 */

// ========================================
// Performance-Optimized Core
// ========================================

class MindgenomeImageApp {
    constructor() {
        this.isInitialized = false;
        this.init();
    }

    init() {
        if (this.isInitialized) return;
        
        // Only initialize essential features
        this.setupNavigation();
        this.setupFlashMessages();
        this.setupLoadingStates();
        this.setupFormEnhancements();
        
        this.isInitialized = true;
    }

    setupNavigation() {
        // Mobile navigation toggle
        const navToggle = document.querySelector('.nav-toggle');
        const navMenu = document.querySelector('#nav-menu');
        
        if (navToggle && navMenu) {
            navToggle.addEventListener('click', () => {
                navMenu.classList.toggle('is-open');
                navToggle.setAttribute('aria-expanded', 
                    navMenu.classList.contains('is-open').toString()
                );
            });
        }

        // User menu dropdown
        const userMenu = document.querySelector('.user-menu-toggle');
        const userDropdown = document.querySelector('.user-dropdown');
        
        if (userMenu && userDropdown) {
            userMenu.addEventListener('click', (e) => {
                e.stopPropagation();
                userDropdown.classList.toggle('is-open');
            });

            // Close on outside click
            document.addEventListener('click', () => {
                userDropdown.classList.remove('is-open');
            });
        }
    }

    setupFlashMessages() {
        const flashMessages = document.querySelectorAll('.flash-message');
        
        flashMessages.forEach(message => {
            // Auto-hide after 5 seconds
            setTimeout(() => {
                message.style.opacity = '0';
                setTimeout(() => message.remove(), 300);
            }, 5000);

            // Close button
            const closeBtn = message.querySelector('.flash-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => {
                    message.style.opacity = '0';
                    setTimeout(() => message.remove(), 300);
                });
            }
        });
    }

    setupLoadingStates() {
        // Show loading on form submission
        const forms = document.querySelectorAll('form[data-loading]');
        forms.forEach(form => {
            form.addEventListener('submit', () => {
                this.showLoading();
            });
        });

        // Hide loading on page load
        window.addEventListener('load', () => {
            this.hideLoading();
        });
    }

    showLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('is-visible');
        }
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('is-visible');
        }
    }

    // Enhanced form handling
    setupFormEnhancements() {
        // Password toggle functionality
        const passwordToggles = document.querySelectorAll('.password-toggle');
        passwordToggles.forEach(toggle => {
            toggle.addEventListener('click', (e) => {
                e.preventDefault();
                const input = toggle.parentElement.querySelector('input[type="password"], input[type="text"]');
                const icon = toggle.querySelector('.toggle-icon');
                
                if (input.type === 'password') {
                    input.type = 'text';
                    icon.textContent = '🙈';
                } else {
                    input.type = 'password';
                    icon.textContent = '👁️';
                }
            });
        });

        // Form validation enhancement
        const forms = document.querySelectorAll('form[data-validate]');
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                if (!this.validateForm(form)) {
                    e.preventDefault();
                }
            });
        });
    }

    validateForm(form) {
        let isValid = true;
        const requiredFields = form.querySelectorAll('[required]');
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                this.showFieldError(field, 'This field is required');
                isValid = false;
            } else {
                this.clearFieldError(field);
            }
        });

        return isValid;
    }

    showFieldError(field, message) {
        this.clearFieldError(field);
        field.classList.add('form-control--error');
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'form-error';
        errorDiv.textContent = message;
        field.parentNode.appendChild(errorDiv);
    }

    clearFieldError(field) {
        field.classList.remove('form-control--error');
        const errorDiv = field.parentNode.querySelector('.form-error');
        if (errorDiv) {
            errorDiv.remove();
        }
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('is-visible');
        }
    }
}

// ========================================
// Global API
// ========================================

window.MindgenomeImage = {
    app: null,
    
    init() {
        this.app = new MindgenomeImageApp();
        return this.app;
    },
    
    showLoading() {
        if (this.app) this.app.showLoading();
    },
    
    hideLoading() {
        if (this.app) this.app.hideLoading();
    }
};

// ========================================
// Auto-initialization
// ========================================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        MindgenomeImage.init();
    });
} else {
    MindgenomeImage.init();
}
