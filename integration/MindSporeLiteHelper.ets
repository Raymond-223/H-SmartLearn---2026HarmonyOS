import { MasteryLevel } from '../model/MasteryLevel';
import { QuizRecord } from '../model/QuizRecord';
import mindSpore from '@ohos.ai.mindSpore'; // 鸿蒙原生 AI SDK

/**
 * 鸿蒙能力集成层：MindSpore Lite 封装模块
 * 负责端侧 AI 模型的加载、内存管理及底层推理执行
 */
export class MindSporeLiteHelper {
  private static model: mindSpore.Model | null = null;
  private static isInitialized: boolean = false;

  /**
   * 初始化：加载 .ms 模型文件
   * @param modelPath 模型在资源文件夹中的路径
   */
  static async init(modelPath: string): Promise<boolean> {
    if (MindSporeLiteHelper.isInitialized) {
      return true;
    }

    try {
      // 1. 配置推理上下文，优先尝试使用 NPU (神经网络处理器)
      const context: mindSpore.Context = {
        target: ['cpu'], // MVP 阶段建议先用 CPU 确保兼容性，优化时可改为 'npu'
        cpu: {
          threadNum: 2,
          threadAffinityMode: 1
        }
      };

      // 2. 从指定路径加载模型
      // 注意：此处的 modelPath 需要对应 entry/src/main/resources/rawfile 里的路径
      MindSporeLiteHelper.model = await mindSpore.loadModelFromFile(modelPath, context);

      if (!MindSporeLiteHelper.model) {
        throw new Error('Model object is null after loading');
      }

      MindSporeLiteHelper.isInitialized = true;
      console.info('[Integration] MindSpore Lite 模型加载成功');
      return true;
    } catch (error) {
      console.error(`[Integration] MindSpore 初始化失败: ${JSON.stringify(error)}`);
      return false;
    }
  }

  /**
   * 执行推理：将答题记录转化为张量并获取掌握度
   * @param records 最近的答题历史记录
   */
  static async infer(records: QuizRecord[]): Promise<MasteryLevel[]> {
    if (!MindSporeLiteHelper.isInitialized || !MindSporeLiteHelper.model) {
      console.error('[Integration] 模型未初始化，无法推理');
      return [];
    }

    try {
      // 1. 获取模型输入张量
      const inputs = MindSporeLiteHelper.model.getInputs();
      if (!inputs || inputs.length === 0) {
        return [];
      }

      // 2. 数据预处理：将 QuizRecord 转化为模型认识的 Float32 数组
      // 假设模型输入 Shape 为 [1, 20]，我们需要提取 20 条记录的“正确性”得分
      const inputData = new Float32Array(20).fill(0);
      records.forEach((record, index) => {
        if (index < 20) {
          inputData[index] = record.correct ? 1.0 : 0.0;
        }
      });

      // 3. 将数据填充进输入张量
      inputs[0].setData(inputData.buffer);

      // 4. 执行推理并获取输出结果
      const outputs = await MindSporeLiteHelper.model.predict(inputs);

      // 5. 数据后处理：将输出 Tensor 转换回业务层的 MasteryLevel 数组
      // 假设模型输出的是对应节点的掌握度数值
      const outputBuffer = new Float32Array(outputs[0].getData());
      const masteryList: MasteryLevel[] = [];

      // 获取当前参与推理的节点 ID（从输入记录中提取去重）
      const nodeIds = Array.from(new Set(records.map(r => r.nodeId)));

      nodeIds.forEach((nodeId, index) => {
        if (index < outputBuffer.length) {
          masteryList.push({
            nodeId: nodeId,
            mastery: outputBuffer[index],
            updatedAt: Date.now()
          } as MasteryLevel);
        }
      });

      return masteryList;
    } catch (error) {
      console.error(`[Integration] 推理执行失败: ${JSON.stringify(error)}`);
      return [];
    }
  }

  /**
   * 资源释放：卸载模型，防止内存泄漏
   */
  static async release(): Promise<void> {
    if (MindSporeLiteHelper.model) {
      // 显式卸载模型，释放底层 C++ 资源
      MindSporeLiteHelper.model.unload();
      MindSporeLiteHelper.model = null;
      MindSporeLiteHelper.isInitialized = false;
      console.info('[Integration] MindSpore 模型已安全卸载');
    }
  }
}