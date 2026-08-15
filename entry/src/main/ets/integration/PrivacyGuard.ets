/** Removes common personal identifiers before audit or cross-device transfer. */
export class PrivacyGuard {
  static maskIdentifier(value: string): string {
    if (!value || value.length <= 8) {
      return value;
    }
    return `${value.substring(0, 4)}••••${value.substring(value.length - 4)}`;
  }

  static sanitizeText(value: string): string {
    return value
      .replace(/[1][3-9][0-9]{9}/g, '[PHONE]')
      .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '[EMAIL]');
  }
}
