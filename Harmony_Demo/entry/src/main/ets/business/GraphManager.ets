import { DataStore } from './DataStore';
import { ColorUtil } from '../utils/ColorUtil';
import { KnowledgeNode } from '../model/KnowledgeNode';

export interface RenderNode {
  id: string;
  name: string;
  color: string;
  height: number;
}

export class GraphManager {
  private static renderNodes: RenderNode[] = [];

  static init(): void {
    this.refreshAll();
  }

  static refreshAll(): void {
    const nodes: KnowledgeNode[] = DataStore.getKnowledgeNodes();
    this.renderNodes = nodes.map((node) => ({
      id: node.id,
      name: node.name,
      color: ColorUtil.masteryToColor(node.mastery),
      height: node.mastery * 0.6
    }));
  }

  static getRenderNodes(): RenderNode[] {
    return this.renderNodes;
  }
}
