import {
  cProgrammingKnowledgeNodes,
  cProgrammingQuestions,
  getDefaultCProgrammingLearningPath
} from '../data/CProgrammingData'
import { LearningPathItem } from '../model/LearningPathItem'
import { KnowledgeNode } from '../model/KnowledgeNode'
import { Question } from '../model/Question'


@Entry
@Component
struct Index {
  private learningPath: LearningPathItem[] = getDefaultCProgrammingLearningPath()

  build() {
    Scroll() {
      Column() {
        Text('H-SmartLearn')
          .fontSize(28)
          .fontWeight(FontWeight.Bold)
          .fontColor('#182431')
          .margin({ bottom: 8 })

        Text('C语言基础学习 Demo')
          .fontSize(18)
          .fontColor('#4E5969')
          .margin({ bottom: 20 })

        Row() {
          this.buildStatCard('知识点数量', cProgrammingKnowledgeNodes.length.toString())
          this.buildStatCard('题库数量', cProgrammingQuestions.length.toString())
        }
        .width('100%')
        .justifyContent(FlexAlign.SpaceBetween)
        .margin({ bottom: 20 })

        Text('知识图谱节点')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor('#182431')
          .width('100%')
          .margin({ bottom: 12 })

        ForEach(cProgrammingKnowledgeNodes, (node: KnowledgeNode) => {
          Column() {
            Row() {
              Text(node.name)
                .fontSize(16)
                .fontWeight(FontWeight.Bold)
                .fontColor('#182431')

              Text('重要度 ' + node.importance.toString())
                .fontSize(12)
                .fontColor('#FFFFFF')
                .backgroundColor('#317AF7')
                .borderRadius(10)
                .padding({
                  left: 8,
                  right: 8,
                  top: 3,
                  bottom: 3
                })
            }
            .width('100%')
            .justifyContent(FlexAlign.SpaceBetween)
            .margin({ bottom: 8 })

            Text('前置知识点：' + this.formatList(node.parentIds))
              .fontSize(13)
              .fontColor('#4E5969')
              .width('100%')
              .margin({ bottom: 4 })

            Text('后续知识点：' + this.formatList(node.childrenIds))
              .fontSize(13)
              .fontColor('#4E5969')
              .width('100%')
          }
          .width('100%')
          .padding(14)
          .backgroundColor('#FFFFFF')
          .borderRadius(12)
          .margin({ bottom: 10 })
        })

        Text('推荐学习路径')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor('#182431')
          .width('100%')
          .margin({ top: 16, bottom: 12 })

        ForEach(this.learningPath, (item: LearningPathItem) => {
          Row() {
            Text(item.priority.toString())
              .fontSize(16)
              .fontWeight(FontWeight.Bold)
              .fontColor('#FFFFFF')
              .width(32)
              .height(32)
              .textAlign(TextAlign.Center)
              .backgroundColor('#317AF7')
              .borderRadius(16)
              .margin({ right: 12 })

            Column() {
              Text(item.nodeName)
                .fontSize(16)
                .fontWeight(FontWeight.Bold)
                .fontColor('#182431')
                .width('100%')
                .margin({ bottom: 6 })

              Text(item.reason)
                .fontSize(13)
                .fontColor('#4E5969')
                .width('100%')

              Row() {
                Text('当前掌握度：' + item.mastery.toString())
                  .fontSize(12)
                  .fontColor('#86909C')

                Text('重要度：' + item.importance.toString())
                  .fontSize(12)
                  .fontColor('#86909C')
              }
              .width('100%')
              .justifyContent(FlexAlign.SpaceBetween)
              .margin({ top: 8 })
            }
            .layoutWeight(1)
          }
          .width('100%')
          .padding(14)
          .backgroundColor('#FFFFFF')
          .borderRadius(12)
          .margin({ bottom: 10 })
        })
        Text('题库样例')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor('#182431')
          .width('100%')
          .margin({ top: 16, bottom: 12 })

        ForEach(cProgrammingQuestions, (question: Question) => {
          Column() {
            Row() {
              Text(question.stem)
                .fontSize(15)
                .fontWeight(FontWeight.Bold)
                .fontColor('#182431')
                .layoutWeight(1)

              Text('难度 ' + question.difficulty.toString())
                .fontSize(12)
                .fontColor('#FFFFFF')
                .backgroundColor('#FF7D00')
                .borderRadius(10)
                .padding({
                  left: 8,
                  right: 8,
                  top: 3,
                  bottom: 3
                })
            }
            .width('100%')
            .margin({ bottom: 8 })

            Text('对应知识点：' + question.nodeId)
              .fontSize(13)
              .fontColor('#4E5969')
              .width('100%')
              .margin({ bottom: 4 })

            Text('正确答案：' + question.answer)
              .fontSize(13)
              .fontColor('#4E5969')
              .width('100%')
              .margin({ bottom: 4 })

            Text('解析：' + question.explanation)
              .fontSize(13)
              .fontColor('#86909C')
              .width('100%')
          }
          .width('100%')
          .padding(14)
          .backgroundColor('#FFFFFF')
          .borderRadius(12)
          .margin({ bottom: 10 })
        })
      }
      .width('100%')
      .padding(16)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F5F7FA')
  }

  @Builder
  buildStatCard(title: string, value: string) {
    Column() {
      Text(value)
        .fontSize(26)
        .fontWeight(FontWeight.Bold)
        .fontColor('#317AF7')
        .margin({ bottom: 6 })

      Text(title)
        .fontSize(14)
        .fontColor('#4E5969')
    }
    .width('48%')
    .padding(16)
    .backgroundColor('#FFFFFF')
    .borderRadius(14)
  }

  private formatList(list: string[]): string {
    if (list.length === 0) {
      return '无'
    }

    let result: string = ''
    for (let i = 0; i < list.length; i++) {
      result += list[i]
      if (i !== list.length - 1) {
        result += '、'
      }
    }
    return result
  }
}