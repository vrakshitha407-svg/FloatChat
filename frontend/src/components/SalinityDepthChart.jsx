import React, { useEffect, useRef } from 'react';
import { Chart as ChartJS, registerables } from 'chart.js';

// Register all Chart.js controllers, elements, and scales
ChartJS.register(...registerables);
const SALINITY_CYCLE_COLORS = [
  { border: '#10b981', bg: 'rgba(16, 185, 129, 0.15)' }, // Emerald Green
  { border: '#14b8a6', bg: 'rgba(20, 184, 166, 0.15)' }, // Teal
  { border: '#2dd4bf', bg: 'rgba(45, 212, 191, 0.15)' }, // Light Aquamarine
  { border: '#34d399', bg: 'rgba(52, 211, 153, 0.15)' }, // Mint
];

export default function SalinityDepthChart({ observations = [], platformId, cycleNumber }) {
  const canvasRef = useRef(null);
  const chartInstanceRef = useRef(null);

  // Filter valid salinity and pressure records
  const validObs = observations.filter(
    (o) =>
      o &&
      o.salinity_psu !== null &&
      o.salinity_psu !== undefined &&
      o.pressure_dbar !== null &&
      o.pressure_dbar !== undefined &&
      !isNaN(o.salinity_psu) &&
      !isNaN(o.pressure_dbar)
  );

  // Compute scientific metrics
  const salinities = validObs.map((o) => o.salinity_psu);
  const pressures = validObs.map((o) => o.pressure_dbar);
  const minPsal = salinities.length ? Math.min(...salinities) : null;
  const maxPsal = salinities.length ? Math.max(...salinities) : null;
  const maxDepth = pressures.length ? Math.max(...pressures) : null;

  const surfaceObs = validObs.length
    ? [...validObs].sort((a, b) => a.pressure_dbar - b.pressure_dbar)[0]
    : null;
  const deepObs = validObs.length
    ? [...validObs].sort((a, b) => b.pressure_dbar - a.pressure_dbar)[0]
    : null;

  useEffect(() => {
    if (!canvasRef.current || validObs.length === 0) return;

    if (chartInstanceRef.current) {
      chartInstanceRef.current.destroy();
    }

    // Group observations by cycle_number
    const cycleGroups = {};
    validObs.forEach((o) => {
      const c = o.cycle_number !== null && o.cycle_number !== undefined ? o.cycle_number : 1;
      if (!cycleGroups[c]) cycleGroups[c] = [];
      cycleGroups[c].push(o);
    });

    const datasets = Object.keys(cycleGroups)
      .sort((a, b) => Number(a) - Number(b))
      .map((c, idx) => {
        const color = SALINITY_CYCLE_COLORS[idx % SALINITY_CYCLE_COLORS.length];
        const sortedLevels = cycleGroups[c].sort((a, b) => a.pressure_dbar - b.pressure_dbar);

        return {
          label: `Float ${platformId || ''} Cycle #${c}`,
          data: sortedLevels.map((o) => ({
            x: o.salinity_psu,
            y: o.pressure_dbar,
          })),
          borderColor: color.border,
          backgroundColor: color.bg,
          borderWidth: 2.2,
          pointRadius: sortedLevels.length > 50 ? 2 : 3.5,
          pointHoverRadius: 6,
          pointBackgroundColor: color.border,
          pointBorderColor: '#0f172a',
          pointBorderWidth: 1.5,
          showLine: true,
          tension: 0.25,
          spanGaps: false,
        };
      });

    const ctx = canvasRef.current.getContext('2d');
    chartInstanceRef.current = new ChartJS(ctx, {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 750,
          easing: 'easeOutQuart',
        },
        interaction: {
          mode: 'nearest',
          axis: 'y',
          intersect: false,
        },
        scales: {
          y: {
            type: 'linear',
            reverse: true, // Inverted vertical axis: 0 dbar at surface, deeper measurements lower
            title: {
              display: true,
              text: 'Pressure / Depth (dbar)',
              color: '#94a3b8',
              font: { size: 12, weight: '600', family: 'Inter, sans-serif' },
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.07)',
            },
            ticks: {
              color: '#94a3b8',
              font: { size: 11, family: 'monospace' },
              callback: (val) => `${val} dbar`,
            },
          },
          x: {
            type: 'linear',
            title: {
              display: true,
              text: 'Practical Salinity (PSU)',
              color: '#10b981',
              font: { size: 12, weight: '600', family: 'Inter, sans-serif' },
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.07)',
            },
            ticks: {
              color: '#94a3b8',
              font: { size: 11, family: 'monospace' },
              callback: (val) => `${val.toFixed(2)} PSU`,
            },
          },
        },
        plugins: {
          legend: {
            display: datasets.length > 1,
            position: 'top',
            labels: {
              color: '#cbd5e1',
              font: { size: 11, weight: '500' },
              boxWidth: 14,
              boxHeight: 14,
              usePointStyle: true,
            },
          },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.92)',
            titleColor: '#10b981',
            bodyColor: '#f1f5f9',
            borderColor: 'rgba(16, 185, 129, 0.3)',
            borderWidth: 1,
            padding: 10,
            cornerRadius: 8,
            titleFont: { size: 12, weight: '600' },
            bodyFont: { size: 12 },
            callbacks: {
              title: (items) => {
                if (!items.length) return '';
                const y = items[0].parsed.y;
                return `Depth / Pressure: ${y.toFixed(1)} dbar`;
              },
              label: (context) => {
                const psal = context.parsed.x;
                return ` ${context.dataset.label}: ${psal.toFixed(2)} PSU`;
              },
            },
          },
        },
      },
    });

    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
        chartInstanceRef.current = null;
      }
    };
  }, [validObs.length, platformId, cycleNumber]);

  if (validObs.length === 0) {
    return (
      <div className="viz-empty-state">
        <p>No valid salinity observations available to chart.</p>
      </div>
    );
  }

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title-block">
          <h4 className="chart-title">
            <span className="chart-badge psal-badge">Salinity Profile</span> Salinity vs Depth
          </h4>
          <span className="chart-subtitle">
            Vertical practical salinity structure (PSU) across measured pressure levels (Inverted Depth Axis)
          </span>
        </div>

        {/* Scientific Metric Badges */}
        <div className="chart-metrics-row">
          {surfaceObs && (
            <div className="chart-metric-chip" title="Near-surface salinity">
              <span className="metric-tag">Surface ({surfaceObs.pressure_dbar?.toFixed(1)} dbar):</span>
              <strong className="text-psal">{surfaceObs.salinity_psu?.toFixed(2)} PSU</strong>
            </div>
          )}
          {deepObs && (
            <div className="chart-metric-chip" title="Deep ocean salinity">
              <span className="metric-tag">Deep ({deepObs.pressure_dbar?.toFixed(0)} dbar):</span>
              <strong className="text-psal">{deepObs.salinity_psu?.toFixed(2)} PSU</strong>
            </div>
          )}
          {minPsal !== null && maxPsal !== null && (
            <div className="chart-metric-chip" title="Salinity variation range">
              <span className="metric-tag">Range:</span>
              <span>{minPsal.toFixed(2)} &rarr; {maxPsal.toFixed(2)} PSU</span>
            </div>
          )}
        </div>
      </div>

      <div className="chart-canvas-wrapper">
        <canvas ref={canvasRef} />
      </div>

      <div className="chart-footer">
        <span className="chart-note">
          Vertical axis is inverted per oceanographic standard (0 dbar at surface down to {maxDepth?.toFixed(0)} dbar).
        </span>
        <span className="chart-records-tag">
          {validObs.length} Discrete Depth Level{validObs.length !== 1 ? 's' : ''}
        </span>
      </div>
    </div>
  );
}
