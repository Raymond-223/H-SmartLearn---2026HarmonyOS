import { MasteryLevel } from '../model/MasteryLevel';
import { QuizRecord } from '../model/QuizRecord';
import mindSpore from '@ohos.ai.mindSpore';

export class MindSporeLiteHelper {
  private static model: mindSpore.Model | null = null;
  private static isInitialized: boolean = false;

  static async init(modelPath: string): Promise<boolean> {
    if (MindSporeLiteHelper.isInitialized) return true;

    try {
      const context: mindSpore.Context = { target: ['cpu'], cpu: { threadNum: 2, threadAffinityMode: 1 } };
      MindSporeLiteHelper.model = await mindSpore.loadModelFromFile(modelPath, context);

      if (!MindSporeLiteHelper.model) throw new Error('Model obj is null');

      MindSporeLiteHelper.isInitialized = true;
      return true;
    } catch (error) {
      return false;
    }
  }

  static async infer(records: QuizRecord[]): Promise<MasteryLevel[]> {
    if (!MindSporeLiteHelper.isInitialized || !MindSporeLiteHelper.model) return [];

    try {
      const inputs = MindSporeLiteHelper.model.getInputs();
      if (!inputs || inputs.length === 0) return [];

      // 数据降维：业务层对象 -> 底层 Float32 张量
      const inputData = new Float32Array(20).fill(0);
      records.forEach((record, index) => {
        if (index < 20) inputData[index] = record.correct ? 1.0 : 0.0;
      });

      inputs[0].setData(inputData.buffer);
      const outputs = await MindSporeLiteHelper.model.predict(inputs);

      const outputBuffer = new Float32Array(outputs[0].getData());
      const masteryList: MasteryLevel[] = [];
      const nodeIds = Array.from(new Set(records.map(r => r.nodeId)));

      // 组装业务层所需的数据结构并返回
      nodeIds.forEach((nodeId, index) => {
        if (index < outputBuffer.length) {
          masteryList.push({ nodeId: nodeId, mastery: outputBuffer[index], updatedAt: Date.now() } as MasteryLevel);
        }
      });

      return masteryList;
    } catch (error) {
      return [];
    }
  }

  static async release(): Promise<void> {
    if (MindSporeLiteHelper.model) {
      MindSporeLiteHelper.model.unload();
      MindSporeLiteHelper.model = null;
      MindSporeLiteHelper.isInitialized = false;
    }
  }
}