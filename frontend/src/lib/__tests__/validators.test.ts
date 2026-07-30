import { indexToExcelColumnName, validateKRAParsingProfileSection } from "../validators";

export function runValidatorsTests(): boolean {
  let passed = true;

  function assertEqual(actual: unknown, expected: unknown, testName: string) {
    if (actual !== expected) {
      console.error(`[FAIL] ${testName}: Expected "${expected}", got "${actual}"`);
      passed = false;
    } else {
      console.log(`[PASS] ${testName}`);
    }
  }

  // --- Excel Column Name Converter Tests ---
  assertEqual(indexToExcelColumnName(0), "A", "0 -> A");
  assertEqual(indexToExcelColumnName(1), "B", "1 -> B");
  assertEqual(indexToExcelColumnName(25), "Z", "25 -> Z");
  assertEqual(indexToExcelColumnName(26), "AA", "26 -> AA");
  assertEqual(indexToExcelColumnName(27), "AB", "27 -> AB");
  assertEqual(indexToExcelColumnName(701), "ZZ", "701 -> ZZ");
  assertEqual(indexToExcelColumnName(702), "AAA", "702 -> AAA");
  assertEqual(indexToExcelColumnName(-1), "", "Negative number -> empty string");
  assertEqual(indexToExcelColumnName(null), "", "Null -> empty string");
  assertEqual(indexToExcelColumnName(undefined), "", "Undefined -> empty string");

  // --- Profile Section Validation Tests ---
  // 1. Unique valid configuration
  const validProfile = {
    pin_column: 0,
    partner_name_column: 1,
    invoice_number_column: 2,
    invoice_date_column: 3,
    cu_number_column: 4,
    base_amount_column: 5,
  };
  const resValid = validateKRAParsingProfileSection(validProfile);
  assertEqual(resValid.valid, true, "Valid profile section");
  assertEqual(Object.keys(resValid.fieldErrors).length, 0, "No field errors for valid profile");

  // 2. Duplicate column collision
  const duplicateProfile = {
    pin_column: 0,
    partner_name_column: 0,
    invoice_number_column: 2,
    invoice_date_column: 3,
  };
  const resDuplicate = validateKRAParsingProfileSection(duplicateProfile);
  assertEqual(resDuplicate.valid, false, "Duplicate profile is invalid");
  assertEqual(
    Boolean(resDuplicate.fieldErrors.pin_column),
    true,
    "pin_column marked as field error on duplicate"
  );
  assertEqual(
    Boolean(resDuplicate.fieldErrors.partner_name_column),
    true,
    "partner_name_column marked as field error on duplicate"
  );
  assertEqual(
    resDuplicate.fieldErrors.invoice_number_column,
    undefined,
    "Non-colliding field invoice_number_column has no error"
  );

  // 3. Negative column index
  const negativeProfile = {
    pin_column: -5,
    partner_name_column: 1,
  };
  const resNegative = validateKRAParsingProfileSection(negativeProfile);
  assertEqual(resNegative.valid, false, "Negative index profile is invalid");
  assertEqual(
    Boolean(resNegative.fieldErrors.pin_column),
    true,
    "pin_column has error on negative index"
  );

  // 4. Null & unmapped values allowed
  const unmappedProfile = {
    pin_column: 0,
    partner_name_column: null,
    invoice_number_column: null,
  };
  const resUnmapped = validateKRAParsingProfileSection(unmappedProfile);
  assertEqual(resUnmapped.valid, true, "Null fields allowed in profile section");

  return passed;
}

if (require.main === module) {
  const success = runValidatorsTests();
  process.exit(success ? 0 : 1);
}
