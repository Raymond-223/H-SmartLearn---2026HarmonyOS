export class MindSporeLiteHelper {
  private static loaded: boolean = false;

  static async initModel(_modelPath: string): Promise<void> {
    this.loaded = true;
  }

  static async inferAnswer(answer: string): Promise<{ isCorrect: boolean; scoreDelta: number }> {
    if (!this.loaded) {
      await this.initModel('rawfile/model.ms');
    }
    const normalized = answer.trim().toUpperCase();
    const isCorrect = normalized === 'B';
    return {
      isCorrect,
      scoreDelta: isCorrect ? 15 : -5
    };
  }
}
