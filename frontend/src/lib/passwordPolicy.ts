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

export function generateAutoPassword(length = 14): string {
  const lowers = "abcdefghjkmnpqrstuvwxyz";
  const uppers = "ABCDEFGHJKLMNPQRSTUVWXYZ";
  const digits = "23456789";
  const specials = "!@#$%^&*()_+-=";
  const all = lowers + uppers + digits + specials;

  const getRandomChar = (str: string) => str[Math.floor(Math.random() * str.length)];

  const passwordChars = [
    getRandomChar(lowers),
    getRandomChar(uppers),
    getRandomChar(digits),
    getRandomChar(specials),
  ];

  for (let i = passwordChars.length; i < length; i++) {
    passwordChars.push(getRandomChar(all));
  }

  for (let i = passwordChars.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [passwordChars[i], passwordChars[j]] = [passwordChars[j], passwordChars[i]];
  }

  return passwordChars.join("");
}
