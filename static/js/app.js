// static/js/app.js

// --- START CHANGES ---
/**
 * Finds a "Show Answer" button and its corresponding answer element within a given
 * container and attaches the toggle functionality.
 * This is designed to work on both the static study page and the dynamic preview area.
 * @param {HTMLElement} container The parent element to search within (e.g., document or a specific div).
 */
const initializeCardInteractivity = (container) => {
    const toggleBtn = container.querySelector('#toggleBtn');
    const cardBack = container.querySelector('#cardBack');

    if (toggleBtn && cardBack) {
        // Ensure the back is hidden initially when the card loads/reloads.
        cardBack.style.display = 'none';
        toggleBtn.textContent = 'Show Answer';

        toggleBtn.addEventListener('click', () => {
            const isHidden = cardBack.style.display === 'none';
            cardBack.style.display = isHidden ? 'block' : 'none';
            toggleBtn.textContent = isHidden ? 'Hide Answer' : 'Show Answer';
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    // This will initialize the card on any page that has one, like the /study page.
    initializeCardInteractivity(document);

    // --- Live Preview for Add/Edit Deck Page ---
    const previewArea = document.getElementById('card-preview-area');
    const refreshPreviewBtn = document.getElementById('refreshPreviewBtn');
    
    // This script should only run on pages that have a preview area
    if (!previewArea || !refreshPreviewBtn) {
        return;
    }

    const templateInput = document.getElementById('card_template');
    const cssInput = document.getElementById('card_css');
    const mediaFolderInput = document.getElementById('media_folder');
    
    // For "Add Deck" page
    const deckFileInput = document.getElementById('deck_file');
    // For "Edit Deck" page
    const sampleCardDataSource = document.getElementById('sampleCardData');
    
    let sampleCardData = null;

    // Logic to get sample data on the "Add Deck" page
    if (deckFileInput) {
        deckFileInput.addEventListener('change', () => {
            const file = deckFileInput.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    try {
                        const data = JSON.parse(e.target.result);
                        if (Array.isArray(data) && data.length > 0) {
                            sampleCardData = data[0];
                            previewArea.querySelector('p').textContent = 'Sample data loaded. Click refresh to see preview.';
                        } else {
                            sampleCardData = null;
                            previewArea.querySelector('p').textContent = 'Error: JSON file must be an array with at least one card object.';
                        }
                    } catch (error) {
                        sampleCardData = null;
                        console.error("Error parsing JSON file:", error);
                        previewArea.querySelector('p').textContent = 'Error: Could not parse JSON file.';
                    }
                };
                reader.readAsText(file);
            }
        });
    }

    // Logic to get sample data on the "Edit Deck" page
    if (sampleCardDataSource) {
        try {
            sampleCardData = JSON.parse(sampleCardDataSource.dataset.card);
        } catch (error) {
            console.error("Error parsing sample card data:", error);
            previewArea.querySelector('p').textContent = 'Error: Could not load sample card data.';
        }
    }
    
    const fetchPreview = async () => {
        if (!sampleCardData) {
            previewArea.innerHTML = '<p>Please select a valid deck file (for new decks) or ensure sample data is present (for existing decks).</p>';
            return;
        }

        previewArea.innerHTML = '<p>Loading preview...</p>';

        try {
            const response = await fetch('/preview_card', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    template: templateInput.value,
                    css: cssInput.value,
                    sample_data: sampleCardData,
                    media_folder: mediaFolderInput.value
                }),
            });

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            const previewHtml = await response.text();
            previewArea.innerHTML = previewHtml;
            previewArea.classList.remove('card-preview-placeholder');

            // Re-attach logic for any interactive elements in the preview using the new reusable function
            initializeCardInteractivity(previewArea);

        } catch (error) {
            console.error('Error fetching preview:', error);
            previewArea.innerHTML = `<p style="color: red;">Error loading preview. Check the browser console for details.</p>`;
            previewArea.classList.add('card-preview-placeholder');
        }
    };

    refreshPreviewBtn.addEventListener('click', fetchPreview);

    // Automatically trigger a preview on the edit page on load
    if (sampleCardDataSource) {
        fetchPreview();
    }
});
// --- END CHANGES ---


// --- Delete Deck Confirmation Modal ---
document.addEventListener('DOMContentLoaded', () => {
    const deleteDeckModal = document.getElementById('deleteDeckModal');
    const deleteDeckBtn = document.getElementById('deleteDeckBtn');
    const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    const deleteDeckForm = document.getElementById('deleteDeckForm');
    const modalDeckName = document.getElementById('modalDeckName');

    if (deleteDeckBtn && deleteDeckModal && cancelDeleteBtn && confirmDeleteBtn && deleteDeckForm) {
        deleteDeckBtn.addEventListener('click', (event) => {
            event.preventDefault(); // Prevent form submission
            const deckName = deleteDeckBtn.dataset.deckName;
            if (modalDeckName) {
                modalDeckName.textContent = deckName;
            }
            deleteDeckModal.classList.add('is-visible');
        });

        const closeModal = () => {
            deleteDeckModal.classList.remove('is-visible');
        };

        cancelDeleteBtn.addEventListener('click', closeModal);
        deleteDeckModal.addEventListener('click', (event) => {
            if (event.target === deleteDeckModal) {
                closeModal();
            }
        });

        confirmDeleteBtn.addEventListener('click', () => {
            deleteDeckForm.submit();
        });
    }
});