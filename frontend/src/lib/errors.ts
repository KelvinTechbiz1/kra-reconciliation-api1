export interface NormalizedApiError {
  message: string;
  details: string[];
}

/**
 * Normalizes API error payloads (FastAPI/Pydantic validation errors, string details, 
 * object messages, network errors) into a structured NormalizedApiError format.
 */
export function formatApiError(
  errData: unknown,
  fallbackMessage: string = "An unexpected error occurred."
): NormalizedApiError {
  if (!errData) {
    return { message: fallbackMessage, details: [] };
  }

  // Handle standard JS Error instances
  if (errData instanceof Error) {
    return { message: errData.message || fallbackMessage, details: [] };
  }

  // Handle string error responses
  if (typeof errData === "string") {
    return { message: errData, details: [] };
  }

  if (typeof errData === "object" && errData !== null) {
    const obj = errData as Record<string, unknown>;

    // Case 1: FastAPI/Pydantic validation errors: { detail: [ { loc: [...], msg: "...", type: "..." } ] }
    if (Array.isArray(obj.detail)) {
      const details: string[] = obj.detail.map((item) => {
        if (typeof item === "string") return item;
        if (typeof item === "object" && item !== null && "msg" in item) {
          const msg = String((item as { msg: unknown }).msg);
          // Strip unwanted "Value error, " prefix if present
          return msg.startsWith("Value error, ") ? msg.replace("Value error, ", "") : msg;
        }
        return JSON.stringify(item);
      });

      const message = details.length > 0 ? details.join("\n") : fallbackMessage;
      return { message, details };
    }

    // Case 2: Object with string detail: { detail: "Some error" }
    if (typeof obj.detail === "string" && obj.detail.trim() !== "") {
      return { message: obj.detail, details: [] };
    }

    // Case 3: Object with message property: { message: "Some error" }
    if (typeof obj.message === "string" && obj.message.trim() !== "") {
      return { message: obj.message, details: [] };
    }

    // Case 4: Detail is a non-array object
    if (typeof obj.detail === "object" && obj.detail !== null) {
      return { message: JSON.stringify(obj.detail), details: [] };
    }
  }

  return { message: fallbackMessage, details: [] };
}

/**
 * Convenience function that returns a single formatted message string for toasts/alerts.
 */
export function getApiErrorMessage(
  errData: unknown,
  fallbackMessage: string = "An unexpected error occurred."
): string {
  const normalized = formatApiError(errData, fallbackMessage);
  return normalized.message;
}
