// Chart configuration and initialization

function initializeStockChart(symbol) {
    // Get the range buttons
    const rangeButtons = document.querySelectorAll('[data-range]');
    let currentRange = '1h'; // Default range
    
    // Get the chart container
    const chartContainer = document.getElementById('stockChart');
    if (!chartContainer) return;
    
    // Create canvas for Chart.js
    const canvas = document.createElement('canvas');
    chartContainer.appendChild(canvas);
    
    // Create and initialize chart
    const ctx = canvas.getContext('2d');
    let stockChart = null;
    
    // Load chart data
    loadChartData(symbol, currentRange);
    
    // Add event listeners to range buttons
    rangeButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Update active button
            rangeButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            // Update chart with new range
            currentRange = this.getAttribute('data-range');
            loadChartData(symbol, currentRange);
        });
    });
    
    // Function to load chart data
    function loadChartData(symbol, range) {
        // Show loading state
        chartContainer.innerHTML = `
            <div class="d-flex justify-content-center align-items-center" style="height: 400px;">
                <div class="text-center">
                    <div class="spinner-border text-primary mb-3" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p>Loading chart data...</p>
                </div>
            </div>
        `;
        
        // Fetch chart data from API
        fetch(`/api/chart_data/${symbol}?range=${range}`)
            .then(response => response.json())
            .then(data => {
                // Prepare data for Chart.js
                const labels = data.map(item => item.date);
                const prices = data.map(item => item.close);
                const volumes = data.map(item => item.volume);
                
                // Remove loading indicator
                chartContainer.innerHTML = '';
                
                // Create new canvas
                const canvas = document.createElement('canvas');
                chartContainer.appendChild(canvas);
                const ctx = canvas.getContext('2d');
                
                // Create the chart
                stockChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: `${symbol} Price`,
                                data: prices,
                                borderColor: '#4dc9f6',
                                backgroundColor: 'rgba(77, 201, 246, 0.1)',
                                borderWidth: 2,
                                fill: true,
                                tension: 0.4,
                                yAxisID: 'y'
                            },
                            {
                                label: 'Volume',
                                data: volumes,
                                borderColor: '#f67019',
                                backgroundColor: 'rgba(246, 112, 25, 0.5)',
                                borderWidth: 1,
                                type: 'bar',
                                yAxisID: 'y1'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false,
                        },
                        plugins: {
                            legend: {
                                position: 'top',
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.dataset.label || '';
                                        const value = context.raw;
                                        
                                        if (label.includes('Price')) {
                                            return `${label}: $${value.toFixed(2)}`;
                                        } else if (label.includes('Volume')) {
                                            return `${label}: ${value.toLocaleString()}`;
                                        }
                                        return `${label}: ${value}`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: {
                                    display: false
                                }
                            },
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                                title: {
                                    display: true,
                                    text: 'Price ($)'
                                }
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                grid: {
                                    drawOnChartArea: false
                                },
                                title: {
                                    display: true,
                                    text: 'Volume'
                                }
                            }
                        }
                    }
                });
            })
            .catch(error => {
                console.error('Error loading chart data:', error);
                chartContainer.innerHTML = `
                    <div class="alert alert-danger text-center">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        Failed to load chart data
                    </div>
                `;
            });
    }
}
