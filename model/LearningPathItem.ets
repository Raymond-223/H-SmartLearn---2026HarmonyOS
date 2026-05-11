export class LearningPathItem {
  nodeId: string;
  nodeName: string;
  reason: string;
  priority: number;
  mastery: number;
  importance: number;

  constructor(
    nodeId: string,
    nodeName: string,
    reason: string,
    priority: number,
    mastery: number,
    importance: number
  ) {
    this.nodeId = nodeId;
    this.nodeName = nodeName;
    this.reason = reason;
    this.priority = priority;
    this.mastery = mastery;
    this.importance = importance;
  }
}