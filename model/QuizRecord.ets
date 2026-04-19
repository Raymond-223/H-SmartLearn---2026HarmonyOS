export class QuizRecord {
  questionId: string;
  nodeId: string;
  correct: boolean;
  timestamp: number;

  constructor(
    questionId: string,
    nodeId: string,
    correct: boolean,
    timestamp: number
  ) {
    this.questionId = questionId;
    this.nodeId = nodeId;
    this.correct = correct;
    this.timestamp = timestamp;
  }
}
