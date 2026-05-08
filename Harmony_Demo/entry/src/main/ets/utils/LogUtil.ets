export class LogUtil {
  static info(tag: string, message: string): void {
    console.info(`[${tag}] ${message}`);
  }

  static warn(tag: string, message: string): void {
    console.warn(`[${tag}] ${message}`);
  }

  static error(tag: string, message: string): void {
    console.error(`[${tag}] ${message}`);
  }
}
