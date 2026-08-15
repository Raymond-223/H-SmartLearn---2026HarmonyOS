/** Minimal, privacy-aware state transferred by HarmonyOS continuation. */
export interface ContinuationSnapshot {
  page: string;
  learnerId: string;
  workflowId: string;
  resourceId: string;
}

export class ContinuationSession {
  private static snapshot: ContinuationSnapshot = {
    page: 'pages/Index',
    learnerId: '',
    workflowId: '',
    resourceId: '',
  };

  static update(page: string, learnerId: string = '', workflowId: string = '', resourceId: string = ''): void {
    ContinuationSession.snapshot = {
      page: page,
      learnerId: learnerId,
      workflowId: workflowId,
      resourceId: resourceId,
    };
  }

  static getSnapshot(): ContinuationSnapshot {
    return ContinuationSession.snapshot;
  }
}
