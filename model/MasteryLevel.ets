export class MasteryLevel {
  nodeId: string;
  mastery: number;
  lastUpdateTime: number;

  constructor(
    nodeId: string,
    mastery: number,
    lastUpdateTime: number
  ) {
    this.nodeId = nodeId;
    this.mastery = mastery;
    this.lastUpdateTime = lastUpdateTime;
  }
}
