document.addEventListener('DOMContentLoaded', function() {

    // --- Logic for the Study Page ---
    const toggleButton = document.getElementById('toggleMeaningBtn');
    const meaningDiv = document.getElementById('kanjiMeaning');

    // Only add the event listener if the button actually exists on the current page.
    if (toggleButton && meaningDiv) {
        toggleButton.addEventListener('click', function() {
            // Check the current display style
            const isHidden = meaningDiv.style.display === 'none' || meaningDiv.style.display === '';

            if (isHidden) {
                // If it's hidden, show it and change button text
                meaningDiv.style.display = 'block';
                toggleButton.textContent = 'Hide Meaning';
            } else {
                // If it's visible, hide it and change button text
                meaningDiv.style.display = 'none';
                toggleButton.textContent = 'Show Meaning';
            }
        });
    }


    // --- Logic for Active Sidebar Link ---
    const currentLocation = window.location.pathname;
    const navLinks = document.querySelectorAll('.sidebar nav ul li a');

    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentLocation) {
            link.classList.add('active');
        }
    });

});