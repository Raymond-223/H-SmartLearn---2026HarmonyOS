import { MasteryLevel } from '../model/MasteryLevel'
import { QuizRecord } from '../model/QuizRecord'

function limitMastery(value: number): number {
  if (value < 0) {
    return 0
  }

  if (value > 100) {
    return 100
  }

  return value
}

function getMasteryIndex(nodeId: string, masteryLevels: MasteryLevel[]): number {
  for (let i = 0; i < masteryLevels.length; i++) {
    if (masteryLevels[i].nodeId === nodeId) {
      return i
    }
  }

  return -1
}

export function updateMasteryByQuizRecord(
  masteryLevels: MasteryLevel[],
  record: QuizRecord
): MasteryLevel[] {
  let result: MasteryLevel[] = []

  for (let i = 0; i < masteryLevels.length; i++) {
    result.push(
      new MasteryLevel(
        masteryLevels[i].nodeId,
        masteryLevels[i].mastery,
        masteryLevels[i].lastUpdateTime
      )
    )
  }

  let index: number = getMasteryIndex(record.nodeId, result)
  let currentTime: number = new Date().getTime()

  if (index === -1) {
    let initialMastery: number = 0

    if (record.correct) {
      initialMastery = 15
    }

    result.push(new MasteryLevel(record.nodeId, initialMastery, currentTime))
    return result
  }

  let oldMastery: number = result[index].mastery
  let newMastery: number = oldMastery

  if (record.correct) {
    newMastery = oldMastery + 10
  } else {
    newMastery = oldMastery - 5
  }

  result[index] = new MasteryLevel(
    record.nodeId,
    limitMastery(newMastery),
    currentTime
  )

  return result
}

export function updateMasteryByQuizRecords(
  masteryLevels: MasteryLevel[],
  records: QuizRecord[]
): MasteryLevel[] {
  let result: MasteryLevel[] = masteryLevels

  for (let i = 0; i < records.length; i++) {
    result = updateMasteryByQuizRecord(result, records[i])
  }

  return result
}

export function calculateCorrectRateByNodeId(
  nodeId: string,
  records: QuizRecord[]
): number {
  let total: number = 0
  let correctCount: number = 0

  for (let i = 0; i < records.length; i++) {
    if (records[i].nodeId === nodeId) {
      total++

      if (records[i].correct) {
        correctCount++
      }
    }
  }

  if (total === 0) {
    return 0
  }

  return correctCount / total
}