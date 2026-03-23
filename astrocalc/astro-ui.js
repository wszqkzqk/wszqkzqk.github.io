export function initAstroApp(calculatorClass, label, color, formatTooltipFooter) {
    const ctx = document.getElementById('astroChart').getContext('2d');
    let chart;

    const inputs = ['lat', 'lon', 'tz', 'date-picker', 'refraction'].map(id => document.getElementById(id));
    document.getElementById('date-picker').valueAsDate = new Date();
    document.getElementById('tz').value = 0;

    const horizonPlugin = {
        id: 'horizonPlugin',
        beforeDraw: (chart) => {
            const { ctx, chartArea: { top, bottom, left, right }, scales: { y } } = chart;
            const zeroLine = y.getPixelForValue(0);
            
            // Night (Below Horizon)
            ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--night-bg');
            ctx.fillRect(left, zeroLine, right - left, bottom - zeroLine);
            
            // Day (Above Horizon)
            ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--day-bg');
            ctx.fillRect(left, top, right - left, zeroLine - top);
        }
    };

    function update() {
        const lat = parseFloat(document.getElementById('lat').value) || 0;
        const lon = parseFloat(document.getElementById('lon').value) || 0;
        const tz = parseFloat(document.getElementById('tz').value) || 0;
        const date = new Date(document.getElementById('date-picker').value);
        const refr = parseFloat(document.getElementById('refraction').value) || 0;

        const data = calculatorClass.generateData(lat, lon, tz, date, refr);
        renderChart(data);
    }

    function renderChart(data) {
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const textColor = isDark ? '#eeeeec' : '#2e3436';
        const gridColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)';

        if (chart) chart.destroy();

        chart = new Chart(ctx, {
            type: 'line',
            plugins: [horizonPlugin],
            data: {
                labels: data.labels,
                datasets: [{
                    label: label,
                    data: data.angles,
                    borderColor: (ctx) => {
                        const val = ctx.raw;
                        return val >= 0 ? color : '#888';
                    },
                    segment: {
                        borderColor: ctx => ctx.p0.parsed.y >= 0 && ctx.p1.parsed.y >= 0 ? color : '#555',
                        borderDash: ctx => ctx.p0.parsed.y < 0 || ctx.p1.parsed.y < 0 ? [5, 5] : undefined
                    },
                    borderWidth: 3,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: color,
                    fill: false,
                    tension: 0.2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        padding: 12,
                        bodyFont: { weight: 'bold' },
                        callbacks: {
                            label: (item) => `Elevation: ${item.raw.toFixed(2)}°`,
                            footer: (items) => {
                                const idx = items[0].dataIndex;
                                return formatTooltipFooter(data, idx);
                            }
                        }
                    }
                },
                scales: {
                    x: { 
                        grid: { color: gridColor },
                        ticks: { color: textColor, maxTicksLimit: 12 }
                    },
                    y: { 
                        grid: { color: gridColor },
                        ticks: { color: textColor },
                        min: -90, max: 90
                    }
                }
            }
        });
    }

    inputs.forEach(i => i.addEventListener('input', update));
    
    async function detectLocation() {
        const status = document.getElementById('geo-status');
        const btn = document.getElementById('btn-detect');
        const originalBtnText = btn.innerHTML;
        
        btn.disabled = true;
        btn.innerHTML = '⏳ Locating...';
        status.innerText = "Attempting to locate...";

        const getBrowserGeo = () => new Promise((res, rej) => {
            navigator.geolocation.getCurrentPosition(res, rej, { timeout: 5000 });
        });

        try {
            const pos = await getBrowserGeo();
            document.getElementById('lat').value = pos.coords.latitude.toFixed(4);
            document.getElementById('lon').value = pos.coords.longitude.toFixed(4);
            const tzOffset = -new Date().getTimezoneOffset() / 60;
            document.getElementById('tz').value = tzOffset;
            status.innerText = "Located via Browser GPS";
        } catch (err) {
            try {
                const resp = await fetch('https://ipapi.co/json/');
                const ipData = await resp.json();
                if (ipData.latitude) {
                    document.getElementById('lat').value = ipData.latitude.toFixed(2);
                    document.getElementById('lon').value = ipData.longitude.toFixed(2);
                    if (ipData.utc_offset) {
                        document.getElementById('tz').value = parseInt(ipData.utc_offset) / 100;
                    }
                    status.innerText = "Located via IP address";
                }
            } catch (ipErr) {
                status.innerText = "Detection failed. Please enter manually.";
            }
        } finally {
            btn.innerHTML = originalBtnText;
            btn.disabled = false;
            update();
        }
    }

    document.getElementById('btn-detect').onclick = detectLocation;

    update();
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', update);
}