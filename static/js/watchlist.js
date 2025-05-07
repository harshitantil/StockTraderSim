// Watchlist management functionality

document.addEventListener('DOMContentLoaded', function() {
    // Set up watchlist button handlers if they exist
    setupWatchlistButtons();
});

function setupWatchlistButtons() {
    // Add to watchlist button
    const watchlistBtn = document.getElementById('watchlistBtn');
    if (watchlistBtn) {
        watchlistBtn.addEventListener('click', function() {
            const symbol = new URLSearchParams(window.location.search).get('symbol');
            if (!symbol) return;
            
            const isAddOperation = !this.classList.contains('btn-warning');
            toggleWatchlistItem(symbol, isAddOperation);
        });
    }
    
    // Remove from watchlist buttons (in watchlist section)
    const removeButtons = document.querySelectorAll('.remove-from-watchlist');
    removeButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const symbol = this.getAttribute('data-symbol');
            if (!symbol) return;
            
            toggleWatchlistItem(symbol, false);
        });
    });
}

function toggleWatchlistItem(symbol, isAdd) {
    const endpoint = isAdd ? '/api/watchlist/add' : '/api/watchlist/remove';
    const watchlistBtn = document.getElementById('watchlistBtn');
    
    // Show loading state
    if (watchlistBtn) {
        const originalText = watchlistBtn.innerHTML;
        watchlistBtn.innerHTML = `
            <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
            ${isAdd ? 'Adding...' : 'Removing...'}
        `;
        watchlistBtn.disabled = true;
    }
    
    // Make API request
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ symbol: symbol }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update button state
            if (watchlistBtn) {
                if (isAdd) {
                    watchlistBtn.classList.remove('btn-outline-warning');
                    watchlistBtn.classList.add('btn-warning');
                    watchlistBtn.innerHTML = '<i class="fas fa-star"></i> Remove from Watchlist';
                } else {
                    watchlistBtn.classList.remove('btn-warning');
                    watchlistBtn.classList.add('btn-outline-warning');
                    watchlistBtn.innerHTML = '<i class="far fa-star"></i> Add to Watchlist';
                }
                watchlistBtn.disabled = false;
            }
            
            // Show notification
            showNotification('success', data.message);
            
            // If in watchlist view, potentially remove the item
            const watchlistItem = document.querySelector(`.watchlist-item[data-symbol="${symbol}"]`);
            if (!isAdd && watchlistItem) {
                watchlistItem.classList.add('fade-out');
                setTimeout(() => {
                    watchlistItem.remove();
                    // Check if watchlist is now empty
                    const remainingItems = document.querySelectorAll('.watchlist-item');
                    if (remainingItems.length === 0) {
                        const watchlistContainer = document.querySelector('.watchlist-container');
                        if (watchlistContainer) {
                            watchlistContainer.innerHTML = `
                                <div class="text-center py-4">
                                    <i class="fas fa-star fa-3x mb-3 text-muted"></i>
                                    <p class="mb-0">Your watchlist is empty.</p>
                                    <p class="small text-muted">Add stocks to track them here.</p>
                                </div>
                            `;
                        }
                    }
                }, 300);
            }
        } else {
            // Show error notification
            showNotification('error', data.error || 'Failed to update watchlist');
            
            // Reset button state
            if (watchlistBtn) {
                if (isAdd) {
                    watchlistBtn.innerHTML = '<i class="far fa-star"></i> Add to Watchlist';
                } else {
                    watchlistBtn.innerHTML = '<i class="fas fa-star"></i> Remove from Watchlist';
                }
                watchlistBtn.disabled = false;
            }
        }
    })
    .catch(error => {
        console.error('Watchlist error:', error);
        showNotification('error', 'Failed to update watchlist');
        
        // Reset button state
        if (watchlistBtn) {
            if (isAdd) {
                watchlistBtn.innerHTML = '<i class="far fa-star"></i> Add to Watchlist';
            } else {
                watchlistBtn.innerHTML = '<i class="fas fa-star"></i> Remove from Watchlist';
            }
            watchlistBtn.disabled = false;
        }
    });
}

function showNotification(type, message) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show position-fixed`;
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.maxWidth = '400px';
    
    notification.innerHTML = `
        <div>${message}</div>
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Add to document
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 500);
    }, 5000);
}
