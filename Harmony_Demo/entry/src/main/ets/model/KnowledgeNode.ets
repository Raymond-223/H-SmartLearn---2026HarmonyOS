import { MasteryLevel } from './MasteryLevel';

export interface KnowledgeNode {
  id: string;
  name: string;
  mastery: MasteryLevel;
  x: number;
  y: number;
  z: number;
}
