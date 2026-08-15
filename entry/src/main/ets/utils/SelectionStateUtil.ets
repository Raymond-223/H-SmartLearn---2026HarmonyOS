/** Pure helpers for observable single-choice state. */
export class SelectionStateUtil {
  static empty(count: number): string[] {
    const result: string[] = [];
    for (let index: number = 0; index < count; index++) result.push('');
    return result;
  }

  static replace(values: string[], index: number, value: string): string[] {
    const result: string[] = values.slice();
    if (index >= 0 && index < result.length) result[index] = value;
    return result;
  }

  static answeredCount(values: string[]): number {
    let count: number = 0;
    for (const value of values) {
      if (value.length > 0) count++;
    }
    return count;
  }

  static allAnswered(values: string[], expectedCount: number): boolean {
    return expectedCount > 0 && values.length === expectedCount &&
      SelectionStateUtil.answeredCount(values) === expectedCount;
  }

  static firstUnanswered(values: string[]): number {
    for (let index: number = 0; index < values.length; index++) {
      if (values[index].length === 0) return index;
    }
    return -1;
  }
}
