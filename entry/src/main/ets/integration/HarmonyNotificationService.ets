/** Native Notification Kit integration for long-running Agent workflows. */
import { notificationManager } from '@kit.NotificationKit';
import { LogUtil } from '../utils/LogUtil';

const TAG: string = 'HarmonyNotificationService';
const WORKFLOW_NOTIFICATION_ID: number = 202630;

export class HarmonyNotificationService {
  static async publishWorkflowCompleted(resourceTitle: string): Promise<void> {
    const request: notificationManager.NotificationRequest = {
      id: WORKFLOW_NOTIFICATION_ID,
      content: {
        notificationContentType: notificationManager.ContentType.NOTIFICATION_CONTENT_BASIC_TEXT,
        normal: {
          title: 'H-SmartLearn · 资源已生成',
          text: resourceTitle || '多智能体审核已通过，点击应用继续学习',
          additionalText: 'HarmonyOS 智慧学习空间',
        },
      },
    };
    try {
      await notificationManager.publish(request);
    } catch (error) {
      LogUtil.warn(TAG, `Publish workflow notification failed: ${(error as Error).message}`);
    }
  }

  static async publishOfflineQueued(): Promise<void> {
    const request: notificationManager.NotificationRequest = {
      id: WORKFLOW_NOTIFICATION_ID + 1,
      content: {
        notificationContentType: notificationManager.ContentType.NOTIFICATION_CONTENT_BASIC_TEXT,
        normal: {
          title: '反馈已安全暂存',
          text: '网络恢复后将自动提交，不会丢失本次学习记录',
          additionalText: 'ArkData 离线队列',
        },
      },
    };
    try {
      await notificationManager.publish(request);
    } catch (error) {
      LogUtil.warn(TAG, `Publish offline-queue notification failed: ${(error as Error).message}`);
    }
  }
}
