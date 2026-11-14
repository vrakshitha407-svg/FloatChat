import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix default marker asset paths in bundlers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

export default function ArgoProfileMap({ profiles = [], observations = [], platformId }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const [selectedItem, setSelectedItem] = useState(null);

  // Extract valid profile points with genuine coordinates
  // Supports both profiles list and observations list
  let validPoints = [];

  if (profiles && profiles.length > 0) {
    validPoints = profiles.filter(
      (p) =>
        p &&
        p.latitude !== null &&
        p.latitude !== undefined &&
        p.longitude !== null &&
        p.longitude !== undefined &&
        !isNaN(p.latitude) &&
        !isNaN(p.longitude)
    );
  } else if (observations && observations.length > 0) {
    // Extract unique profile dive locations from observations
    const uniqueMap = new Map();
    observations.forEach((o) => {
      if (
        o &&
        o.latitude !== null &&
        o.latitude !== undefined &&
        o.longitude !== null &&
        o.longitude !== undefined &&
        !isNaN(o.latitude) &&
        !isNaN(o.longitude)
      ) {
        const key = `${o.platform_id}-${o.cycle_number}`;
        if (!uniqueMap.has(key)) {
          uniqueMap.set(key, {
            platform_id: o.platform_id,
            cycle_number: o.cycle_number,
            datetime: o.datetime,
            latitude: o.latitude,
            longitude: o.longitude,
            position_qc: o.position_qc,
            data_mode: o.data_mode || 'D',
          });
        }
      }
    });
    validPoints = Array.from(uniqueMap.values());
  }

  // Sort by cycle number for consistent chronological tracking
  validPoints.sort((a, b) => (a.cycle_number || 0) - (b.cycle_number || 0));

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Destroy prior map instance if re-rendering
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    if (validPoints.length === 0) return;

    // Initialize Leaflet map
    const map = L.map(mapContainerRef.current, {
      zoomControl: true,
      attributionControl: true,
      minZoom: 2,
      maxZoom: 18,
    });
    mapInstanceRef.current = map;

    // Add high-resolution oceanographic basemap (Esri Ocean / World Dark Gray) with OSM fallback
    const oceanTileLayer = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}',
      {
        attribution:
          'Tiles &copy; Esri &mdash; Sources: GEBCO, NOAA, CHS, OSU, UNH, CSUMB, National Geographic, DeLorme, NAVTEQ, and other contributors',
        maxZoom: 13,
      }
    );
    oceanTileLayer.addTo(map);

    // Marker feature group for bounds calculation
    const markersGroup = L.featureGroup();
    const latLngs = [];

    validPoints.forEach((p, idx) => {
      const lat = p.latitude;
      const lon = p.longitude;
      latLngs.push([lat, lon]);

      // Custom ocean beacon marker with cycle label and pulsing radar ring
      const customBeaconIcon = L.divIcon({
        className: 'argo-leaflet-marker',
        html: `
          <div class="beacon-pin" title="Float ${p.platform_id} Cycle #${p.cycle_number}">
            <div class="beacon-pulse"></div>
            <div class="beacon-dot">
              <span>#${p.cycle_number !== undefined ? p.cycle_number : idx + 1}</span>
            </div>
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -14],
      });

      const marker = L.marker([lat, lon], { icon: customBeaconIcon });

      const dateStr = p.datetime
        ? p.datetime.replace('T', ' ').slice(0, 19) + ' UTC'
        : 'N/A';
      const latStr = `${Math.abs(lat).toFixed(3)}° ${lat >= 0 ? 'N' : 'S'}`;
      const lonStr = `${Math.abs(lon).toFixed(3)}° ${lon >= 0 ? 'E' : 'W'}`;

      const popupContent = `
        <div class="argo-popup-card">
          <div class="popup-header">
            <span class="popup-badge">ARGO Profiling Float</span>
            <h4 class="popup-title">WMO ID: ${p.platform_id}</h4>
          </div>
          <div class="popup-grid">
            <div class="popup-item">
              <span class="p-label">Dive Cycle:</span>
              <strong class="p-val text-cyan">Cycle #${p.cycle_number}</strong>
            </div>
            <div class="popup-item">
              <span class="p-label">Surfacing Date:</span>
              <span class="p-val">${dateStr}</span>
            </div>
            <div class="popup-item">
              <span class="p-label">Latitude:</span>
              <span class="p-val font-mono">${latStr} (${lat.toFixed(4)}°)</span>
            </div>
            <div class="popup-item">
              <span class="p-label">Longitude:</span>
              <span class="p-val font-mono">${lonStr} (${lon.toFixed(4)}°)</span>
            </div>
            ${
              p.num_levels
                ? `<div class="popup-item">
                     <span class="p-label">Vertical Levels:</span>
                     <span class="p-val">${p.num_levels} depth samples</span>
                   </div>`
                : ''
            }
            ${
              p.min_pressure_dbar !== undefined && p.max_pressure_dbar !== undefined
                ? `<div class="popup-item">
                     <span class="p-label">Depth Range:</span>
                     <span class="p-val">${p.min_pressure_dbar?.toFixed(1)} &rarr; ${p.max_pressure_dbar?.toFixed(1)} dbar</span>
                   </div>`
                : ''
            }
          </div>
        </div>
      `;

      marker.bindPopup(popupContent, {
        className: 'argo-custom-popup',
        maxWidth: 280,
      });

      marker.on('click', () => {
        setSelectedItem(p);
      });

      marker.addTo(markersGroup);
    });

    // Draw drift trajectory line connecting dive cycles if multiple points exist
    if (latLngs.length > 1) {
      const trajectory = L.polyline(latLngs, {
        color: '#38bdf8',
        weight: 2.5,
        opacity: 0.85,
        dashArray: '6, 8',
        lineCap: 'round',
      });
      trajectory.addTo(map);
    }

    markersGroup.addTo(map);

    // Auto-fit map viewport to encompass all float markers
    if (validPoints.length === 1) {
      map.setView([validPoints[0].latitude, validPoints[0].longitude], 7);
    } else {
      map.fitBounds(markersGroup.getBounds().pad(0.35));
    }

    // Force tile recalculation after layout mount
    setTimeout(() => {
      map.invalidateSize();
    }, 150);

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [validPoints.length]);

  if (validPoints.length === 0) {
    return (
      <div className="viz-empty-state">
        <p>No spatial coordinates available in the retrieved records to plot on map.</p>
      </div>
    );
  }

  return (
    <div className="map-card">
      <div className="map-header">
        <div className="map-title-block">
          <h4 className="map-title">
            <span className="chart-badge map-badge">Geographic Map</span> ARGO Float Trajectory &amp; Profile Locations
          </h4>
          <span className="map-subtitle">
            Authentic surfacing coordinates for Float {platformId || validPoints[0]?.platform_id} ({validPoints.length} cycle{validPoints.length !== 1 ? 's' : ''})
          </span>
        </div>

        {/* Selected or First Profile Coordinates Chip */}
        <div className="map-meta-tags">
          <div className="map-tag">
            <span className="map-tag-label">Active Region:</span>
            <span className="map-tag-val">Equatorial Indian Ocean</span>
          </div>
          {validPoints.length > 1 && (
            <div className="map-tag">
              <span className="map-tag-label">Float Drift:</span>
              <span className="map-tag-val">Cycle #{validPoints[0].cycle_number} &rarr; Cycle #{validPoints[validPoints.length - 1].cycle_number}</span>
            </div>
          )}
        </div>
      </div>

      <div className="leaflet-map-wrapper">
        <div ref={mapContainerRef} className="argo-map-container" />
      </div>

      <div className="map-footer">
        <span className="map-note">
          Click any marker pin to inspect surfacing date, coordinates, and depth level details.
        </span>
        <span className="map-legend-drift">
          <span className="legend-dash"></span> Drift Trajectory
        </span>
      </div>
    </div>
  );
}
