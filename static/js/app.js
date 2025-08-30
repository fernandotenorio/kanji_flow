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

    // Live Preview for Add Deck Page ---
    const deckFileInput = document.getElementById('deck_file');
    const templateInput = document.getElementById('card_template');
    const cssInput = document.getElementById('card_css');
    const previewArea = document.getElementById('card-preview-area');
    const refreshPreviewBtn = document.getElementById('refreshPreviewBtn');
    
    if (deckFileInput && templateInput && cssInput && previewArea) {
        let previewCardData = null;

        // Function to handle the toggle logic for the preview card
        const setupPreviewCardInteractivity = () => {
            const previewToggleButton = previewArea.querySelector('#toggleBtn');
            const previewBackContent = previewArea.querySelector('#cardBack');
            
            if (previewToggleButton && previewBackContent) {
                // We use a direct listener here because we call this function
                // every time the preview is updated, ensuring the new button gets the listener.
                previewToggleButton.addEventListener('click', () => {
                    const isHidden = previewBackContent.style.display === 'none' || previewBackContent.style.display === '';
                    if (isHidden) {
                        previewBackContent.style.display = 'block';
                        previewToggleButton.textContent = 'Hide Answer';
                    } else {
                        previewBackContent.style.display = 'none';
                        previewToggleButton.textContent = 'Show Answer';
                    }
                });
            }
        };

        // Function to render the preview
        const updatePreview = () => {
            if (!previewCardData) return;

            const templateStr = templateInput.value;
            const cssStr = cssInput.value;

            let renderedHtml = templateStr.replace(/{{\s*card\.data\.(\w+)\s*}}/g, (match, key) => {
                return previewCardData[key] || `[${key} not found]`;
            });
            
            previewArea.innerHTML = `<style>${cssStr}</style>${renderedHtml}`;

            // Implement Cache Busting for the Live Preview ---
            // This ensures that media is always re-fetched from the server.
            const timestamp = Date.now(); // Get a unique value
            const mediaElements = previewArea.querySelectorAll('img, audio, source');

            mediaElements.forEach(el => {
                // Check if src exists and doesn't already have a query string
                if (el.src && el.src.indexOf('?') === -1) {
                    el.src = `${el.src}?t=${timestamp}`;
                }
            });
            // --- END OF CACHE BUSTING ---

            previewArea.classList.remove('card-preview-placeholder');

            // After updating the HTML, find the new button and add the listener
            setupPreviewCardInteractivity();
        };

         // Useful when the user changes media folder but template and css are already correct
        if (refreshPreviewBtn) {
            refreshPreviewBtn.addEventListener('click', updatePreview);
        }

        // 1. Listen for file selection
        deckFileInput.addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const content = JSON.parse(e.target.result);
                    if (Array.isArray(content) && content.length > 0) {
                        previewCardData = content[0];
                        updatePreview();
                    } else {
                        previewArea.innerHTML = '<p style="color: red;">Error: JSON must be an array of card objects.</p>';
                        previewCardData = null;
                    }
                } catch (error) {
                    previewArea.innerHTML = `<p style="color: red;">Error parsing JSON: ${error.message}</p>`;
                    previewCardData = null;
                }
            };
            reader.readAsText(file);
        });

        // 2. Listen for changes in the template and CSS textareas
        templateInput.addEventListener('input', updatePreview);
        cssInput.addEventListener('input', updatePreview);
    }

    // --- Logic for Custom Delete Confirmation Modal ---
    const deleteBtn = document.getElementById('deleteDeckBtn');
    const deleteModal = document.getElementById('deleteDeckModal');
    const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    const deleteDeckForm = document.getElementById('deleteDeckForm');
    const modalDeckName = document.getElementById('modalDeckName');

    // Only run this logic if we are on a page with the delete button
    if (deleteBtn && deleteModal && deleteDeckForm) {

        // Show the modal when the main delete button is clicked
        deleteBtn.addEventListener('click', function() {
            const deckName = this.getAttribute('data-deck-name');
            modalDeckName.textContent = `'${deckName}'`; // Update modal text
            deleteModal.classList.add('is-visible');
        });

        // Function to hide the modal
        const hideModal = () => {
            deleteModal.classList.remove('is-visible');
        };

        // Hide modal on cancel button click or overlay click
        cancelDeleteBtn.addEventListener('click', hideModal);
        deleteModal.addEventListener('click', function(event) {
            // Only close if the overlay itself is clicked, not the content
            if (event.target === deleteModal) {
                hideModal();
            }
        });

        // Handle the final confirmation
        confirmDeleteBtn.addEventListener('click', function() {
            // Submit the form to perform the deletion
            deleteDeckForm.submit();
        });
    }
});