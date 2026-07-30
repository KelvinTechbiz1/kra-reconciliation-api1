import { formatApiError, getApiErrorMessage } from "../errors";

/**
 * Self-contained assertion helper for testing lib/errors without external test runner dependencies.
 */
export function runErrorsTests(): boolean {
  let passed = true;

  function assertEqual(actual: unknown, expected: unknown, testName: string) {
    if (actual !== expected) {
      console.error(`[FAIL] ${testName}: Expected "${expected}", got "${actual}"`);
      passed = false;
    } else {
      console.log(`[PASS] ${testName}`);
    }
  }

  // 1. String detail
  assertEqual(
    getApiErrorMessage({ detail: "Simple string error" }),
    "Simple string error",
    "String detail error"
  );

  // 2. String error direct
  assertEqual(
    getApiErrorMessage("Direct string error"),
    "Direct string error",
    "Direct string input"
  );

  // 3. Pydantic validation array with 'Value error, ' prefix
  const pydanticSingle = {
    detail: [
      {
        loc: ["body", "kra_parsing_profiles", "profiles", "SEC_B"],
        msg: "Value error, Duplicate column indexes are not allowed in a parsing profile",
        type: "value_error",
      },
    ],
  };
  assertEqual(
    getApiErrorMessage(pydanticSingle),
    "Duplicate column indexes are not allowed in a parsing profile",
    "Pydantic single validation error (prefix stripped)"
  );

  // 4. Multiple Pydantic validation errors
  const pydanticMultiple = {
    detail: [
      { msg: "Value error, Field A invalid" },
      { msg: "Field B must be >= 0" },
    ],
  };
  assertEqual(
    getApiErrorMessage(pydanticMultiple),
    "Field A invalid\nField B must be >= 0",
    "Multiple Pydantic validation errors joined by newline"
  );

  // 5. Message property
  assertEqual(
    getApiErrorMessage({ message: "Database unavailable" }),
    "Database unavailable",
    "Object with message property"
  );

  // 6. Native JS Error instance
  assertEqual(
    getApiErrorMessage(new Error("Network failed")),
    "Network failed",
    "JS Error instance"
  );

  // 7. Empty object returning fallback
  assertEqual(
    getApiErrorMessage({}, "Default fallback"),
    "Default fallback",
    "Empty object fallback"
  );

  // 8. Null / undefined returning fallback
  assertEqual(
    getApiErrorMessage(null, "Default fallback"),
    "Default fallback",
    "Null input fallback"
  );

  return passed;
}

if (require.main === module) {
  const success = runErrorsTests();
  process.exit(success ? 0 : 1);
}
