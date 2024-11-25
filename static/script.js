// Add this helper function at the top level
function cleanWord(word) {
    return word.replace(/[.,!?;:"'()]/g, '').trim();
}

async function translateWord(word) {
    try {
        const response = await fetch(`/api/translate/de-en/${word}`);
        const data = await response.json();
        
        if (data.success) {
            console.log(`Translations for ${word}:`, data.translations);
            return data.translations;
        } else {
            console.error(`Error translating ${word}:`, data.error);
            return [];
        }
    } catch (error) {
        console.error(`Error translating ${word}:`, error);
        return [];
    }
}

// Add at the top of your script
let translationTimer = null;
let lastWord = null;

document.addEventListener('DOMContentLoaded', function() {
    // File upload handling
    const uploadForm = document.getElementById('uploadForm');
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('fileInput');
        const file = fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        // Reload page to update text list
        window.location.reload();
    });

    // URL form handling
    const urlForm = document.getElementById('urlForm');
    urlForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const urlInput = document.getElementById('urlInput');
        const url = urlInput.value.trim();
        if (!url) return;

        try {
            const formData = new FormData();
            formData.append('url', url);

            const response = await fetch('/load-url', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Failed to load URL');
            }

            const data = await response.json();
            
            // Display the text content
            const words = data.content.split(/(\s+)/);
            const textContent = document.getElementById('textContent');
            textContent.innerHTML = words.map(word => 
                word.trim() ? `<span class="word">${word}</span>` : word
            ).join('');

            // Clear the input
            urlInput.value = '';
        } catch (error) {
            alert('Error loading URL: ' + error.message);
        }
    });

    // Text selection handling
    document.addEventListener('click', async (e) => {
        if (e.target.classList.contains('text-link')) {
            e.preventDefault();
            const filename = e.target.dataset.filename;
            const response = await fetch(`/text/${filename}`);
            const data = await response.json();
            
            // Split text into words and wrap in spans
            const words = data.content.split(/(\s+)/);
            const textContent = document.getElementById('textContent');
            textContent.innerHTML = words.map(word => 
                word.trim() ? `<span class="word">${word}</span>` : word
            ).join('');
        }

        if (e.target.classList.contains('word')) {
            const word = cleanWord(e.target.textContent);
            if (word) {
                const formData = new FormData();
                formData.append('word', word);
                
                await fetch('/vocab', {
                    method: 'POST',
                    body: formData
                });
                
                updateVocabList();
            }
        }
    });

    // Initialize vocabulary list
    updateVocabList();

    // Add mouseover handler for words
    document.addEventListener('mouseover', (e) => {
        if (e.target.classList.contains('word')) {
            const word = cleanWord(e.target.textContent);
            
            // Don't fetch again if it's the same word
            if (word === lastWord) return;
            lastWord = word;
            
            // Clear any pending translation request
            if (translationTimer) clearTimeout(translationTimer);
            
            const translationContent = document.getElementById('translationContent');
            translationContent.innerHTML = 'Loading...';
            
            // Wait 300ms before fetching translation
            translationTimer = setTimeout(async () => {
                const translations = await translateWord(word);
                
                // Check if this is still the current word
                if (word === lastWord) {
                    if (translations && translations.length > 0) {
                        translationContent.innerHTML = `
                            <div class="translation-item">
                                <strong>${word}</strong>
                                <ul>
                                    ${translations.map(t => `<li>${t}</li>`).join('')}
                                </ul>
                            </div>
                        `;
                    } else {
                        translationContent.innerHTML = `
                            <div class="translation-item">
                                <strong>${word}</strong>
                                <p>No translation found</p>
                            </div>
                        `;
                    }
                }
            }, 50); // 300ms delay
        }
    });

    // Modify mouseout handler
    document.addEventListener('mouseout', (e) => {
        if (e.target.classList.contains('word')) {
            // Clear the timer and last word
            if (translationTimer) clearTimeout(translationTimer);
            lastWord = null;
            
            const translationContent = document.getElementById('translationContent');
            translationContent.innerHTML = '<p>Hover over a word to see translations</p>';
        }
    });
});

async function updateVocabList() {
    const response = await fetch('/vocab');
    const data = await response.json();
    const vocabList = document.getElementById('vocabList');
    vocabList.innerHTML = data.vocab.map(word => 
        `<li>
            ${word}
            <span class="delete-vocab" title="Delete word">&times;</span>
         </li>`
    ).join('');

    // Add click handlers for delete buttons
    document.querySelectorAll('.delete-vocab').forEach(btn => {
        btn.onclick = async (e) => {
            e.stopPropagation();
            const word = e.target.parentElement.firstChild.textContent.trim();
            if (confirm(`Delete "${word}" from vocabulary?`)) {
                await fetch(`/vocab/${encodeURIComponent(word)}`, {
                    method: 'DELETE'
                });
                updateVocabList();
            }
        };
    });
}