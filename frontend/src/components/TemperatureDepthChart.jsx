import React, { useEffect, useRef } from 'react';
import { Chart as ChartJS, registerables } from 'chart.js';

// Register all Chart.js controllers, elements, and scales
ChartJS.register(...registerables);

// Distinct oceanographic color palette for different dive cycles
const CYCLE_COLORS = [
  { border: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)' }, // Ocean Cyan
  { border: '#0ea5e9', bg: 'rgba(14, 165, 233, 0.15)' }, // Sky Blue
  { border: '#06b6d4', bg: 'rgba(6, 182, 212, 0.15)' },  // Deep Teal
  { border: '#3b82f6', bg: 'rgba(59, 130, 246, 0.15)' }, // Indigo Blue
];

export default function TemperatureDepthChart({ observations = [], platformId, cycleNumber }) {
  const canvasRef = useRef(null);
  const chartInstanceRef = useRef(null);

  // Group valid observations by cycle
  const validObs = observations.filter(
    (o) =>
      o &&
      o.temperature_c !== null &&
      o.temperature_c !== undefined &&
      o.pressure_dbar !== null &&
      o.pressure_dbar !== undefined &&
      !isNaN(o.temperature_c) &&
      !isNaN(o.pressure_dbar)
  );

  // Calculate scientific summary metrics
  const temperatures = validObs.map((o) => o.temperature_c);
  const pressures = validObs.map((o) => o.pressure_dbar);
  const minTemp = temperatures.length ? Math.min(...temperatures) : null;
  const maxTemp = temperatures.length ? Math.max(...temperatures) : null;
  const minDepth = pressures.length ? Math.min(...pressures) : null;
  const maxDepth = pressures.length ? Math.max(...pressures) : null;

  // Find surface and deep temperatures
  const surfaceObs = validObs.length
    ? [...validObs].sort((a, b) => a.pressure_dbar - b.pressure_dbar)[0]
    : null;
  const deepObs = validObs.length
    ? [...validObs].sort((a, b) => b.pressure_dbar - a.pressure_dbar)[0]
    : null;

  useEffect(() => {
    if (!canvasRef.current || validObs.length === 0) return;

    // Destroy existing chart instance if present
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
        const color = CYCLE_COLORS[idx % CYCLE_COLORS.length];
        const sortedLevels = cycleGroups[c].sort((a, b) => a.pressure_dbar - b.pressure_dbar);

        return {
          label: `Float ${platformId || ''} Cycle #${c}`,
          data: sortedLevels.map((o) => ({
            x: o.temperature_c,
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
          spanGaps: false, // Ensure missing/null values are handled safely
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
            reverse: true, // INVERTED: 0 dbar at surface, deep measurements at bottom!
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
              text: 'In-Situ Temperature (°C)',
              color: '#38bdf8',
              font: { size: 12, weight: '600', family: 'Inter, sans-serif' },
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.07)',
            },
            ticks: {
              color: '#94a3b8',
              font: { size: 11, family: 'monospace' },
              callback: (val) => `${val.toFixed(1)}°C`,
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
            titleColor: '#38bdf8',
            bodyColor: '#f1f5f9',
            borderColor: 'rgba(56, 189, 248, 0.3)',
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
                const temp = context.parsed.x;
                return ` ${context.dataset.label}: ${temp.toFixed(2)} °C`;
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
        <p>No valid temperature observations available to chart.</p>
      </div>
    );
  }

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title-block">
          <h4 className="chart-title">
            <span className="chart-badge temp-badge">Temperature Profile</span> Temperature vs Depth
          </h4>
          <span className="chart-subtitle">
            Vertical in-situ seawater temperature variation across measured pressure levels (Inverted Depth Axis)
          </span>
        </div>

        {/* Scientific Metric Badges */}
        <div className="chart-metrics-row">
          {surfaceObs && (
            <div className="chart-metric-chip" title="Near-surface sampled temperature">
              <span className="metric-tag">Surface ({surfaceObs.pressure_dbar?.toFixed(1)} dbar):</span>
              <strong className="text-temp">{surfaceObs.temperature_c?.toFixed(2)} °C</strong>
            </div>
          )}
          {deepObs && (
            <div className="chart-metric-chip" title="Deepest ocean sampled temperature">
              <span className="metric-tag">Deep ({deepObs.pressure_dbar?.toFixed(0)} dbar):</span>
              <strong className="text-temp">{deepObs.temperature_c?.toFixed(2)} °C</strong>
            </div>
          )}
          {minTemp !== null && maxTemp !== null && (
            <div className="chart-metric-chip" title="Temperature range across profile">
              <span className="metric-tag">Range:</span>
              <span>{minTemp.toFixed(2)}°C &rarr; {maxTemp.toFixed(2)}°C</span>
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
