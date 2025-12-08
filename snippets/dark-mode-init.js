// Apply dark mode immediately to prevent flash (html element exists in head)
if (localStorage.getItem('darkMode') === 'true') {
    document.documentElement.classList.add('dark-mode');
}

