// Portfolio management functionality

document.addEventListener('DOMContentLoaded', function() {
    // Initialize portfolio charts if on portfolio page
    if (document.querySelector('#holdingsChart')) {
        initializePortfolioCharts();
    }
});

function initializePortfolioCharts() {
    // Holdings distribution chart (already implemented in portfolio.html)
    
    // Additional charts could be added here
    
    // Portfolio performance chart (example)
    const performanceChartElement = document.getElementById('performanceChart');
    if (performanceChartElement) {
        createPerformanceChart(performanceChartElement);
    }
}

function createPerformanceChart(element) {
    // This would fetch historical portfolio data from the server
    // and create a performance chart
    
    // Example implementation:
    
    // Sample data - in a real app, this would come from the server
    const dates = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];
    const portfolioValues = [10000, 10400, 10200, 10800, 11200, 11600];
    const benchmarkValues = [10000, 10200, 10300, 10400, 10600, 10800];
    
    new Chart(element.getContext('2d'), {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Portfolio',
                    data: portfolioValues,
                    borderColor: '#4dc9f6',
                    backgroundColor: 'rgba(77, 201, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Benchmark (S&P 500)',
                    data: benchmarkValues,
                    borderColor: '#f67019',
                    backgroundColor: 'rgba(246, 112, 25, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
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
                            return `${label}: $${value.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    title: {
                        display: true,
                        text: 'Value ($)'
                    }
                }
            }
        }
    });
}
