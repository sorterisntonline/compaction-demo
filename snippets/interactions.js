// Script runs after textarea exists (inline after form)
const textarea = document.querySelector('textarea');
const storageKey = 'draft-' + window.location.pathname;

if (textarea) {
    // Restore on load
    const saved = localStorage.getItem(storageKey);
    if (saved) {
        textarea.value = saved;
    }
    
    // Save on change
    textarea.addEventListener('input', function() {
        localStorage.setItem(storageKey, this.value);
    });
}

// Form submission - hold button down, clear draft on success
document.querySelector('form')?.addEventListener('submit', function() {
    const btn = this.querySelector('button');
    btn.classList.add('sending');
    btn.textContent = '...';
    localStorage.removeItem(storageKey);
});

// Copy to clipboard
document.addEventListener('click', async e => {
    if (!e.target.classList.contains('copy-btn')) return;
    const container = e.target.parentElement;
    const text = container.innerText;
    await navigator.clipboard.writeText(text);
    e.target.textContent = '✓';
    setTimeout(() => e.target.textContent = '⧉', 1500);
});

