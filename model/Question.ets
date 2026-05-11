export class QuestionOption {
  key: string;
  text: string;

  constructor(key: string, text: string) {
    this.key = key;
    this.text = text;
  }
}

export class Question {
  id: string;
  nodeId: string;
  type: string;
  difficulty: number;
  stem: string;
  options: QuestionOption[];
  answer: string;
  explanation: string;

  constructor(
    id: string,
    nodeId: string,
    type: string,
    difficulty: number,
    stem: string,
    options: QuestionOption[],
    answer: string,
    explanation: string
  ) {
    this.id = id;
    this.nodeId = nodeId;
    this.type = type;
    this.difficulty = difficulty;
    this.stem = stem;
    this.options = options;
    this.answer = answer;
    this.explanation = explanation;
  }
}