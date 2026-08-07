/** Skill graph service. Formal mode is remote-only; local data is available only in explicit demo mode. */
import { ApiService, SkillGraphResponse, SkillGraphNodeDto, SkillGraphEdgeDto } from './ApiService';
import { DataStore } from '../business/DataStore';
import { LogUtil } from '../utils/LogUtil';

const TAG: string = 'SkillGraphService';

export interface SkillNode {
  id: string;
  name: string;
  difficulty: number;
  estimatedMinutes: number;
  objectives: string[];
  criteria: string[];
  mastery?: number;
}

export interface SkillEdge {
  from: string;
  to: string;
  relation: string;
}

export class SkillGraphService {
  private static nodes: SkillNode[] = [];
  private static edges: SkillEdge[] = [];
  private static loadedDomain: string = '';

  static async loadGraph(domainId: string, force: boolean = false, demoMode: boolean = false): Promise<void> {
    const cacheKey: string = `${demoMode ? 'demo' : 'remote'}:${domainId}`;
    if (!force && SkillGraphService.loadedDomain === cacheKey && SkillGraphService.nodes.length > 0) {
      return;
    }

    const api: ApiService = demoMode ? ApiService.createDemo() : new ApiService();
    try {
      const response: SkillGraphResponse = await api.getSkillGraph(domainId);
      SkillGraphService.nodes = response.nodes.map((item: SkillGraphNodeDto): SkillNode => {
        return {
          id: item.id,
          name: item.name,
          difficulty: item.difficulty,
          estimatedMinutes: item.estimated_minutes,
          objectives: item.objectives || [],
          criteria: item.criteria || [],
          mastery: 0,
        };
      });
      SkillGraphService.edges = response.edges.map((edge: SkillGraphEdgeDto): SkillEdge => {
        return {
          from: edge.from_skill_id || edge.from || '',
          to: edge.to_skill_id || edge.to || '',
          relation: edge.relation_type || edge.relation || 'prerequisite',
        };
      }).filter((edge: SkillEdge) => !!edge.from && !!edge.to);
    } catch (error) {
      SkillGraphService.nodes = [];
      SkillGraphService.edges = [];
      SkillGraphService.loadedDomain = '';
      const message: string = (error as Error).message || 'Unknown error';
      LogUtil.error(TAG, `Graph load failed: ${message}`);
      throw new Error(`Graph load failed: ${message}`);
    }

    if (!demoMode) {
      const masteryMap = await DataStore.getAllMastery();
      for (const node of SkillGraphService.nodes) {
        node.mastery = masteryMap.get(node.id) ?? 0;
      }
    }
    SkillGraphService.loadedDomain = cacheKey;
  }

  static getNodes(): SkillNode[] {
    return SkillGraphService.nodes;
  }

  static getEdges(): SkillEdge[] {
    return SkillGraphService.edges;
  }

  static getPrerequisites(skillId: string): SkillNode[] {
    const ids = SkillGraphService.edges
      .filter((edge: SkillEdge) => edge.to === skillId && edge.relation === 'prerequisite')
      .map((edge: SkillEdge) => edge.from);
    return SkillGraphService.nodes.filter((node: SkillNode) => ids.includes(node.id));
  }

  static getDependents(skillId: string): SkillNode[] {
    const ids = SkillGraphService.edges
      .filter((edge: SkillEdge) => edge.from === skillId && edge.relation === 'prerequisite')
      .map((edge: SkillEdge) => edge.to);
    return SkillGraphService.nodes.filter((node: SkillNode) => ids.includes(node.id));
  }

  static getLearningPath(): string[] {
    const visited = new Set<string>();
    const visiting = new Set<string>();
    const path: string[] = [];
    const visit = (nodeId: string): void => {
      if (visited.has(nodeId)) return;
      if (visiting.has(nodeId)) {
        throw new Error(`技能图谱存在循环依赖：${nodeId}`);
      }
      visiting.add(nodeId);
      for (const prerequisite of SkillGraphService.getPrerequisites(nodeId)) {
        visit(prerequisite.id);
      }
      visiting.delete(nodeId);
      visited.add(nodeId);
      path.push(nodeId);
    };
    const orderedNodes: SkillNode[] = SkillGraphService.nodes.slice().sort((left: SkillNode, right: SkillNode): number => {
      if (left.difficulty !== right.difficulty) return left.difficulty - right.difficulty;
      return left.id.localeCompare(right.id);
    });
    for (const node of orderedNodes) {
      visit(node.id);
    }
    return path;
  }
}
