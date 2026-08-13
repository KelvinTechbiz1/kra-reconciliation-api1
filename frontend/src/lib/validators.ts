export interface ProfileValidationResult {
  valid: boolean;
  fieldErrors: Record<string, string>; // Maps model property field key (e.g. "pin_column") to error string
  messages: string[];
}

const FIELD_LABELS: Record<string, string> = {
  pin_column: "PIN Column Index",
  partner_name_column: "Partner Name Column Index",
  invoice_number_column: "Invoice Number Column Index",
  invoice_date_column: "Invoice Date Column Index",
  cu_number_column: "CU / Receipt Number Column Index",
  base_amount_column: "Base Amount Column Index",
};

/**
 * Converts a zero-based column index to an Excel-style column letter representation.
 * Examples: 0 -> "A", 25 -> "Z", 26 -> "AA", 27 -> "AB", 701 -> "ZZ", 702 -> "AAA"
 * Returns "" for negative numbers, null, or undefined.
 */
export function indexToExcelColumnName(index: number | null | undefined): string {
  if (index === null || index === undefined || index < 0 || !Number.isInteger(index)) {
    return "";
  }
  let temp = index;
  let colName = "";
  while (temp >= 0) {
    colName = String.fromCharCode((temp % 26) + 65) + colName;
    temp = Math.floor(temp / 26) - 1;
  }
  return colName;
}

/**
 * Validates a single KRA CSV Parsing Profile section configuration.
 * Checks for negative column indices and duplicate column index assignments.
 */
export function validateKRAParsingProfileSection(
  profile: Record<string, number | null | undefined>
): ProfileValidationResult {
  const fieldErrors: Record<string, string> = {};
  const messages: string[] = [];

  const indexMap = new Map<number, string[]>();

  for (const [fieldKey, value] of Object.entries(profile)) {
    if (value === null || value === undefined) {
      continue;
    }

    // Rule 1: Must be non-negative integer
    if (value < 0 || !Number.isInteger(value)) {
      const label = FIELD_LABELS[fieldKey] || fieldKey;
      fieldErrors[fieldKey] = `${label} must be a non-negative integer.`;
      messages.push(`${label} must be a non-negative integer.`);
      continue;
    }

    // Track assigned column index for duplicate collision check
    const existing = indexMap.get(value) || [];
    indexMap.set(value, [...existing, fieldKey]);
  }

  // Rule 2: Duplicate Index Collision check grouped by column index
  for (const [colIndex, fieldKeys] of indexMap.entries()) {
    if (fieldKeys.length > 1) {
      const excelLetter = indexToExcelColumnName(colIndex);
      const labels = fieldKeys.map((k) => FIELD_LABELS[k] || k).join(", ");
      const msg = `Column ${colIndex} (${excelLetter}) is assigned to multiple fields: ${labels}`;
      messages.push(msg);

      for (const fieldKey of fieldKeys) {
        fieldErrors[fieldKey] = `Duplicate column index ${colIndex} (${excelLetter})`;
      }
    }
  }

  return {
    valid: Object.keys(fieldErrors).length === 0,
    fieldErrors,
    messages,
  };
}

/**
 * Validates a new KRA section prefix string (e.g., "SEC_J", "SEC_B").
 * Must start with "SEC_" and consist of uppercase letters, numbers, or underscores.
 */
export function validateKRASectionPrefix(rawPrefix: string): { valid: boolean; formatted: string; error?: string } {
  const trimmed = rawPrefix.trim().toUpperCase();
  let prefix = trimmed;
  if (prefix && !prefix.startsWith("SEC_")) {
    prefix = `SEC_${prefix}`;
  }

  if (!prefix) {
    return { valid: false, formatted: "", error: "Section prefix cannot be empty." };
  }

  if (!/^SEC_[A-Z0-9]+$/.test(prefix)) {
    return {
      valid: false,
      formatted: prefix,
      error: "Section identifier must match pattern SEC_... (e.g., SEC_J, SEC_B, SEC_J1).",
    };
  }

  return { valid: true, formatted: prefix };
}

