import { MindSporeLiteHelper } from '../integration/MindSporeLiteHelper';
import { DataStore } from './DataStore';
import { QuizRecord } from '../model/QuizRecord';

export class AiInference {
  static async processAnswer(questionId: string, answer: string): Promise<void> {
    const result = await MindSporeLiteHelper.inferAnswer(answer);
    const record: QuizRecord = {
      questionId,
      answer,
      isCorrect: result.isCorrect,
      scoreDelta: result.scoreDelta,
      timestamp: Date.now()
    };
    DataStore.saveQuizRecord(record);
  }
}
