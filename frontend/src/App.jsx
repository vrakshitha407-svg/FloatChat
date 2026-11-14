import React, { useState, useEffect, useRef } from 'react';
import { checkBackendHealth, sendChatQuery } from './services/api';
import VisualizationsPanel from './components/VisualizationsPanel';
import './App.css';

// Sample real-data queries aligned with loaded ARGO float 1900121
const EXAMPLE_QUERIES = [
  {
    label: 'Dataset Overview',
    prompt: 'What ARGO datasets are currently loaded?',
    category: 'summary',
  },
  {
    label: 'Float Profiles',
    prompt: 'Show profiles for float 1900121',
    category: 'profiles',
  },
  {
    label: 'Cycle 1 Observations',
    prompt: 'Show observations for float 1900121 cycle 1',
    category: 'observations',
  },
  {
    label: 'Surface Temperature',
    prompt: 'Surface temperature for float 1900121 cycle 2',
    category: 'depth',
  },
  {
    label: 'Upper Ocean Salinity',
    prompt: 'Salinity measurements between 0 and 200 dbar for float 1900121',
    category: 'depth',
  },
  {
    label: 'Out-of-Domain Query',
    prompt: 'How do I bake chocolate chip cookies?',
    category: 'test',
  },
];

function App() {
  // Backend health status
  const [healthStatus, setHealthStatus] = useState({
    loading: true,
    connected: false,
    data: null,
    error: null,
    latencyMs: null,
  });

  // Chat conversation messages
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      isWelcome: true,
      timestamp: new Date().toLocaleTimeString(),
      summary:
        'Welcome to FloatChat. I am connected to the ARGO oceanographic query engine. You can ask natural language questions about float profiles, dive cycles, ocean temperatures, practical salinity, and pressure/depth levels.',
      intent: 'summary',
      source: 'system',
      data_count: 0,
    },
  ]);

  // Input state
  const [inputPrompt, setInputPrompt] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Expanded inspection states: messageId -> boolean
  const [expandedInspectors, setExpandedInspectors] = useState({});
  // View mode for inspection: messageId -> 'table' | 'json'
  const [inspectViewModes, setInspectViewModes] = useState({});

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSubmitting]);

  // Verify backend health on mount and periodically
  const verifyBackend = async () => {
    setHealthStatus((prev) => ({ ...prev, loading: true, error: null }));
    const result = await checkBackendHealth();
    if (result.ok) {
      setHealthStatus({
        loading: false,
        connected: true,
        data: result.data,
        error: null,
        latencyMs: result.latencyMs,
      });
    } else {
      setHealthStatus({
        loading: false,
        connected: false,
        data: null,
        error: result.error,
        latencyMs: result.latencyMs,
      });
    }
  };

  useEffect(() => {
    verifyBackend();
    const interval = setInterval(verifyBackend, 30000); // Heartbeat every 30s
    return () => clearInterval(interval);
  }, []);

  // Handle submitting a chat query
  const handleSubmitQuery = async (queryText) => {
    const textToSend = (queryText || inputPrompt).trim();
    if (!textToSend || isSubmitting) return;

    const userMessageId = `user-${Date.now()}`;
    const userMessage = {
      id: userMessageId,
      role: 'user',
      prompt: textToSend,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputPrompt('');
    setIsSubmitting(true);

    const result = await sendChatQuery(textToSend);

    if (result.ok && result.data) {
      const responseData = result.data;
      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        prompt: responseData.prompt,
        intent: responseData.intent,
        parameters: responseData.parameters || {},
        data: responseData.data,
        data_count: responseData.data_count ?? 0,
        summary: responseData.summary,
        interpretation_explanation: responseData.interpretation_explanation,
        source: responseData.source,
        latencyMs: result.latencyMs,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } else {
      // Error message
      const errorMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        isError: true,
        error: result.error || 'Failed to retrieve data from FloatChat service',
        prompt: textToSend,
        timestamp: new Date().toLocaleTimeString(),
        latencyMs: result.latencyMs,
      };
      setMessages((prev) => [...prev, errorMessage]);
    }

    setIsSubmitting(false);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmitQuery();
    }
  };

  const toggleInspector = (msgId) => {
    setExpandedInspectors((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  const setViewMode = (msgId, mode) => {
    setInspectViewModes((prev) => ({
      ...prev,
      [msgId]: mode,
    }));
  };

  const clearChat = () => {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: 'assistant',
        isWelcome: true,
        timestamp: new Date().toLocaleTimeString(),
        summary:
          'Chat history cleared. The ARGO dataset is ready for new queries.',
        intent: 'summary',
        source: 'system',
        data_count: 0,
      },
    ]);
  };

  // Helper to format source badge
  const renderSourceBadge = (source) => {
    if (source === 'gemini') {
      return (
        <span className="source-badge gemini" title="Generated by Google Gemini LLM">
          <span className="badge-sparkle">✦</span> Gemini LLM
        </span>
      );
    }
    if (source === 'rule_based') {
      return (
        <span className="source-badge rule-based" title="Processed by Deterministic Rule-Based Fallback Engine">
          <span className="badge-gear">⚙</span> Rule-Based Fallback
        </span>
      );
    }
    return null;
  };

  // Helper to format intent badge
  const renderIntentBadge = (intent) => {
    const labels = {
      summary: 'Dataset Overview',
      query_profiles: 'Profiles Query',
      query_observations: 'Observations Query',
      out_of_domain: 'Out of Domain',
    };
    return (
      <span className={`intent-badge ${intent || 'default'}`}>
        {labels[intent] || intent}
      </span>
    );
  };

  // Render extracted parameters chips
  const renderParameters = (params) => {
    if (!params) return null;
    const chips = [];

    if (params.platform_id) {
      chips.push(
        <span key="plat" className="param-chip">
          <strong>Float:</strong> {params.platform_id}
        </span>
      );
    }
    if (params.cycle_number !== null && params.cycle_number !== undefined) {
      chips.push(
        <span key="cycle" className="param-chip">
          <strong>Cycle:</strong> #{params.cycle_number}
        </span>
      );
    }
    if (params.min_depth !== null || params.max_depth !== null) {
      const dMin = params.min_depth !== null ? `${params.min_depth} dbar` : '0';
      const dMax = params.max_depth !== null ? `${params.max_depth} dbar` : 'max';
      chips.push(
        <span key="depth" className="param-chip">
          <strong>Depth:</strong> {dMin} &rarr; {dMax}
        </span>
      );
    }
    if (params.start_date || params.end_date) {
      chips.push(
        <span key="dates" className="param-chip">
          <strong>Dates:</strong> {params.start_date || 'start'} &rarr; {params.end_date || 'end'}
        </span>
      );
    }
    if (params.min_lat !== null || params.max_lat !== null) {
      chips.push(
        <span key="lat" className="param-chip">
          <strong>Lat:</strong> {params.min_lat}&deg; &rarr; {params.max_lat}&deg;
        </span>
      );
    }
    if (params.variables && params.variables.length > 0) {
      chips.push(
        <span key="vars" className="param-chip">
          <strong>Vars:</strong> {params.variables.join(', ')}
        </span>
      );
    }

    if (chips.length === 0) return null;

    return (
      <div className="parameters-row">
        <span className="param-header">Extracted Parameters:</span>
        <div className="param-chips-list">{chips}</div>
      </div>
    );
  };

  // Render retrieved data tables
  const renderDataTable = (msg) => {
    const { intent, data } = msg;
    if (!data) return <p className="no-data-msg">No data records returned.</p>;

    // Case 1: Summary Intent
    if (intent === 'summary' && data.summary) {
      const s = data.summary;
      return (
        <div className="summary-data-grid">
          <div className="stat-card">
            <span className="stat-label">Total Profiles</span>
            <span className="stat-val">{s.total_profiles}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Total Observation Levels</span>
            <span className="stat-val">{s.total_observations}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Indexed Platforms</span>
            <span className="stat-val">{(s.platforms || []).join(', ') || 'N/A'}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Temporal Range</span>
            <span className="stat-val">
              {s.date_min ? s.date_min.split('T')[0] : 'N/A'} &rarr; {s.date_max ? s.date_max.split('T')[0] : 'N/A'}
            </span>
          </div>
          <div className="stat-card full-span">
            <span className="stat-label">Geographic Bounding Box</span>
            <span className="stat-val">
              Latitude: {s.lat_min?.toFixed(2)}&deg; to {s.lat_max?.toFixed(2)}&deg; &bull; Longitude: {s.lon_min?.toFixed(2)}&deg; to {s.lon_max?.toFixed(2)}&deg;
            </span>
          </div>
        </div>
      );
    }

    // Case 2: Profiles List
    if (intent === 'query_profiles' && data.profiles) {
      const profiles = data.profiles;
      if (profiles.length === 0) {
        return <p className="no-data-msg">Zero profiles matched the query.</p>;
      }
      return (
        <div className="table-responsive">
          <table className="scientific-table">
            <thead>
              <tr>
                <th>Platform ID</th>
                <th>Cycle</th>
                <th>Surfacing Time (UTC)</th>
                <th>Coordinates (Lat, Lon)</th>
                <th>Levels</th>
                <th>Depth Range (dbar)</th>
                <th>Mode</th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p, idx) => (
                <tr key={idx}>
                  <td><code>{p.platform_id}</code></td>
                  <td><strong>#{p.cycle_number}</strong></td>
                  <td>{p.datetime ? p.datetime.replace('T', ' ').slice(0, 19) : 'N/A'}</td>
                  <td>{p.latitude?.toFixed(3)}&deg;, {p.longitude?.toFixed(3)}&deg;</td>
                  <td>{p.num_levels}</td>
                  <td>
                    {p.min_pressure_dbar?.toFixed(1)} &rarr; {p.max_pressure_dbar?.toFixed(1)}
                  </td>
                  <td><span className="badge-mode">{p.data_mode}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    // Case 3: Observations List
    if (intent === 'query_observations' && data.observations) {
      const obs = data.observations;
      if (obs.length === 0) {
        return <p className="no-data-msg">Zero observations matched the depth/cycle filters.</p>;
      }
      const previewRows = obs.slice(0, 50); // Preview up to 50 levels for performance
      return (
        <div className="table-responsive">
          <table className="scientific-table">
            <thead>
              <tr>
                <th>Level</th>
                <th>Pressure (dbar)</th>
                <th>Temperature (&deg;C)</th>
                <th>Salinity (PSU)</th>
                <th>QC Flags (P, T, S)</th>
                <th>Data Source</th>
              </tr>
            </thead>
            <tbody>
              {previewRows.map((o, idx) => (
                <tr key={idx}>
                  <td>{o.level_index !== undefined ? o.level_index : idx + 1}</td>
                  <td><code>{o.pressure_dbar !== null ? o.pressure_dbar.toFixed(1) : 'NaN'}</code></td>
                  <td className="temp-cell">
                    {o.temperature_c !== null ? `${o.temperature_c.toFixed(2)} °C` : 'NaN'}
                  </td>
                  <td className="psal-cell">
                    {o.salinity_psu !== null ? `${o.salinity_psu.toFixed(2)} PSU` : 'NaN'}
                  </td>
                  <td>
                    <span className="qc-tag" title="Pressure QC">P:{o.pres_qc}</span>{' '}
                    <span className="qc-tag" title="Temperature QC">T:{o.temp_qc}</span>{' '}
                    <span className="qc-tag" title="Salinity QC">S:{o.psal_qc}</span>
                  </td>
                  <td><span className="source-tag">{o.temp_source || 'adjusted'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {obs.length > 50 && (
            <p className="table-footnote">
              Showing first 50 of {obs.length} vertical observation levels. Switch to JSON view for full records.
            </p>
          )}
        </div>
      );
    }

    // Fallback: render keys
    return <p className="no-data-msg">Retrieved {msg.data_count} records.</p>;
  };

  return (
    <div className="app-container">
      {/* Top Application Bar */}
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-badge">Oceanographic AI Platform</div>
          <h1 className="brand-title">
            <span className="ocean-gradient">FloatChat</span>
          </h1>
          <p className="brand-subtitle">
            AI-Powered Conversational Interface for ARGO Ocean Data Discovery and Visualization
          </p>
        </div>

        {/* Live Connectivity Indicator */}
        <div className="connectivity-card">
          <div className="status-indicator">
            <span
              className={`status-dot ${
                healthStatus.loading ? 'loading' : healthStatus.connected ? 'connected' : 'disconnected'
              }`}
            />
            <div className="status-text">
              <span className="status-state">
                {healthStatus.loading
                  ? 'Connecting...'
                  : healthStatus.connected
                  ? 'FastAPI Connected'
                  : 'Backend Offline'}
              </span>
              {healthStatus.connected && (
                <span className="status-meta">
                  {healthStatus.latencyMs}ms &bull; v{healthStatus.data?.version || '0.1.0'}
                </span>
              )}
            </div>
          </div>

          <div className="header-actions">
            <button
              onClick={verifyBackend}
              disabled={healthStatus.loading}
              className="action-btn-mini"
              title="Re-test backend connectivity"
            >
              &#8635;
            </button>
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="action-btn-mini"
              title="Open FastAPI Swagger Documentation"
            >
              API Docs ↗
            </a>
          </div>
        </div>
      </header>

      {/* Dataset Context Bar */}
      <section className="dataset-context-bar">
        <div className="context-item">
          <span className="ctx-label">Active Platform</span>
          <span className="ctx-val">INCOIS Float 1900121</span>
        </div>
        <div className="context-item">
          <span className="ctx-label">Location</span>
          <span className="ctx-val">Equatorial Indian Ocean</span>
        </div>
        <div className="context-item">
          <span className="ctx-label">Loaded Cycles</span>
          <span className="ctx-val">Cycles 1, 2, 3 (135 Obs Levels)</span>
        </div>
        <div className="context-item">
          <span className="ctx-label">Data Fidelity</span>
          <span className="ctx-val text-cyan">Authentic NetCDF (Preserved)</span>
        </div>
      </section>

      {/* Main Conversational Workspace */}
      <main className="chat-workspace">
        <div className="messages-stream">
          {messages.map((msg) => (
            <div key={msg.id} className={`message-bubble ${msg.role}`}>
              {/* User Message */}
              {msg.role === 'user' && (
                <div className="user-message-card">
                  <div className="message-meta">
                    <span className="author-label">You</span>
                    <span className="message-time">{msg.timestamp}</span>
                  </div>
                  <div className="user-prompt-text">{msg.prompt}</div>
                </div>
              )}

              {/* Assistant Message */}
              {msg.role === 'assistant' && (
                <div className={`assistant-message-card ${msg.isError ? 'error-card' : ''}`}>
                  {/* Assistant Meta Header */}
                  <div className="message-meta">
                    <div className="meta-left">
                      <span className="author-label assistant-label">FloatChat AI</span>
                      {!msg.isError && renderIntentBadge(msg.intent)}
                      {!msg.isError && renderSourceBadge(msg.source)}
                      {msg.data_count !== undefined && msg.data_count > 0 && (
                        <span className="count-badge">
                          {msg.data_count} record{msg.data_count !== 1 ? 's' : ''}
                        </span>
                      )}
                    </div>
                    <div className="meta-right">
                      {msg.latencyMs && (
                        <span className="latency-badge">{msg.latencyMs} ms</span>
                      )}
                      <span className="message-time">{msg.timestamp}</span>
                    </div>
                  </div>

                  {/* Summary / Core Answer */}
                  {msg.isError ? (
                    <div className="error-content">
                      <p className="error-title">&#9888; Query Processing Error</p>
                      <p className="error-text">{msg.error}</p>
                      <button
                        onClick={() => handleSubmitQuery(msg.prompt)}
                        className="retry-btn"
                      >
                        &#8635; Retry Query
                      </button>
                    </div>
                  ) : (
                    <div className="summary-content">
                      <p className="summary-text">{msg.summary}</p>
                    </div>
                  )}

                  {/* Extracted Parameters & Interpretation Explanation */}
                  {!msg.isError && !msg.isWelcome && (
                    <div className="interpretation-section">
                      {renderParameters(msg.parameters)}
                      {msg.interpretation_explanation && (
                        <div className="explanation-text">
                          <span className="expl-label">Reasoning:</span>{' '}
                          {msg.interpretation_explanation}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Interactive Scientific Visualisations (Stage 3) */}
                  {!msg.isError && !msg.isWelcome && (
                    <VisualizationsPanel message={msg} />
                  )}

                  {/* Expandable Data Inspector */}
                  {!msg.isError && !msg.isWelcome && msg.data && (
                    <div className="data-inspector-container">
                      <div className="inspector-header">
                        <button
                          onClick={() => toggleInspector(msg.id)}
                          className="inspector-toggle-btn"
                        >
                          <span className="toggle-icon">
                            {expandedInspectors[msg.id] ? '&#9660;' : '&#9654;'}
                          </span>
                          Inspect Retrieved Data ({msg.data_count} record{msg.data_count !== 1 ? 's' : ''})
                        </button>

                        {expandedInspectors[msg.id] && (
                          <div className="view-mode-tabs">
                            <button
                              onClick={() => setViewMode(msg.id, 'table')}
                              className={`tab-btn ${(inspectViewModes[msg.id] || 'table') === 'table' ? 'active' : ''}`}
                            >
                              Table View
                            </button>
                            <button
                              onClick={() => setViewMode(msg.id, 'json')}
                              className={`tab-btn ${inspectViewModes[msg.id] === 'json' ? 'active' : ''}`}
                            >
                              Raw JSON
                            </button>
                          </div>
                        )}
                      </div>

                      {expandedInspectors[msg.id] && (
                        <div className="inspector-body">
                          {(inspectViewModes[msg.id] || 'table') === 'table' ? (
                            renderDataTable(msg)
                          ) : (
                            <pre className="json-pre">
                              {JSON.stringify(msg.data, null, 2)}
                            </pre>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Submitting / Loading Pulse */}
          {isSubmitting && (
            <div className="message-bubble assistant">
              <div className="assistant-message-card loading-card">
                <div className="loading-indicator">
                  <div className="pulse-spinner" />
                  <span className="loading-label">
                    Interpreting query, searching ARGO Parquet datasets & generating grounded summary...
                  </span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Chips */}
        <div className="suggestions-bar">
          <div className="suggestions-label">Example Questions:</div>
          <div className="chips-scroller">
            {EXAMPLE_QUERIES.map((q, idx) => (
              <button
                key={idx}
                onClick={() => handleSubmitQuery(q.prompt)}
                disabled={isSubmitting}
                className={`suggestion-chip category-${q.category}`}
              >
                {q.label}
              </button>
            ))}
          </div>
        </div>

        {/* Chat Input Bar */}
        <div className="chat-input-container">
          <div className="input-wrapper">
            <textarea
              ref={inputRef}
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about ARGO floats, dive cycles, depth, temperature, salinity..."
              rows={1}
              disabled={isSubmitting}
              className="chat-textarea"
            />
            <button
              onClick={() => handleSubmitQuery()}
              disabled={isSubmitting || !inputPrompt.trim()}
              className="send-btn"
              title="Send Query (Enter)"
            >
              {isSubmitting ? (
                <span className="mini-spinner" />
              ) : (
                <svg
                  className="send-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              )}
            </button>
          </div>

          <div className="input-footer">
            <span className="input-hint">
              Press <strong>Enter</strong> to send &bull; Shift + Enter for new line
            </span>
            {messages.length > 1 && (
              <button onClick={clearChat} className="clear-btn">
                Clear Chat
              </button>
            )}
          </div>
        </div>
      </main>

      {/* Scientific Integrity Footer */}
      <footer className="app-footer">
        <p>
          FloatChat &bull; Authentic ARGO Float Observations (WMO ID 1900121) &bull; Grounded Science Interface
        </p>
      </footer>
    </div>
  );
}

export default App;
