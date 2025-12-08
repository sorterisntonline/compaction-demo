// Dark mode toggle handler
const toggle = document.getElementById('dark-mode-toggle');
if (toggle) {
    toggle.checked = localStorage.getItem('darkMode') === 'true';
    toggle.addEventListener('change', function() {
        document.documentElement.classList.toggle('dark-mode', this.checked);
        localStorage.setItem('darkMode', this.checked);
    });
}

// Form submission state
document.querySelector('form')?.addEventListener('submit', function() {
    const btn = this.querySelector('button');
    btn.classList.add('sending');
    btn.textContent = 'sending...';
});

