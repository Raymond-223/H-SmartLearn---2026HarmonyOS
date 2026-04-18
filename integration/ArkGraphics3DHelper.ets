import { KnowledgeNode } from '../model/KnowledgeNode';
import { ColorUtil } from '../utils/ColorUtil';
// 导入鸿蒙原生 ArkGraphics 3D 引擎 API
import graphics3D from '@ohos.graphics.ark3D';

export class ArkGraphics3DHelper {
  // 维护底层的 3D 场景对象
  private static scene: graphics3D.Scene | null = null;
  // 维护底层的摄像机对象，用于处理手势缩放和旋转
  private static camera: graphics3D.Camera | null = null;
  // 核心：用字典（Map）保存知识点 ID 和底层 3D 节点对象的映射关系
  // 这样当业务层说“更新节点 A”时，我们能以 O(1) 的速度找到底层的 3D 实体
  private static nodeMap: Map<string, graphics3D.Node> = new Map();

  /**
   * 初始化 3D 场景
   * @param xComponentController UI 层传来的画布控制器
   */
  static async init(xComponentController: any): Promise<boolean> {
    try {
      // 1. 创建原生的 3D 场景
      ArkGraphics3DHelper.scene = await graphics3D.createScene();

      // 2. 将场景挂载到前端 UI 的 XComponent 画布上
      // 这一步是将底层 C++ 渲染管线与前端屏幕绑定的关键
      xComponentController.bindScene(ArkGraphics3DHelper.scene);

      // 3. 创建并设置主摄像机（视角）
      ArkGraphics3DHelper.camera = await ArkGraphics3DHelper.scene.createCamera();
      ArkGraphics3DHelper.camera.position = { x: 0, y: 10, z: 20 }; // 设置摄像机的初始空间位置
      ArkGraphics3DHelper.scene.addNode(ArkGraphics3DHelper.camera);

      console.info('[ArkGraphics3D] 3D 引擎初始化并挂载成功');
      return true;
    } catch (error) {
      console.error(`[ArkGraphics3D] 初始化失败: ${error}`);
      return false;
    }
  }

  /**
   * 根据知识点数据，在 3D 空间中批量生成实体节点
   * @param nodes 业务层 (GraphManager) 传来的知识点数组
   */
  static async buildGraph(nodes: KnowledgeNode[]): Promise<void> {
    if (!ArkGraphics3DHelper.scene) return;

    // 清空旧的缓存
    ArkGraphics3DHelper.nodeMap.clear();

    for (let i = 0; i < nodes.length; i++) {
      const nodeData = nodes[i];

      // 1. 在底层引擎中创建一个基础的 3D 几何体（比如球体，代表知识点）
      const geometry = await graphics3D.createGeometry(graphics3D.GeometryType.SPHERE);
      const node3D = await ArkGraphics3DHelper.scene.createNode(geometry);

      // 2. 空间排布算法：计算它在 3D 空间里的坐标 (x, y, z)
      // 这里用一个简单的环形排布算法示例
      const angle = (i / nodes.length) * Math.PI * 2;
      const radius = 5;
      node3D.position = {
        x: Math.cos(angle) * radius,
        y: nodeData.importance * 2, // 高度直接与重要性挂钩
        z: Math.sin(angle) * radius
      };

      // 3. 设置默认材质（颜色）
      const material = await graphics3D.createMaterial();
      material.baseColor = { r: 0.5, g: 0.5, b: 0.5, a: 1.0 }; // 默认灰色
      node3D.setMaterial(material);

      // 4. 将建好的 3D 实体添加到场景中
      ArkGraphics3DHelper.scene.addNode(node3D);

      // 5. 存入字典，方便后续业务层随时来修改它的颜色或高度
      ArkGraphics3DHelper.nodeMap.set(nodeData.id, node3D);
    }
    console.info(`[ArkGraphics3D] 成功构建图谱，共渲染 ${nodes.length} 个 3D 节点`);
  }

  /**
   * 更新节点颜色（响应掌握度变化）
   * @param nodeId 知识点 ID
   * @param mastery 业务层传来的新掌握度 (0~1)
   */
  static async updateNodeColor(nodeId: string, mastery: number): Promise<void> {
    const node3D = ArkGraphics3DHelper.nodeMap.get(nodeId);
    if (node3D) {
      // 1. 调用工具类，把 0.85 这种数字变成具体的 RGB 颜色
      const newColor = ColorUtil.masteryToColor(mastery);

      // 2. 修改底层材质属性
      const material = await node3D.getMaterial();
      // 假设 ColorUtil 返回的是 {r, g, b, a} 格式
      material.baseColor = newColor;
      node3D.setMaterial(material);
    }
  }

  /**
   * 更新节点高度（响应重要性或层级变化）
   */
  static async updateNodeHeight(nodeId: string, importance: number): Promise<void> {
    const node3D = ArkGraphics3DHelper.nodeMap.get(nodeId);
    if (node3D) {
      // 修改 3D 空间坐标的 Y 轴
      const currentPos = node3D.position;
      node3D.position = { x: currentPos.x, y: importance * 2, z: currentPos.z };
    }
  }

  /**
   * 处理用户的触屏手势（旋转、缩放）
   */
  static async handleGesture(deltaX: number, deltaY: number, scale: number): Promise<void> {
    if (ArkGraphics3DHelper.camera) {
      // 通过修改摄像机的位置或旋转角度，实现场景的交互游览
      ArkGraphics3DHelper.camera.rotate(deltaX * 0.01, deltaY * 0.01, 0);
      ArkGraphics3DHelper.camera.scale(scale, scale, scale);
    }
  }

  /**
   * 释放底层 3D 资源
   */
  static async clear(): Promise<void> {
    if (ArkGraphics3DHelper.scene) {
      ArkGraphics3DHelper.scene.destroy(); // 销毁底层 C++ 场景内存
      ArkGraphics3DHelper.scene = null;
      ArkGraphics3DHelper.camera = null;
      ArkGraphics3DHelper.nodeMap.clear();
      console.info('[ArkGraphics3D] 3D 场景内存已释放');
    }
  }
}