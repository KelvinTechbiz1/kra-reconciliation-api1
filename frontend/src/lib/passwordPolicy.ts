export interface PasswordPolicyResult {
  isValid: boolean;
  checks: {
    length: boolean;
    uppercase: boolean;
    lowercase: boolean;
    number: boolean;
    special: boolean;
  };
  errors: string[];
}

export function validatePasswordPolicy(password: string): PasswordPolicyResult {
  const checks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
    special: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>/?~`]/.test(password),
  };

  const errors: string[] = [];
  if (!checks.length) errors.push("At least 8 characters");
  if (!checks.uppercase) errors.push("At least 1 uppercase letter (A-Z)");
  if (!checks.lowercase) errors.push("At least 1 lowercase letter (a-z)");
  if (!checks.number) errors.push("At least 1 number (0-9)");
  if (!checks.special) errors.push("At least 1 special character (!@#$%^&*)");

  const isValid = Object.values(checks).every(Boolean);

  return {
    isValid,
    checks,
    errors,
  };
}
