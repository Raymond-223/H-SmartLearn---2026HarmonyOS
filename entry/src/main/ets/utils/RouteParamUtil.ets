/** Typed accessors for parameters passed through HarmonyOS router. */
export class RouteParamUtil {
  static asMap(params: Object): Record<string, Object> {
    return params as Record<string, Object>;
  }

  static string(params: Object, key: string, fallback: string = ''): string {
    const value: Object | undefined = RouteParamUtil.asMap(params)[key];
    return typeof value === 'string' ? value : fallback;
  }

  static boolean(params: Object, key: string, fallback: boolean = false): boolean {
    const value: Object | undefined = RouteParamUtil.asMap(params)[key];
    if (typeof value === 'boolean') return value;
    if (typeof value === 'string') return value.toLowerCase() === 'true';
    return fallback;
  }
}
