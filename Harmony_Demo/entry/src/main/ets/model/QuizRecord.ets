export interface QuizRecord {
  questionId: string;
  answer: string;
  isCorrect: boolean;
  scoreDelta: number;
  timestamp: number;
}
