import { KnowledgeNode } from '../model/KnowledgeNode';
import { ColorUtil } from '../utils/ColorUtil';
import graphics3D from '@ohos.graphics.ark3D';

export class ArkGraphics3DHelper {
  private static scene: graphics3D.Scene | null = null;
  private static camera: graphics3D.Camera | null = null;
  private static nodeMap: Map<string, graphics3D.Node> = new Map();

  // 严格约定入参为 XComponentController
  static async init(xComponentController: XComponentController): Promise<boolean> {
    try {
      ArkGraphics3DHelper.scene = await graphics3D.createScene();
      // 绑定 UI 层的 XComponent 画布
      xComponentController.bindScene(ArkGraphics3DHelper.scene);

      ArkGraphics3DHelper.camera = await ArkGraphics3DHelper.scene.createCamera();
      ArkGraphics3DHelper.camera.position = { x: 0, y: 10, z: 20 };
      ArkGraphics3DHelper.scene.addNode(ArkGraphics3DHelper.camera);
      return true;
    } catch (error) {
      return false;
    }
  }

  static async buildGraph(nodes: KnowledgeNode[]): Promise<void> {
    if (!ArkGraphics3DHelper.scene) return;
    ArkGraphics3DHelper.nodeMap.clear();

    for (let i = 0; i < nodes.length; i++) {
      const nodeData = nodes[i];
      const geometry = await graphics3D.createGeometry(graphics3D.GeometryType.SPHERE);
      const node3D = await ArkGraphics3DHelper.scene.createNode(geometry);

      const angle = (i / nodes.length) * Math.PI * 2;
      const radius = 5;
      node3D.position = { x: Math.cos(angle) * radius, y: nodeData.importance * 2, z: Math.sin(angle) * radius };

      const material = await graphics3D.createMaterial();
      material.baseColor = { r: 0.5, g: 0.5, b: 0.5, a: 1.0 };
      node3D.setMaterial(material);

      ArkGraphics3DHelper.scene.addNode(node3D);
      ArkGraphics3DHelper.nodeMap.set(nodeData.id, node3D);
    }
  }

  static async updateNodeColor(nodeId: string, mastery: number): Promise<void> {
    const node3D = ArkGraphics3DHelper.nodeMap.get(nodeId);
    if (node3D) {
      const newColor = ColorUtil.masteryToColor(mastery);
      const material = await node3D.getMaterial();
      material.baseColor = newColor;
      node3D.setMaterial(material);
    }
  }

  static async updateNodeHeight(nodeId: string, importance: number): Promise<void> {
    const node3D = ArkGraphics3DHelper.nodeMap.get(nodeId);
    if (node3D) {
      const currentPos = node3D.position;
      node3D.position = { x: currentPos.x, y: importance * 2, z: currentPos.z };
    }
  }

  static async handleGesture(deltaX: number, deltaY: number, scale: number): Promise<void> {
    if (ArkGraphics3DHelper.camera) {
      ArkGraphics3DHelper.camera.rotate(deltaX * 0.01, deltaY * 0.01, 0);
      ArkGraphics3DHelper.camera.scale(scale, scale, scale);
    }
  }

  static async clear(): Promise<void> {
    if (ArkGraphics3DHelper.scene) {
      ArkGraphics3DHelper.scene.destroy();
      ArkGraphics3DHelper.scene = null;
      ArkGraphics3DHelper.camera = null;
      ArkGraphics3DHelper.nodeMap.clear();
    }
  }
}