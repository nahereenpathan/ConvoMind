/**
 * Centralized utility to safely format any unknown error, API error response,
 * FastAPI detail object/array, or Axios error into a human-readable string.
 * Guarantees that the return value is ALWAYS a string, preventing React runtime
 * errors ("Objects are not valid as a React child").
 */
export function getErrorMessage(error: unknown): string {
  if (error === null || error === undefined) {
    return 'An unexpected error occurred';
  }

  if (typeof error === 'string') {
    return error.trim() || 'An unexpected error occurred';
  }

  if (typeof error === 'number' || typeof error === 'boolean') {
    return String(error);
  }

  if (typeof error === 'object') {
    const err = error as Record<string, any>;

    // 1. Axios Error with response payload
    if (err.response?.data) {
      const data = err.response.data;

      // FastAPI string detail e.g. { detail: "User with this email already exists" }
      if (typeof data.detail === 'string' && data.detail.trim()) {
        return data.detail;
      }

      // FastAPI 422 validation errors array: [{ loc: [...], msg: "...", type: "..." }]
      if (Array.isArray(data.detail)) {
        return formatFastApiDetailArray(data.detail);
      }

      // { message: "..." }
      if (typeof data.message === 'string' && data.message.trim()) {
        return data.message;
      }

      // { error: "..." }
      if (typeof data.error === 'string' && data.error.trim()) {
        return data.error;
      }
    }

    if (err.response?.status === 401) {
      return 'Session expired or unauthorized (401). Please log in again.';
    }

    if (err.response?.status === 403) {
      return 'Access denied (403). You do not have permission to perform this action.';
    }

    if (err.response?.status === 404) {
      return 'Requested resource or API endpoint not found (404).';
    }

    if (err.response?.status === 422) {
      return 'Validation error (422). Please verify your input data.';
    }

    if (err.response?.status === 500) {
      return 'Internal server error (500). Please check backend logs.';
    }

    if (err.response?.status === 503) {
      return 'Backend service temporarily unavailable (503). Please wait a moment and retry.';
    }

    if (err.code === 'ERR_NETWORK' || err.message === 'Network Error' || !err.response) {
      return 'Unable to reach backend server. Please verify the backend FastAPI server (port 8000) is running.';
    }

    // 2. Direct detail property on error object
    if (typeof err.detail === 'string' && err.detail.trim()) {
      return err.detail;
    }

    if (Array.isArray(err.detail)) {
      return formatFastApiDetailArray(err.detail);
    }

    // 3. Direct message property (Standard Error instance or custom object)
    if (typeof err.message === 'string' && err.message.trim()) {
      return err.message;
    }

    // 4. Fallback string representation for object
    try {
      const json = JSON.stringify(error);
      if (json && json !== '{}') {
        return json;
      }
    } catch {
      // Ignore serialization errors
    }
  }

  return String(error) || 'An unexpected error occurred';
}

/**
 * Format FastAPI 422 detail array [{ loc, msg, type }] into a clean string.
 */
function formatFastApiDetailArray(detailArray: any[]): string {
  if (!Array.isArray(detailArray) || detailArray.length === 0) {
    return 'Validation failed';
  }

  const messages = detailArray.map((item) => {
    if (typeof item === 'string') return item;
    if (item && typeof item === 'object') {
      const field = Array.isArray(item.loc)
        ? item.loc.filter((part: any) => part !== 'body' && part !== 'query' && part !== 'path').join('.')
        : '';
      const msg = item.msg || item.message || JSON.stringify(item);
      return field ? `${field}: ${msg}` : msg;
    }
    return String(item);
  });

  return messages.filter(Boolean).join('; ') || 'Validation error';
}
