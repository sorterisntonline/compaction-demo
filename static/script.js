// Dark mode toggle
document.addEventListener('DOMContentLoaded', function() {
    const body = document.body;
    const toggle = document.getElementById('dark-mode-toggle');
    
    // Load saved preference
    if (localStorage.getItem('darkMode') === 'true') {
        body.classList.add('dark-mode');
        if (toggle) toggle.checked = true;
    }
    
    // Toggle handler
    if (toggle) {
        toggle.addEventListener('change', function() {
            if (this.checked) {
                body.classList.add('dark-mode');
                localStorage.setItem('darkMode', 'true');
            } else {
                body.classList.remove('dark-mode');
                localStorage.setItem('darkMode', 'false');
            }
        });
    }
});

// Form submission state
document.querySelector('form')?.addEventListener('submit', function() {
    const btn = this.querySelector('button');
    btn.classList.add('sending');
    btn.textContent = 'sending...';
});

