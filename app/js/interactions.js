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
    btn.disabled = true;
    localStorage.removeItem(storageKey);
});

// Lazy-load event bodies: on first open, POST the hidden expand-form to /do;
// event_body() returns the body HTML fragment which we append to <details>.
document.addEventListener('toggle', async e => {
    const d = e.target;
    if (!d.matches('details.event') || !d.open || d.dataset.expanded) return;
    const form = d.querySelector('form.expand-form');
    if (!form) return;
    d.dataset.expanded = '1';
    try {
        const r = await fetch('/do', {
            method: 'POST',
            body: new URLSearchParams(new FormData(form)),
        });
        if (r.ok && r.status !== 204) {
            const body = await r.text();
            if (body.trim()) {
                form.remove();
                d.insertAdjacentHTML('beforeend', body);
            }
        }
    } catch (_) {}
}, true); // capture phase — toggle doesn't bubble

// Copy to clipboard
document.addEventListener('click', async e => {
    if (!e.target.classList.contains('copy-btn')) return;
    const container = e.target.parentElement;
    const text = container.innerText;
    await navigator.clipboard.writeText(text);
    e.target.textContent = '✓';
    setTimeout(() => e.target.textContent = '⧉', 1500);
});

