/**
 * ArkData RDB cache for resilient HarmonyOS learning sessions.
 * The backend remains the source of truth; this database only stores retryable
 * actions and presentation snapshots.
 */
import { relationalStore } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';
import { LogUtil } from '../utils/LogUtil';

const TAG: string = 'LearningCacheDatabase';

const DB_NAME: string = 'smartlearn_cache.db';
const ACTION_TABLE: string = 'offline_actions';
const SNAPSHOT_TABLE: string = 'workflow_snapshots';

export interface OfflineActionRecord {
  id: number;
  actionType: string;
  payload: string;
  createdAt: number;
}

export interface WorkflowSnapshotRecord {
  workflowId: string;
  status: string;
  progress: number;
  resourceId: string;
  updatedAt: number;
}

export class LearningCacheDatabase {
  private static context: common.Context | null = null;
  private static store: relationalStore.RdbStore | null = null;

  static init(context: common.Context): void {
    LearningCacheDatabase.context = context;
  }

  private static message(error: Object): string {
    return (error as Error).message || 'Unknown ArkData error';
  }

  private static async getStore(): Promise<relationalStore.RdbStore> {
    if (LearningCacheDatabase.store !== null) {
      return LearningCacheDatabase.store;
    }
    if (LearningCacheDatabase.context === null) {
      throw new Error('LearningCacheDatabase is not initialized');
    }
    const config: relationalStore.StoreConfig = {
      name: DB_NAME,
      securityLevel: relationalStore.SecurityLevel.S2,
    };
    try {
      const store: relationalStore.RdbStore =
        await relationalStore.getRdbStore(LearningCacheDatabase.context, config);
      await store.executeSql(
        `CREATE TABLE IF NOT EXISTS ${ACTION_TABLE} (` +
        'id INTEGER PRIMARY KEY AUTOINCREMENT, action_type TEXT NOT NULL, payload TEXT NOT NULL, ' +
        "status TEXT NOT NULL DEFAULT 'pending', created_at INTEGER NOT NULL)"
      );
      await store.executeSql(
        `CREATE TABLE IF NOT EXISTS ${SNAPSHOT_TABLE} (` +
        'workflow_id TEXT PRIMARY KEY, status TEXT NOT NULL, progress INTEGER NOT NULL, ' +
        'resource_id TEXT NOT NULL, updated_at INTEGER NOT NULL)'
      );
      LearningCacheDatabase.store = store;
      return store;
    } catch (error) {
      LearningCacheDatabase.store = null;
      const message: string = LearningCacheDatabase.message(error as Object);
      LogUtil.error(TAG, `Database initialization failed: ${message}`);
      throw new Error(`Learning cache database unavailable: ${message}`);
    }
  }

  static async enqueueAction(actionType: string, payload: string): Promise<void> {
    try {
      const store: relationalStore.RdbStore = await LearningCacheDatabase.getStore();
      const values: relationalStore.ValuesBucket = {
        'action_type': actionType,
        'payload': payload,
        'status': 'pending',
        'created_at': Date.now(),
      };
      await store.insert(ACTION_TABLE, values);
    } catch (error) {
      const message: string = LearningCacheDatabase.message(error as Object);
      LogUtil.error(TAG, `Enqueue offline action failed: ${message}`);
      throw new Error(`Unable to enqueue offline action: ${message}`);
    }
  }

  static async listPendingActions(actionType: string = ''): Promise<OfflineActionRecord[]> {
    try {
      const store: relationalStore.RdbStore = await LearningCacheDatabase.getStore();
      let predicates: relationalStore.RdbPredicates =
        new relationalStore.RdbPredicates(ACTION_TABLE).equalTo('status', 'pending');
      if (actionType.length > 0) {
        predicates = predicates.equalTo('action_type', actionType);
      }
      predicates.orderByAsc('created_at');
      const resultSet: relationalStore.ResultSet =
        await store.query(predicates, ['id', 'action_type', 'payload', 'created_at']);
      const actions: OfflineActionRecord[] = [];
      try {
        while (resultSet.goToNextRow()) {
          const idColumn: number = resultSet.getColumnIndex('id');
          const actionTypeColumn: number = resultSet.getColumnIndex('action_type');
          const payloadColumn: number = resultSet.getColumnIndex('payload');
          const createdAtColumn: number = resultSet.getColumnIndex('created_at');
          actions.push({
            id: resultSet.getLong(idColumn),
            actionType: resultSet.getString(actionTypeColumn),
            payload: resultSet.getString(payloadColumn),
            createdAt: resultSet.getLong(createdAtColumn),
          });
        }
      } catch (error) {
        const message: string = LearningCacheDatabase.message(error as Object);
        LogUtil.error(TAG, `Read offline actions failed: ${message}`);
        throw new Error(`Unable to read offline actions: ${message}`);
      } finally {
        try {
          resultSet.close();
        } catch (error) {
          LogUtil.warn(TAG, `Closing offline action result set failed: ${LearningCacheDatabase.message(error as Object)}`);
        }
      }
      return actions;
    } catch (error) {
      const message: string = LearningCacheDatabase.message(error as Object);
      LogUtil.error(TAG, `List pending actions failed: ${message}`);
      throw new Error(`Unable to list pending actions: ${message}`);
    }
  }

  static async deleteAction(id: number): Promise<void> {
    try {
      const store: relationalStore.RdbStore = await LearningCacheDatabase.getStore();
      const predicates: relationalStore.RdbPredicates =
        new relationalStore.RdbPredicates(ACTION_TABLE).equalTo('id', id);
      await store.delete(predicates);
    } catch (error) {
      const message: string = LearningCacheDatabase.message(error as Object);
      LogUtil.error(TAG, `Delete offline action failed: ${message}`);
      throw new Error(`Unable to delete offline action: ${message}`);
    }
  }

  static async clearActions(actionType: string = ''): Promise<void> {
    try {
      const store: relationalStore.RdbStore = await LearningCacheDatabase.getStore();
      let predicates: relationalStore.RdbPredicates = new relationalStore.RdbPredicates(ACTION_TABLE);
      if (actionType.length > 0) {
        predicates = predicates.equalTo('action_type', actionType);
      }
      await store.delete(predicates);
    } catch (error) {
      const message: string = LearningCacheDatabase.message(error as Object);
      LogUtil.error(TAG, `Clear offline actions failed: ${message}`);
      throw new Error(`Unable to clear offline actions: ${message}`);
    }
  }

  static async saveWorkflowSnapshot(snapshot: WorkflowSnapshotRecord): Promise<void> {
    try {
      const store: relationalStore.RdbStore = await LearningCacheDatabase.getStore();
      const values: relationalStore.ValuesBucket = {
        'workflow_id': snapshot.workflowId,
        'status': snapshot.status,
        'progress': snapshot.progress,
        'resource_id': snapshot.resourceId,
        'updated_at': snapshot.updatedAt,
      };
      const predicates: relationalStore.RdbPredicates =
        new relationalStore.RdbPredicates(SNAPSHOT_TABLE).equalTo('workflow_id', snapshot.workflowId);
      await store.delete(predicates);
      await store.insert(SNAPSHOT_TABLE, values);
    } catch (error) {
      const message: string = LearningCacheDatabase.message(error as Object);
      LogUtil.error(TAG, `Save workflow snapshot failed: ${message}`);
      throw new Error(`Unable to save workflow snapshot: ${message}`);
    }
  }

  static async getWorkflowSnapshot(workflowId: string): Promise<WorkflowSnapshotRecord | null> {
    try {
      const store: relationalStore.RdbStore = await LearningCacheDatabase.getStore();
      const predicates: relationalStore.RdbPredicates =
        new relationalStore.RdbPredicates(SNAPSHOT_TABLE).equalTo('workflow_id', workflowId);
      const resultSet: relationalStore.ResultSet = await store.query(predicates);
      try {
        if (!resultSet.goToFirstRow()) {
          return null;
        }
        const workflowIdColumn: number = resultSet.getColumnIndex('workflow_id');
        const statusColumn: number = resultSet.getColumnIndex('status');
        const progressColumn: number = resultSet.getColumnIndex('progress');
        const resourceIdColumn: number = resultSet.getColumnIndex('resource_id');
        const updatedAtColumn: number = resultSet.getColumnIndex('updated_at');
        return {
          workflowId: resultSet.getString(workflowIdColumn),
          status: resultSet.getString(statusColumn),
          progress: resultSet.getLong(progressColumn),
          resourceId: resultSet.getString(resourceIdColumn),
          updatedAt: resultSet.getLong(updatedAtColumn),
        };
      } catch (error) {
        const message: string = LearningCacheDatabase.message(error as Object);
        LogUtil.error(TAG, `Read workflow snapshot failed: ${message}`);
        throw new Error(`Unable to read workflow snapshot: ${message}`);
      } finally {
        try {
          resultSet.close();
        } catch (error) {
          LogUtil.warn(TAG, `Closing workflow snapshot result set failed: ${LearningCacheDatabase.message(error as Object)}`);
        }
      }
    } catch (error) {
      const message: string = LearningCacheDatabase.message(error as Object);
      LogUtil.error(TAG, `Get workflow snapshot failed: ${message}`);
      throw new Error(`Unable to get workflow snapshot: ${message}`);
    }
  }

  static async clearAll(): Promise<void> {
    try {
      await LearningCacheDatabase.clearActions();
      const store: relationalStore.RdbStore = await LearningCacheDatabase.getStore();
      const predicates: relationalStore.RdbPredicates = new relationalStore.RdbPredicates(SNAPSHOT_TABLE);
      await store.delete(predicates);
    } catch (error) {
      const message: string = LearningCacheDatabase.message(error as Object);
      LogUtil.error(TAG, `Clear learning cache failed: ${message}`);
      throw new Error(`Unable to clear learning cache: ${message}`);
    }
  }
}
