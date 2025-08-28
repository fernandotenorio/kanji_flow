document.addEventListener('DOMContentLoaded', function() {

    // --- Logic for the Study Page Card Toggle ---
    // This is now generic to work with any card template that uses these IDs.
    const toggleButton = document.getElementById('toggleBtn');
    const backContent = document.getElementById('cardBack');

    if (toggleButton && backContent) {
        toggleButton.addEventListener('click', function() {
            const isHidden = backContent.style.display === 'none' || backContent.style.display === '';

            if (isHidden) {
                backContent.style.display = 'block';
                toggleButton.textContent = 'Hide Answer';
            } else {
                backContent.style.display = 'none';
                toggleButton.textContent = 'Show Answer';
            }
        });
    }


    // --- Logic for Active Sidebar Link ---
    const currentLocation = window.location.pathname;
    const navLinks = document.querySelectorAll('.sidebar nav ul li a');

    navLinks.forEach(link => {
        // Use startsWith to highlight parent sections like '/decks' when on '/add_deck'
        const linkPath = link.getAttribute('href');
        if (currentLocation === linkPath) {
            link.classList.add('active');
        }
    });
});