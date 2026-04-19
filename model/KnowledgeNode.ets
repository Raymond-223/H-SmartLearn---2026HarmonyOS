export class KnowledgeNode {
  id: string;
  name: string;
  importance: number;
  parentIds: string[];
  childrenIds: string[];

  constructor(
    id: string,
    name: string,
    importance: number,
    parentIds: string[],
    childrenIds: string[]
  ) {
    this.id = id;
    this.name = name;
    this.importance = importance;
    this.parentIds = parentIds;
    this.childrenIds = childrenIds;
  }
}
