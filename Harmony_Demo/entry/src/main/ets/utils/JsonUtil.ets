export class JsonUtil {
  static parseObject<T>(text: string, fallback: T): T {
    try {
      return JSON.parse(text) as T;
    } catch (error) {
      return fallback;
    }
  }
}
