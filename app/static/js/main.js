document.addEventListener('DOMContentLoaded', () => {
    // --- Code for fetching articles on the main page ---
    const fetchButton = document.getElementById('fetch-articles');
    const statusMessage = document.getElementById('status-message');

    if (fetchButton) {
        fetchButton.addEventListener('click', () => {
            statusMessage.textContent = 'Pobieranie...';
            statusMessage.className = 'status-message';
            statusMessage.style.display = 'block';
            fetchButton.disabled = true;

            fetch('/fetch_articles', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        statusMessage.textContent = `Błąd: ${data.error}`;
                        statusMessage.classList.add('error');
                        fetchButton.disabled = false;
                    } else {
                        statusMessage.textContent = data.message;
                        statusMessage.classList.add('success');
                        setTimeout(() => window.location.reload(), 1500);
                    }
                })
                .catch(error => {
                    statusMessage.textContent = `Błąd sieci: ${error}`;
                    statusMessage.classList.add('error');
                    fetchButton.disabled = false;
                });
        });
    }

    // --- Code for fetching and selecting images on the edit page ---
    const fetchImagesButton = document.getElementById('fetch-images');
    const imageSelectionContainer = document.getElementById('image-selection-container');
    const selectedImagesInput = document.getElementById('selected_images');

    if (fetchImagesButton) {
        // Function to update the hidden input based on selected images
        const updateSelectedImagesInput = () => {
            const selected = imageSelectionContainer.querySelectorAll('img.selected');
            const urls = Array.from(selected).map(img => img.src);
            selectedImagesInput.value = urls.join(',');
        };

        // Function to render images and attach handlers
        const renderImages = (imageUrls) => {
            imageSelectionContainer.innerHTML = '';
            const currentlySelected = new Set((selectedImagesInput.value || '').split(','));
            
            imageUrls.forEach(url => {
                const img = document.createElement('img');
                img.src = url;
                img.alt = 'Scraped image';
                if (currentlySelected.has(url)) {
                    img.classList.add('selected');
                }
                
                img.addEventListener('click', () => {
                    img.classList.toggle('selected');
                    updateSelectedImagesInput();
                });

                imageSelectionContainer.appendChild(img);
            });
        };
        
        // Initial render for already selected images
        if (selectedImagesInput.value) {
            renderImages(selectedImagesInput.value.split(','));
        }

        // Handler for the fetch button
        fetchImagesButton.addEventListener('click', () => {
            const articleId = fetchImagesButton.dataset.articleId;
            imageSelectionContainer.innerHTML = 'Pobieranie obrazków...';
            fetchImagesButton.disabled = true;

            fetch(`/fetch_images/${articleId}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        imageSelectionContainer.innerHTML = `<p class="error">${data.error}</p>`;
                    } else if (data.images && data.images.length > 0) {
                        renderImages(data.images);
                    } else {
                        imageSelectionContainer.innerHTML = 'Nie znaleziono żadnych obrazków.';
                    }
                })
                .catch(error => {
                    imageSelectionContainer.innerHTML = `<p class="error">Błąd sieci: ${error}</p>`;
                })
                .finally(() => {
                    fetchImagesButton.disabled = false;
                });
        });
    }
});

