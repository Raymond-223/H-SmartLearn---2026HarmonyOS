import { KnowledgeNode } from '../model/KnowledgeNode';
import { DataStore } from './DataStore';
import { ArkGraphics3DHelper } from '../integration/ArkGraphics3DHelper';
import { JsonUtil } from '../utils/JsonUtil';

export class GraphManager {
  private static nodes: KnowledgeNode[] = [];

  private static initialized = false;

  static async init(): Promise<void> {
    if (GraphManager.initialized) {
      return;
    }

    const parsed = JsonUtil.parseGraph();
    GraphManager.nodes = await Promise.resolve(parsed) as KnowledgeNode[];

    await ArkGraphics3DHelper.buildGraph(GraphManager.nodes);

    DataStore.onMasteryChanged(async (nodeId: string, newMastery: number) => {
      await GraphManager.onMasteryChanged(nodeId, newMastery);
    });

    GraphManager.initialized = true;
  }

  static async refreshAll(): Promise<void> {
    const masteryMap = await DataStore.getAllMastery();

    for (const node of GraphManager.nodes) {
      const mastery = masteryMap.get(node.id) ?? 0;
      await ArkGraphics3DHelper.updateNodeColor(node.id, mastery);
      await ArkGraphics3DHelper.updateNodeHeight(node.id, node.importance);
    }
  }

  static async onMasteryChanged(nodeId: string, newMastery: number): Promise<void> {
    const node = GraphManager.nodes.find((item) => item.id === nodeId);
    if (!node) {
      return;
    }

    await ArkGraphics3DHelper.updateNodeColor(nodeId, newMastery);
    await ArkGraphics3DHelper.updateNodeHeight(nodeId, node.importance);
  }
}
