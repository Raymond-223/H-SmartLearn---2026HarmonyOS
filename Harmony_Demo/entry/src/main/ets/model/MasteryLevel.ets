export enum MasteryLevel {
  LOW = 1,
  MEDIUM = 2,
  HIGH = 3
}

export function scoreToMasteryLevel(score: number): MasteryLevel {
  if (score >= 80) {
    return MasteryLevel.HIGH;
  }
  if (score >= 50) {
    return MasteryLevel.MEDIUM;
  }
  return MasteryLevel.LOW;
}
