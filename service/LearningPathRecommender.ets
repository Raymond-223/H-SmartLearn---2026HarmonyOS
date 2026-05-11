import { KnowledgeNode } from '../model/KnowledgeNode'
import { MasteryLevel } from '../model/MasteryLevel'
import { LearningPathItem } from '../model/LearningPathItem'
import { cProgrammingKnowledgeNodes } from '../data/CProgrammingData'

class NodeRecommendScore {
  node: KnowledgeNode
  mastery: number
  score: number
  reason: string

  constructor(node: KnowledgeNode, mastery: number, score: number, reason: string) {
    this.node = node
    this.mastery = mastery
    this.score = score
    this.reason = reason
  }
}

function getMasteryByNodeId(nodeId: string, masteryLevels: MasteryLevel[]): number {
  for (let i = 0; i < masteryLevels.length; i++) {
    if (masteryLevels[i].nodeId === nodeId) {
      return masteryLevels[i].mastery
    }
  }

  return 0
}

function hasWeakParent(node: KnowledgeNode, masteryLevels: MasteryLevel[]): boolean {
  for (let i = 0; i < node.parentIds.length; i++) {
    let parentMastery: number = getMasteryByNodeId(node.parentIds[i], masteryLevels)

    if (parentMastery < 60) {
      return true
    }
  }

  return false
}

function buildRecommendReason(node: KnowledgeNode, mastery: number, weakParent: boolean): string {
  if (mastery < 40) {
    return '当前知识点掌握度较低，建议优先复习。'
  }

  if (weakParent) {
    return '该知识点存在前置基础薄弱的问题，建议结合前置知识一起学习。'
  }

  if (node.importance >= 5) {
    return '该知识点重要性较高，是后续学习的重要基础。'
  }

  return '该知识点仍有提升空间，建议继续巩固。'
}

function calculateRecommendScore(node: KnowledgeNode, mastery: number, weakParent: boolean): number {
  let score: number = 0

  score += 100 - mastery
  score += node.importance * 10

  if (weakParent) {
    score += 20
  }

  return score
}

export function generateLearningPath(
  nodes: KnowledgeNode[],
  masteryLevels: MasteryLevel[],
  maxCount: number
): LearningPathItem[] {
  let scores: NodeRecommendScore[] = []

  for (let i = 0; i < nodes.length; i++) {
    let node: KnowledgeNode = nodes[i]

    if (node.parentIds.length === 0) {
      continue
    }

    let mastery: number = getMasteryByNodeId(node.id, masteryLevels)

    if (mastery >= 85) {
      continue
    }

    let weakParent: boolean = hasWeakParent(node, masteryLevels)
    let score: number = calculateRecommendScore(node, mastery, weakParent)
    let reason: string = buildRecommendReason(node, mastery, weakParent)

    scores.push(new NodeRecommendScore(node, mastery, score, reason))
  }

  scores.sort((a: NodeRecommendScore, b: NodeRecommendScore) => {
    return b.score - a.score
  })

  let result: LearningPathItem[] = []
  let count: number = maxCount

  if (scores.length < maxCount) {
    count = scores.length
  }

  for (let i = 0; i < count; i++) {
    result.push(
      new LearningPathItem(
        scores[i].node.id,
        scores[i].node.name,
        scores[i].reason,
        i + 1,
        scores[i].mastery,
        scores[i].node.importance
      )
    )
  }

  return result
}

export function generateCProgrammingLearningPath(
  masteryLevels: MasteryLevel[]
): LearningPathItem[] {
  return generateLearningPath(cProgrammingKnowledgeNodes, masteryLevels, 5)
}