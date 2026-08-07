import { AbilityConstant, ConfigurationConstant, UIAbility, Want } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { window } from '@kit.ArkUI';
import { DataStore } from '../business/DataStore';
import { ContinuationSession, ContinuationSnapshot } from '../integration/ContinuationSession';

const DOMAIN = 0x0000;
const DEFAULT_PAGE: string = 'pages/Index';

export default class EntryAbility extends UIAbility {
  private launchPage: string = DEFAULT_PAGE;
  private continuationLearnerId: string = '';
  private continuationWorkflowId: string = '';
  private continuationResourceId: string = '';

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    try {
      this.context.getApplicationContext().setColorMode(ConfigurationConstant.ColorMode.COLOR_MODE_NOT_SET);
    } catch (err) {
      hilog.error(DOMAIN, 'SmartLearn', 'Failed to set colorMode. Cause: %{public}s', JSON.stringify(err));
    }

    DataStore.init(this.context);
    const params = want.parameters;
    if (params !== undefined) {
      const continuedPage = params['continuationPage'];
      const learnerId = params['learnerId'];
      const workflowId = params['workflowId'];
      const resourceId = params['resourceId'];
      if (typeof continuedPage === 'string' && continuedPage.startsWith('pages/')) {
        this.launchPage = continuedPage;
      }
      if (typeof learnerId === 'string' && learnerId.length > 0) {
        this.continuationLearnerId = learnerId;
      }
      if (typeof workflowId === 'string' && workflowId.length > 0) {
        this.continuationWorkflowId = workflowId;
      }
      if (typeof resourceId === 'string' && resourceId.length > 0) {
        this.continuationResourceId = resourceId;
      }
    }
    hilog.info(DOMAIN, 'SmartLearn', 'Ability created, continuation=%{public}s', this.launchPage);
  }

  onContinue(wantParam: Record<string, Object>): AbilityConstant.OnContinueResult {
    const snapshot: ContinuationSnapshot = ContinuationSession.getSnapshot();
    wantParam['continuationPage'] = snapshot.page;
    wantParam['learnerId'] = snapshot.learnerId;
    wantParam['workflowId'] = snapshot.workflowId;
    wantParam['resourceId'] = snapshot.resourceId;
    hilog.info(DOMAIN, 'SmartLearn', 'Continuation prepared for %{public}s', snapshot.page);
    return AbilityConstant.OnContinueResult.AGREE;
  }

  onDestroy(): void {
    hilog.info(DOMAIN, 'SmartLearn', 'Ability onDestroy');
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    this.restoreContinuationAndLoad(windowStage);
  }

  private async restoreContinuationAndLoad(windowStage: window.WindowStage): Promise<void> {
    try {
      if (this.continuationLearnerId.length > 0) {
        await DataStore.saveLearnerId(this.continuationLearnerId);
      }
      if (this.continuationWorkflowId.length > 0) {
        await DataStore.saveLastWorkflowId(this.continuationWorkflowId);
      }
      if (this.continuationResourceId.length > 0) {
        await DataStore.saveLastResourceId(this.continuationResourceId);
      }
    } catch (error) {
      hilog.error(DOMAIN, 'SmartLearn', 'Failed to restore continuation state: %{public}s', JSON.stringify(error));
      this.launchPage = DEFAULT_PAGE;
    }
    windowStage.loadContent(this.launchPage, (err) => {
      if (err.code) {
        hilog.error(DOMAIN, 'SmartLearn', 'Failed to load content. Cause: %{public}s', JSON.stringify(err));
        return;
      }
      hilog.info(DOMAIN, 'SmartLearn', 'Loaded %{public}s', this.launchPage);
    });
  }

  onWindowStageDestroy(): void {
    hilog.info(DOMAIN, 'SmartLearn', 'Ability onWindowStageDestroy');
  }

  onForeground(): void {
    hilog.info(DOMAIN, 'SmartLearn', 'Ability onForeground');
  }

  onBackground(): void {
    hilog.info(DOMAIN, 'SmartLearn', 'Ability onBackground');
  }
}
