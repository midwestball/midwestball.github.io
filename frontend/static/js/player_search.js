document.addEventListener("DOMContentLoaded", function() {
    const searchInput = document.getElementById("player-search");
    const suggestionsBox = document.getElementById("suggestions-box");
    const searchForm = document.getElementById("search-form");
    
    let selectedIndex = -1;
    let suggestions = [];
    
    // Debounce function to limit API calls
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    // Fetch suggestions from server
    const fetchSuggestions = debounce(async (query) => {
        if (query.length < 2) {
            suggestionsBox.style.display = "none";
            return;
        }
        
        try {
            const response = await fetch(`/player_suggestions?q=${encodeURIComponent(query)}`);
            suggestions = await response.json();
            
            if (suggestions.length > 0) {
                displaySuggestions(suggestions, query);
            } else {
                suggestionsBox.style.display = "none";
            }
        } catch (error) {
            console.error("Error fetching suggestions:", error);
        }
    }, 300); // 300ms debounce
    
    // Display suggestions in dropdown
    function displaySuggestions(suggestions, query) {
        suggestionsBox.innerHTML = "";
        
        suggestions.forEach((suggestion, index) => {
            const div = document.createElement("div");
            div.className = "suggestion-item";
            
            // Highlight matching text
            const regex = new RegExp(`(${escapeRegExp(query)})`, "gi");
            const highlightedText = suggestion.replace(
                regex,
                "<span class='highlight'>$1</span>"
            );
            
            div.innerHTML = highlightedText;
            
            div.addEventListener("click", () => {
                searchInput.value = suggestion;
                suggestionsBox.style.display = "none";
                searchForm.submit();
            });
            
            div.addEventListener("mouseover", () => {
                selectedIndex = index;
                highlightSuggestion();
            });
            
            suggestionsBox.appendChild(div);
        });
        
        suggestionsBox.style.display = "block";
    }
    
    // Helper function to escape special characters in regex
    function escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }
    
    // Highlight selected suggestion
    function highlightSuggestion() {
        const items = suggestionsBox.getElementsByClassName("suggestion-item");
        for (let i = 0; i < items.length; i++) {
            items[i].classList.remove("selected");
        }
        if (selectedIndex >= 0 && selectedIndex < items.length) {
            items[selectedIndex].classList.add("selected");
        }
    }
    
    // Input event listeners
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            fetchSuggestions(e.target.value);
        });
        
        // Focus event (show suggestions if input already has text)
        searchInput.addEventListener("focus", () => {
            if (searchInput.value.length >= 2) {
                fetchSuggestions(searchInput.value);
            }
            
            // Save original value
            searchInput.dataset.originalValue = searchInput.value;
        });
        
        // Keyboard navigation
        searchInput.addEventListener("keydown", (e) => {
            const items = suggestionsBox.getElementsByClassName("suggestion-item");
            
            switch(e.key) {
                case "ArrowDown":
                    e.preventDefault();
                    selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
                    highlightSuggestion();
                    if (items[selectedIndex]) {
                        searchInput.value = items[selectedIndex].textContent;
                    }
                    break;
                    
                case "ArrowUp":
                    e.preventDefault();
                    selectedIndex = Math.max(selectedIndex - 1, -1);
                    highlightSuggestion();
                    if (selectedIndex === -1) {
                        searchInput.value = searchInput.dataset.originalValue || "";
                    } else if (items[selectedIndex]) {
                        searchInput.value = items[selectedIndex].textContent;
                    }
                    break;
                    
                case "Enter":
                    if (selectedIndex >= 0 && items[selectedIndex]) {
                        e.preventDefault();
                        searchInput.value = items[selectedIndex].textContent;
                        suggestionsBox.style.display = "none";
                        searchForm.submit();
                    }
                    break;
                    
                case "Escape":
                    suggestionsBox.style.display = "none";
                    selectedIndex = -1;
                    break;
            }
        });
    }
    
    // Close suggestions when clicking outside
    document.addEventListener("click", (e) => {
        if (searchInput && suggestionsBox && 
            !searchInput.contains(e.target) && 
            !suggestionsBox.contains(e.target)) {
            suggestionsBox.style.display = "none";
        }
    });
});