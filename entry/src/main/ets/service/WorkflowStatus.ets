/** Central workflow-state contract shared by demo transport and UI. */
export enum WorkflowStatus {
  QUEUED = 'queued',
  ASSESSMENT_COMPLETED = 'ASSESSMENT_COMPLETED',
  DIAGNOSING = 'DIAGNOSING',
  PATH_PLANNING = 'PATH_PLANNING',
  RETRIEVING = 'RETRIEVING',
  GENERATING = 'GENERATING',
  REVIEWING = 'REVIEWING',
  REVISING = 'REVISING',
  PUBLISHED = 'PUBLISHED',
  FAILED = 'FAILED',
}

export class WorkflowStatusUtil {
  static isTerminal(status: WorkflowStatus): boolean {
    return status === WorkflowStatus.PUBLISHED || status === WorkflowStatus.FAILED;
  }

  static label(status: WorkflowStatus): string {
    switch (status) {
      case WorkflowStatus.QUEUED: return '任务已入队';
      case WorkflowStatus.ASSESSMENT_COMPLETED: return '诊断数据已锁定';
      case WorkflowStatus.DIAGNOSING: return '正在分析学情';
      case WorkflowStatus.PATH_PLANNING: return '正在规划路径';
      case WorkflowStatus.RETRIEVING: return '正在检索证据';
      case WorkflowStatus.GENERATING: return '正在生成资源';
      case WorkflowStatus.REVIEWING: return '正在审核内容';
      case WorkflowStatus.REVISING: return '正在定向修订';
      case WorkflowStatus.PUBLISHED: return '资源已发布';
      case WorkflowStatus.FAILED: return '执行失败';
      default: return '未知状态';
    }
  }

  static nextPollDelay(status: WorkflowStatus, failureCount: number): number {
    if (failureCount > 0) {
      return Math.min(15000, 1000 * Math.pow(2, Math.min(failureCount, 4)));
    }
    if (status === WorkflowStatus.GENERATING || status === WorkflowStatus.REVIEWING || status === WorkflowStatus.REVISING) {
      return 1500;
    }
    return 900;
  }
}
