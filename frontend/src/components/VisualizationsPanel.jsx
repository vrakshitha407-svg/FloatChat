import React, { useState } from 'react';
import TemperatureDepthChart from './TemperatureDepthChart';
import SalinityDepthChart from './SalinityDepthChart';
import ArgoProfileMap from './ArgoProfileMap';

export default function VisualizationsPanel({ message }) {
  if (!message || message.isError || message.isWelcome) return null;

  const { intent, data, parameters, data_count } = message;

  // Extract observations and profiles if present
  const observations = data?.observations || [];
  const profiles = data?.profiles || [];
  const platformId = parameters?.platform_id || '1900121';
  const cycleNumber = parameters?.cycle_number;

  const hasObservations = observations.length > 0;
  const hasProfiles = profiles.length > 0;

  // If no data or out of domain, do not render scientific charts
  if (!hasObservations && !hasProfiles) {
    if (intent === 'out_of_domain') {
      return null;
    }
    if (data_count === 0) {
      return (
        <div className="viz-panel-empty">
          <span className="empty-icon">&#9432;</span>
          <span>No observation levels or profiles matched the criteria to visualize.</span>
        </div>
      );
    }
    return null;
  }

  // Determine initial active tab based on query intent
  const defaultTab = hasObservations ? 'temp' : 'map';
  const [activeTab, setActiveTab] = useState(defaultTab);

  return (
    <div className="visualizations-panel">
      {/* Visualisation Mode Tabs */}
      <div className="viz-tabs-bar">
        <div className="viz-tabs-group">
          {hasObservations && (
            <>
              <button
                onClick={() => setActiveTab('temp')}
                className={`viz-tab-btn ${activeTab === 'temp' ? 'active temp' : ''}`}
              >
                <span className="tab-icon">🌡</span>
                <span>Temperature vs Depth</span>
              </button>
              <button
                onClick={() => setActiveTab('psal')}
                className={`viz-tab-btn ${activeTab === 'psal' ? 'active psal' : ''}`}
              >
                <span className="tab-icon">🧂</span>
                <span>Salinity vs Depth</span>
              </button>
              <button
                onClick={() => setActiveTab('side-by-side')}
                className={`viz-tab-btn ${activeTab === 'side-by-side' ? 'active combo' : ''}`}
              >
                <span className="tab-icon">📊</span>
                <span>Side-by-Side Profiles</span>
              </button>
            </>
          )}

          {(hasProfiles || (hasObservations && observations[0]?.latitude !== undefined)) && (
            <button
              onClick={() => setActiveTab('map')}
              className={`viz-tab-btn ${activeTab === 'map' ? 'active map' : ''}`}
            >
              <span className="tab-icon">🗺</span>
              <span>Profile Location Map</span>
            </button>
          )}
        </div>

        <div className="viz-meta-indicator">
          <span className="viz-source-tag">Live ARGO Engine Data</span>
        </div>
      </div>

      {/* Visualisation Viewport */}
      <div className="viz-viewport">
        {activeTab === 'temp' && hasObservations && (
          <TemperatureDepthChart
            observations={observations}
            platformId={platformId}
            cycleNumber={cycleNumber}
          />
        )}

        {activeTab === 'psal' && hasObservations && (
          <SalinityDepthChart
            observations={observations}
            platformId={platformId}
            cycleNumber={cycleNumber}
          />
        )}

        {activeTab === 'side-by-side' && hasObservations && (
          <div className="side-by-side-grid">
            <TemperatureDepthChart
              observations={observations}
              platformId={platformId}
              cycleNumber={cycleNumber}
            />
            <SalinityDepthChart
              observations={observations}
              platformId={platformId}
              cycleNumber={cycleNumber}
            />
          </div>
        )}

        {activeTab === 'map' && (
          <ArgoProfileMap
            profiles={profiles}
            observations={observations}
            platformId={platformId}
          />
        )}
      </div>
    </div>
  );
}
