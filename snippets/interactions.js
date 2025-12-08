// Form submission state
document.querySelector('form')?.addEventListener('submit', function() {
    const btn = this.querySelector('button');
    btn.classList.add('sending');
    btn.textContent = 'sending...';
});

