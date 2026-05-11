import { KnowledgeNode } from '../model/KnowledgeNode'
import { MasteryLevel } from '../model/MasteryLevel'
import { Question } from '../model/Question'
import { QuizRecord } from '../model/QuizRecord'
import { LearningPathItem } from '../model/LearningPathItem'

import {
  cProgrammingKnowledgeNodes,
  cProgrammingQuestions,
  getInitialCProgrammingMasteryLevels,
  getCProgrammingQuestionsByNodeId
} from '../data/CProgrammingData'

import {
  updateMasteryByQuizRecord,
  updateMasteryByQuizRecords
} from './LearningProgressService'

import {
  generateCProgrammingLearningPath
} from './LearningPathRecommender'

export class CProgrammingLearningState {
  knowledgeNodes: KnowledgeNode[]
  questions: Question[]
  masteryLevels: MasteryLevel[]
  learningPath: LearningPathItem[]

  constructor(
    knowledgeNodes: KnowledgeNode[],
    questions: Question[],
    masteryLevels: MasteryLevel[],
    learningPath: LearningPathItem[]
  ) {
    this.knowledgeNodes = knowledgeNodes
    this.questions = questions
    this.masteryLevels = masteryLevels
    this.learningPath = learningPath
  }
}

export function getCProgrammingKnowledgeNodes(): KnowledgeNode[] {
  return cProgrammingKnowledgeNodes
}

export function getCProgrammingQuestions(): Question[] {
  return cProgrammingQuestions
}

export function getQuestionsByCProgrammingNodeId(nodeId: string): Question[] {
  return getCProgrammingQuestionsByNodeId(nodeId)
}

export function createInitialCProgrammingMasteryLevels(): MasteryLevel[] {
  return getInitialCProgrammingMasteryLevels()
}

export function submitCProgrammingAnswer(
  masteryLevels: MasteryLevel[],
  questionId: string,
  nodeId: string,
  correct: boolean
): MasteryLevel[] {
  let record: QuizRecord = new QuizRecord(
    questionId,
    nodeId,
    correct,
    new Date().getTime()
  )

  return updateMasteryByQuizRecord(masteryLevels, record)
}

export function submitCProgrammingQuizRecords(
  masteryLevels: MasteryLevel[],
  records: QuizRecord[]
): MasteryLevel[] {
  return updateMasteryByQuizRecords(masteryLevels, records)
}

export function getCProgrammingLearningPath(
  masteryLevels: MasteryLevel[]
): LearningPathItem[] {
  return generateCProgrammingLearningPath(masteryLevels)
}

export function buildDemoCProgrammingLearningState(): CProgrammingLearningState {
  let masteryLevels: MasteryLevel[] = getInitialCProgrammingMasteryLevels()
  let currentTime: number = new Date().getTime()

  let records: QuizRecord[] = [
    new QuizRecord('q_c_001', 'c_variable', true, currentTime),
    new QuizRecord('q_c_002', 'c_datatype', true, currentTime),
    new QuizRecord('q_c_003', 'c_operator', false, currentTime),
    new QuizRecord('q_c_006', 'c_array', false, currentTime),
    new QuizRecord('q_c_008', 'c_pointer', false, currentTime)
  ]

  masteryLevels = updateMasteryByQuizRecords(masteryLevels, records)

  let learningPath: LearningPathItem[] = generateCProgrammingLearningPath(masteryLevels)

  return new CProgrammingLearningState(
    cProgrammingKnowledgeNodes,
    cProgrammingQuestions,
    masteryLevels,
    learningPath
  )
}