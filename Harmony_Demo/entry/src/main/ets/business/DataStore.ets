import { MasteryLevel, scoreToMasteryLevel } from '../model/MasteryLevel';
import { QuizRecord } from '../model/QuizRecord';
import { KnowledgeNode } from '../model/KnowledgeNode';

export class DataStore {
  private static masteryScore: number = 50;
  private static records: QuizRecord[] = [];

  static saveQuizRecord(record: QuizRecord): void {
    this.records.push(record);
    this.masteryScore = Math.max(0, Math.min(100, this.masteryScore + record.scoreDelta));
  }

  static getMasteryLevel(): MasteryLevel {
    return scoreToMasteryLevel(this.masteryScore);
  }

  static getRecords(): QuizRecord[] {
    return this.records;
  }

  static getKnowledgeNodes(): KnowledgeNode[] {
    const level = this.getMasteryLevel();
    return [
      { id: 'n1', name: '分布式基础', mastery: level, x: -1, y: 0, z: 0.5 },
      { id: 'n2', name: 'ArkUI 组件', mastery: level, x: 0, y: 0.8, z: -0.3 },
      { id: 'n3', name: '设备协同', mastery: level, x: 1, y: -0.2, z: 0.1 }
    ];
  }
}
