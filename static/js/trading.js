// Trading functionality

document.addEventListener('DOMContentLoaded', function() {
    // Initialize any trading related functionality that needs to run on page load
    
    // Stock search autocomplete
    setupStockSearchAutocomplete();
});

function setupStockSearchAutocomplete() {
    const searchInput = document.getElementById('stockSearch');
    if (!searchInput) return;
    
    let timeout = null;
    
    searchInput.addEventListener('input', function() {
        // Clear the previous timeout
        clearTimeout(timeout);
        
        // Set a timeout to avoid making too many requests
        timeout = setTimeout(() => {
            const query = this.value.trim();
            if (query.length < 2) return;
            
            performStockSearch(query);
        }, 500);
    });
}

function performStockSearch(query) {
    const searchResults = document.getElementById('searchResults');
    if (!searchResults) return;
    
    const resultsContainer = searchResults.querySelector('.list-group');
    
    // Add loading indicator
    resultsContainer.innerHTML = `
        <div class="list-group-item text-center">
            <div class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <span class="ms-2">Searching...</span>
        </div>
    `;
    searchResults.classList.remove('d-none');
    
    // Fetch search results
    fetch(`/api/search_stocks?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            resultsContainer.innerHTML = '';
            
            if (data.length === 0) {
                resultsContainer.innerHTML = `
                    <div class="list-group-item">
                        <div class="text-center text-muted">
                            <i class="fas fa-search me-2"></i>No results found
                        </div>
                    </div>
                `;
            } else {
                data.forEach(stock => {
                    const resultItem = document.createElement('a');
                    resultItem.href = `/trading?symbol=${stock.symbol}`;
                    resultItem.classList.add('list-group-item', 'list-group-item-action');
                    resultItem.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <strong>${stock.symbol}</strong>
                                <div class="small">${stock.name}</div>
                            </div>
                            <div class="badge bg-secondary">${stock.region}</div>
                        </div>
                    `;
                    resultsContainer.appendChild(resultItem);
                });
            }
        })
        .catch(error => {
            console.error('Error searching stocks:', error);
            resultsContainer.innerHTML = `
                <div class="list-group-item text-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>Error fetching results
                </div>
            `;
        });
}

// Execute a trade
function executeTrade(type, symbol, quantity) {
    // Show loading state
    const tradeButton = document.getElementById(`${type}Btn`);
    const originalButtonText = tradeButton.innerHTML;
    tradeButton.innerHTML = `
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        Processing...
    `;
    tradeButton.disabled = true;
    
    // Execute the trade via API
    fetch('/api/trade', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            symbol: symbol,
            quantity: parseInt(quantity),
            type: type
        }),
    })
    .then(response => response.json())
    .then(data => {
        // Reset button state
        tradeButton.innerHTML = originalButtonText;
        tradeButton.disabled = false;
        
        if (data.error) {
            // Show error notification
            showNotification('error', data.error);
            return;
        }
        
        // Show success notification
        showNotification('success', data.message);
        
        // Update UI
        updateUIAfterTrade(data);
    })
    .catch(error => {
        // Reset button state
        tradeButton.innerHTML = originalButtonText;
        tradeButton.disabled = false;
        
        console.error('Trade execution error:', error);
        showNotification('error', 'Failed to execute trade. Please try again.');
    });
}

function updateUIAfterTrade(data) {
    // Update wallet balance
    const walletBalanceElement = document.querySelector('.wallet-balance');
    if (walletBalanceElement) {
        walletBalanceElement.textContent = `$${parseFloat(data.wallet_balance).toFixed(2)}`;
    }
    
    // Update position information
    if (data.position) {
        // Update or add position information
        // This part would be implemented based on the actual UI structure
    }
    
    // Refresh any other relevant UI elements
    
    // Optionally reload the page after a short delay
    setTimeout(() => {
        window.location.reload();
    }, 2000);
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

// Update total cost
function updateTotalCost() {
    const quantity = document.getElementById('quantity').value;
    const totalCost = quantity * currentPrice;
    const walletSelect = document.getElementById('walletSelect');
    const selectedWallet = walletSelect.options[walletSelect.selectedIndex];
    const walletBalance = parseFloat(selectedWallet.textContent.match(/\$([\d.]+)/)[1]);
    const tradeType = document.getElementById('tradeType').value;
    const costHelp = document.getElementById('costHelp');
    const tradeButton = document.getElementById('tradeButton');
    
    document.getElementById('totalCost').textContent = `$${totalCost.toFixed(2)}`;
    
    if (tradeType === 'buy') {
        if (totalCost > walletBalance) {
            costHelp.textContent = `Insufficient funds. Required: $${totalCost.toFixed(2)}, Available: $${walletBalance.toFixed(2)}`;
            costHelp.className = 'form-text text-danger';
            tradeButton.disabled = true;
        } else {
            costHelp.textContent = `Available balance: $${walletBalance.toFixed(2)}`;
            costHelp.className = 'form-text text-success';
            tradeButton.disabled = false;
        }
    } else {
        costHelp.textContent = `Available balance: $${walletBalance.toFixed(2)}`;
        costHelp.className = 'form-text text-success';
        tradeButton.disabled = false;
    }
}
