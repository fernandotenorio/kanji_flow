// static/js/modal.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Generic Modal Closer ---
    // Attaches closing logic to all modals on the page.
    document.querySelectorAll('.modal-overlay').forEach(modal => {
        modal.addEventListener('click', (event) => {
            // Close if the dark overlay background is clicked, or if an element 
            // with the class .js-modal-close is clicked (like a "Cancel" button).
            if (event.target === modal || event.target.closest('.js-modal-close')) {
                modal.classList.remove('is-visible');
            }
        });
    });

    // --- Edit Card Modal Logic ---
    const editCardModal = document.getElementById('editCardModal');
    if (editCardModal) {
        const editCardForm = document.getElementById('editCardForm');
        const cardDataTextarea = document.getElementById('cardDataTextarea');
        const messageEl = document.getElementById('editCardMessage');
        let currentCardId = null; // Store the ID of the card being edited

        // Find all "Edit" buttons and attach the event listener.
        document.querySelectorAll('.js-edit-trigger').forEach(button => {
            button.addEventListener('click', () => {
                currentCardId = button.dataset.cardId; // Store the card ID
                const cardData = JSON.parse(button.dataset.cardData);
                
                // Set the form's action URL to point to the correct card.
                editCardForm.action = `/card/${currentCardId}/edit`;
                
                // Populate the textarea with pretty-printed JSON for readability.
                cardDataTextarea.value = JSON.stringify(cardData, null, 2);
                
                // Clear any previous messages
                messageEl.textContent = '';
                messageEl.style.color = '';

                // Show the modal.
                editCardModal.classList.add('is-visible');
            });
        });

        // Handle the form submission asynchronously
        editCardForm.addEventListener('submit', async (event) => {
            event.preventDefault(); // Stop the browser from performing a full page reload

            messageEl.textContent = 'Saving...';
            messageEl.style.color = '#7f8c8d';

            try {
                const response = await fetch(editCardForm.action, {
                    method: 'POST',
                    body: new FormData(editCardForm)
                });

                const data = await response.json();

                if (response.ok) {
                    messageEl.textContent = data.message;
                    messageEl.style.color = '#27ae60'; // Green for success

                    // --- Update the UI on the main page ---
                    // Find the table row corresponding to the edited card
                    const tableRow = document.querySelector(`tr[data-card-id="${currentCardId}"]`);
                    if (tableRow) {
                        // Update the <pre> tag with the new, pretty-printed JSON data
                        const preElement = tableRow.querySelector('pre');
                        preElement.textContent = JSON.stringify(data.card_data, null, 2);

                        // Update the data-card-data attribute on the edit button itself
                        // so reopening the modal shows the latest saved data.
                        const editButton = tableRow.querySelector('.js-edit-trigger');
                        editButton.dataset.cardData = JSON.stringify(data.card_data);
                    }

                } else {
                    // Handle HTTP errors (e.g., 400, 500)
                    messageEl.textContent = data.message || 'An error occurred.';
                    messageEl.style.color = '#e74c3c'; // Red for error
                }

            } catch (error) {
                console.error("Fetch error:", error);
                messageEl.textContent = 'A network error occurred.';
                messageEl.style.color = '#e74c3c';
            }

            // Clear the message after a few seconds
            setTimeout(() => {
                messageEl.textContent = '';
            }, 4000);
        });
    }

    // --- Generic Delete Confirmation Modal Logic ---
    // This handles both Deck and Card deletion triggers.
    const deleteItemModal = document.getElementById('deleteItemModal');
    if (deleteItemModal) {
        const deleteItemForm = document.getElementById('deleteItemForm');
        const modalItemName = document.getElementById('modalItemName');
        const deleteMessageEl = document.getElementById('deleteItemMessage');
        let currentCardIdToDelete = null;

        // Find all delete trigger buttons on the page.
        document.querySelectorAll('.js-delete-trigger').forEach(button => {
            button.addEventListener('click', (event) => {
                event.preventDefault(); // Prevent any default button action.
                
                const itemName = button.dataset.itemName || 'this item';
                const formAction = button.dataset.formAction;
                currentCardIdToDelete = button.dataset.cardId; // Store card ID for card deletions

                // Set the item name in the modal text for clarity.
                if (modalItemName) {
                    modalItemName.textContent = itemName;
                }
                
                // Set the form's action URL to the correct delete endpoint.
                if (deleteItemForm) {
                    deleteItemForm.action = formAction;
                }

                // Clear any previous messages
                if (deleteMessageEl) {
                    deleteMessageEl.textContent = '';
                    deleteMessageEl.style.color = '';
                }

                // Show the modal.
                deleteItemModal.classList.add('is-visible');
            });
        });

        // Handle delete form submission asynchronously
        deleteItemForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            
            if (deleteMessageEl) {
                deleteMessageEl.textContent = 'Deleting...';
                deleteMessageEl.style.color = '#7f8c8d';
            }

            try {
                const response = await fetch(deleteItemForm.action, {
                    method: 'POST',
                    body: new FormData(deleteItemForm) // Send form data if needed by backend
                });

                if (response.ok) {
                    // --- If this was a card deletion, remove the row from the table ---
                    if (currentCardIdToDelete) {
                        const tableRow = document.querySelector(`tr[data-card-id="${currentCardIdToDelete}"]`);
                        if (tableRow) {
                            tableRow.remove();
                        }
                    } else {
                        // If it was another type of deletion (like a deck), redirect
                        window.location.href = "/decks";
                        return;
                    }
                    
                    // Close the modal on success
                    deleteItemModal.classList.remove('is-visible');

                } else {
                    const data = await response.json();
                    deleteMessageEl.textContent = data.message || 'Deletion failed.';
                    deleteMessageEl.style.color = '#e74c3c'; // Red for error
                }
            } catch (error) {
                console.error("Delete fetch error:", error);
                deleteMessageEl.textContent = 'A network error occurred.';
                deleteMessageEl.style.color = '#e74c3c';
            }
        });
    }
});