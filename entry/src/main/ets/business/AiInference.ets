import { QuizRecord } from '../model/QuizRecord';
import { DataStore } from './DataStore';
import { MindSporeLiteHelper } from '../integration/MindSporeLiteHelper';

export class AiInference {
  static async processAnswer(questionId: string, nodeId: string, correct: boolean): Promise<void> {
    const record = {
      questionId,
      nodeId,
      correct,
      timestamp: Date.now(),
    } as QuizRecord;

    await DataStore.addQuizRecord(record);

    const history = await DataStore.getRecentRecords(20);
    const masteryList = await MindSporeLiteHelper.infer(history);

    await DataStore.saveMasteryList(masteryList);
  }
}
