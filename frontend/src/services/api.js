/**
 * API Service for FloatChat.
 * Centralizes all communication with the FastAPI backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

/**
 * Checks backend health by querying GET /api/health.
 * @returns {Promise<{ ok: boolean, data?: object, error?: string, latencyMs?: number }>}
 */
export async function checkBackendHealth() {
  const startTime = performance.now();
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    const latencyMs = Math.round(performance.now() - startTime);

    if (!response.ok) {
      return {
        ok: false,
        error: `Server responded with status HTTP ${response.status}`,
        latencyMs,
      };
    }

    const data = await response.json();
    return {
      ok: true,
      data,
      latencyMs,
    };
  } catch (err) {
    const latencyMs = Math.round(performance.now() - startTime);
    return {
      ok: false,
      error: err instanceof Error ? err.message : 'Failed to connect to backend',
      latencyMs,
    };
  }
}

/**
 * Sends a natural language query to POST /api/chat/query.
 * @param {string} prompt - User natural language question
 * @returns {Promise<{
 *   ok: boolean,
 *   data?: {
 *     prompt: string,
 *     intent: string,
 *     parameters: object,
 *     data: object | null,
 *     data_count: number,
 *     summary: string,
 *     interpretation_explanation: string | null,
 *     source: string
 *   },
 *   error?: string,
 *   latencyMs?: number,
 *   status?: number
 * }>}
 */
export async function sendChatQuery(prompt) {
  const startTime = performance.now();
  try {
    const response = await fetch(`${API_BASE_URL}/api/chat/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ prompt: prompt.trim() }),
    });

    const latencyMs = Math.round(performance.now() - startTime);

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status} Error`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          errorMessage = typeof errorJson.detail === 'string'
            ? errorJson.detail
            : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fallback to generic message if response is not JSON
      }
      return {
        ok: false,
        error: errorMessage,
        status: response.status,
        latencyMs,
      };
    }

    const data = await response.json();
    return {
      ok: true,
      data,
      latencyMs,
    };
  } catch (err) {
    const latencyMs = Math.round(performance.now() - startTime);
    return {
      ok: false,
      error: err instanceof Error ? err.message : 'Network request failed. Is the FastAPI backend running?',
      latencyMs,
    };
  }
}
