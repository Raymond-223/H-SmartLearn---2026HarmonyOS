/**
 * Embedded deterministic demo engine.
 *
 * The demo executes the same user-visible loop as the remote backend: profile-aware
 * assessment, target-skill workflow, interactive resource, feedback decision and
 * a real follow-up workflow. Public payloads cross the ArkTS boundary through JSON
 * parsing so strict static typing does not rely on anonymous object literals.
 */
import http from '@ohos.net.http';
import { LogUtil } from '../utils/LogUtil';
import { WorkflowStatus } from './WorkflowStatus';

const TAG: string = 'DemoBackend';

class DemoOption {
  key: string = '';
  text: string = '';
}

class DemoQuestionRecord {
  item_id: string = '';
  skill_id: string = '';
  type: string = '';
  difficulty: number = 1;
  stem: string = '';
  options: DemoOption[] = [];
  correct_answer: string = '';
  explanation: string = '';
}


class DemoPublicQuestion {
  item_id: string;
  skill_id: string;
  type: string;
  difficulty: number;
  stem: string;
  options: DemoOption[];

  constructor(question: DemoQuestionRecord) {
    this.item_id = question.item_id;
    this.skill_id = question.skill_id;
    this.type = question.type;
    this.difficulty = question.difficulty;
    this.stem = question.stem;
    this.options = question.options;
  }
}

class DemoAnswerItem {
  item_id: string = '';
  answer: string = '';
}

class DemoGradedTestItem {
  id: string = '';
  skill_id: string = '';
  options: DemoOption[] = [];
  correct_answer: string = '';
  explanation: string = '';
}

class DemoPracticeResult {
  order: number = 0;
  success: boolean = false;
}

class DemoAssessmentResultItem {
  item_id: string;
  skill_id: string;
  stem: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  explanation: string;
  error_tags: string[];

  constructor(question: DemoQuestionRecord, userAnswer: string) {
    this.item_id = question.item_id;
    this.skill_id = question.skill_id;
    this.stem = question.stem;
    this.user_answer = userAnswer;
    this.correct_answer = question.correct_answer;
    this.is_correct = userAnswer === question.correct_answer;
    this.explanation = question.explanation;
    this.error_tags = this.is_correct ? [] : [question.skill_id];
  }
}

class DemoWorkflowData {
  workflowId: string;
  learnerId: string;
  domainId: string;
  profileId: string;
  targetSkillId: string;
  resourceId: string;
  requestedDifficulty: string;
  phaseIndex: number;

  constructor(workflowId: string, learnerId: string, domainId: string,
    profileId: string, targetSkillId: string, resourceId: string, requestedDifficulty: string) {
    this.workflowId = workflowId;
    this.learnerId = learnerId;
    this.domainId = domainId;
    this.profileId = profileId;
    this.targetSkillId = targetSkillId;
    this.resourceId = resourceId;
    this.requestedDifficulty = requestedDifficulty;
    this.phaseIndex = 0;
  }
}

class DemoSnapshotResult {
  status: Object;
  trace: Object;

  constructor(status: Object, trace: Object) {
    this.status = status;
    this.trace = trace;
  }
}

class DemoPracticeSpec {
  title: string;
  command: string;
  expected: string;

  constructor(title: string, command: string, expected: string) {
    this.title = title;
    this.command = command;
    this.expected = expected;
  }
}

class DemoMasteryRow {
  skill_id: string = '';
  name: string = '';
  score: number = 0;
  confidence: number = 0;
  difficulty: number = 1;
}

class DemoLearningPathRow {
  order: number = 0;
  skill_id: string = '';
  name: string = '';
  estimated_minutes: number = 0;
  mastery: number = 0;
}

class DemoDifficultyRow {
  label: string;
  score: number;
  skill_count: number;

  constructor(label: string, score: number, skillCount: number) {
    this.label = label;
    this.score = score;
    this.skill_count = skillCount;
  }
}

class DemoProgressRow {
  timestamp: string;
  event_type: string;
  label: string;
  score: number;
  skill_id?: string;

  constructor(eventType: string, label: string, score: number, skillId?: string) {
    this.timestamp = new Date().toISOString();
    this.event_type = eventType;
    this.label = label;
    this.score = score;
    this.skill_id = skillId;
  }
}

class DemoReportPayload {
  learner_id: string = '';
  overall_mastery: number = 0;
  domain: string = '';
  skill_mastery: DemoMasteryRow[] = [];
  knowledge_gaps: string[] = [];
  strengths: string[] = [];
  difficulty_curve: DemoDifficultyRow[] = [];
  learning_path: DemoLearningPathRow[] = [];
  progress_history: DemoProgressRow[] = [];
  recommended_resources: string[] = [];
}

class DemoRequestBody {
  learner_id?: string;
  domain_id?: string;
  assessment_id?: string;
  target_goal?: string;
  target_skill_id?: string;
  requested_difficulty?: string;
  version_filter?: string;
  education?: string;
  major?: string;
  weekly_hours?: number;
  answers?: DemoAnswerItem[];
  correct_rate?: number;
  practice_score?: number;
  practice_results?: DemoPracticeResult[];
  subjective_difficulty?: string;
  error_tags?: string[];
}
const ROS2_QUESTIONS_JSON: string = `[{"skill_id":"linux_environment","type":"single_choice","difficulty":1,"stem":"新终端使用ROS2 Humble命令前通常应执行什么？","options":[{"key":"A","text":"source /opt/ros/humble/setup.bash"},{"key":"B","text":"删除工作空间"},{"key":"C","text":"关闭网络"},{"key":"D","text":"修改内核"}],"correct_answer":"A","explanation":"每个新终端都需要加载ROS2环境。","item_id":"ros_q_001"},{"skill_id":"ros2_node","type":"single_choice","difficulty":1,"stem":"ROS2图中承担单一模块职责的基本实体是什么？","options":[{"key":"A","text":"节点"},{"key":"B","text":"图片"},{"key":"C","text":"数据库表"},{"key":"D","text":"压缩包"}],"correct_answer":"A","explanation":"节点是ROS2图中执行计算并通过接口协作的基本实体。","item_id":"ros_q_002"},{"skill_id":"ros2_topic","type":"single_choice","difficulty":2,"stem":"Topic通信使用哪种模式？","options":[{"key":"A","text":"发布-订阅"},{"key":"B","text":"文件锁"},{"key":"C","text":"远程桌面"},{"key":"D","text":"数据库事务"}],"correct_answer":"A","explanation":"Topic通过Publisher和Subscriber实现异步通信。","item_id":"ros_q_003"},{"skill_id":"ros2_topic_custom","type":"single_choice","difficulty":2,"stem":"ROS2自定义消息通常使用哪种文件？","options":[{"key":"A","text":".css"},{"key":"B","text":".msg"},{"key":"C","text":".sql"},{"key":"D","text":".apk"}],"correct_answer":"B","explanation":"消息接口使用.msg文件定义。","item_id":"ros_q_004"},{"skill_id":"ros2_service","type":"single_choice","difficulty":2,"stem":"Service最适合哪种交互？","options":[{"key":"A","text":"连续高速传感器流"},{"key":"B","text":"短时请求-响应"},{"key":"C","text":"视频存档"},{"key":"D","text":"永久共享内存"}],"correct_answer":"B","explanation":"Service适合需要明确返回结果的短时请求响应。","item_id":"ros_q_005"},{"skill_id":"ros2_tf2","type":"single_choice","difficulty":3,"stem":"持续查询map到base_link变换常用哪条命令？","options":[{"key":"A","text":"ros2 topic list map base_link"},{"key":"B","text":"ros2 run tf2_ros tf2_echo map base_link"},{"key":"C","text":"colcon tf map"},{"key":"D","text":"ros2 service delete tf"}],"correct_answer":"B","explanation":"tf2_echo持续显示两个坐标系间的变换。","item_id":"ros_q_006"},{"skill_id":"ros2_launch","type":"single_choice","difficulty":2,"stem":"Launch文件的主要价值是什么？","options":[{"key":"A","text":"一次启动和配置多个节点"},{"key":"B","text":"替代所有消息接口"},{"key":"C","text":"自动修复硬件"},{"key":"D","text":"保存地图像素"}],"correct_answer":"A","explanation":"Launch用于统一启动、配置和监控多个节点。","item_id":"ros_q_007"},{"skill_id":"ros2_nav2_basic","type":"single_choice","difficulty":4,"stem":"Nav2中负责长期导航任务编排的核心机制通常是什么？","options":[{"key":"A","text":"行为树导航器"},{"key":"B","text":"文本编辑器"},{"key":"C","text":"编译器链接器"},{"key":"D","text":"文件压缩器"}],"correct_answer":"A","explanation":"Nav2使用行为树导航器编排规划、控制和恢复等任务。","item_id":"ros_q_008"},{"skill_id":"ros2_slam","type":"single_choice","difficulty":4,"stem":"SLAM Toolbox在线建图至少需要LaserScan和哪类有效关系？","options":[{"key":"A","text":"odom到base_frame的TF"},{"key":"B","text":"网页Cookie"},{"key":"C","text":"Git分支"},{"key":"D","text":"数据库主键"}],"correct_answer":"A","explanation":"建图需要雷达数据以及连续有效的里程计到机器人基座变换。","item_id":"ros_q_009"},{"skill_id":"ros2_robot_bringup","type":"single_choice","difficulty":3,"stem":"URDF主要描述什么？","options":[{"key":"A","text":"机器人连杆、关节和几何组织"},{"key":"B","text":"用户密码"},{"key":"C","text":"数据库事务"},{"key":"D","text":"网页主题"}],"correct_answer":"A","explanation":"URDF描述机器人的结构、几何和关节关系。","item_id":"ros_q_010"}]`;
const C_QUESTIONS_JSON: string = `[{"skill_id":"c_basic","type":"single_choice","difficulty":1,"stem":"标准C程序通常从哪个函数开始执行？","options":[{"key":"A","text":"printf"},{"key":"B","text":"main"},{"key":"C","text":"scanf"},{"key":"D","text":"include"}],"correct_answer":"B","explanation":"main是C程序入口。","item_id":"c_q_001"},{"skill_id":"c_variable","type":"single_choice","difficulty":1,"stem":"下面哪个是合法变量定义？","options":[{"key":"A","text":"int 1num;"},{"key":"B","text":"int num;"},{"key":"C","text":"int for;"},{"key":"D","text":"int num-1;"}],"correct_answer":"B","explanation":"标识符不能以数字开头、使用关键字或包含减号。","item_id":"c_q_002"},{"skill_id":"c_datatype","type":"single_choice","difficulty":1,"stem":"int通常用于表示哪类数据？","options":[{"key":"A","text":"整数"},{"key":"B","text":"字符串"},{"key":"C","text":"文件"},{"key":"D","text":"函数"}],"correct_answer":"A","explanation":"int通常表示整数。","item_id":"c_q_003"},{"skill_id":"c_operator","type":"single_choice","difficulty":2,"stem":"两个int操作数执行5 / 2的结果通常是？","options":[{"key":"A","text":"2"},{"key":"B","text":"2.5"},{"key":"C","text":"3"},{"key":"D","text":"编译失败"}],"correct_answer":"A","explanation":"整数除法会舍去小数部分。","item_id":"c_q_004"},{"skill_id":"c_control","type":"single_choice","difficulty":1,"stem":"顺序、选择和循环结构描述程序的什么？","options":[{"key":"A","text":"文件大小"},{"key":"B","text":"执行流程"},{"key":"C","text":"字符编码"},{"key":"D","text":"链接方式"}],"correct_answer":"B","explanation":"三种结构描述语句执行流程。","item_id":"c_q_005"},{"skill_id":"c_if","type":"single_choice","difficulty":2,"stem":"if条件不成立时，哪个分支可能被执行？","options":[{"key":"A","text":"else"},{"key":"B","text":"include"},{"key":"C","text":"typedef"},{"key":"D","text":"sizeof"}],"correct_answer":"A","explanation":"else用于处理条件不成立的情况。","item_id":"c_q_006"},{"skill_id":"c_loop","type":"single_choice","difficulty":2,"stem":"循环中的break通常有什么作用？","options":[{"key":"A","text":"结束当前循环"},{"key":"B","text":"定义变量"},{"key":"C","text":"调用函数"},{"key":"D","text":"创建数组"}],"correct_answer":"A","explanation":"break立即退出当前循环或switch。","item_id":"c_q_007"},{"skill_id":"c_array","type":"single_choice","difficulty":2,"stem":"int a[5]的合法下标范围是？","options":[{"key":"A","text":"1到5"},{"key":"B","text":"0到5"},{"key":"C","text":"0到4"},{"key":"D","text":"-1到4"}],"correct_answer":"C","explanation":"C数组下标从0开始。","item_id":"c_q_008"},{"skill_id":"c_function","type":"single_choice","difficulty":2,"stem":"函数的主要价值是什么？","options":[{"key":"A","text":"组织可复用代码"},{"key":"B","text":"增加文件大小"},{"key":"C","text":"替代变量"},{"key":"D","text":"关闭编译器"}],"correct_answer":"A","explanation":"函数封装功能并提高复用性。","item_id":"c_q_009"},{"skill_id":"c_pointer","type":"single_choice","difficulty":3,"stem":"指针变量主要保存什么？","options":[{"key":"A","text":"变量名称"},{"key":"B","text":"内存地址"},{"key":"C","text":"数据类型"},{"key":"D","text":"源文件"}],"correct_answer":"B","explanation":"指针用于保存地址。","item_id":"c_q_010"}]`;
const ROS2_REPORT_BEGINNER_JSON: string = `{"learner_id":"__LEARNER_ID__","overall_mastery":33.2,"domain":"ros2_robotics","skill_mastery":[{"skill_id":"linux_environment","name":"Linux环境配置","score":53,"confidence":0.87,"difficulty":1},{"skill_id":"ros2_node","name":"ROS2节点","score":43,"confidence":0.86,"difficulty":2},{"skill_id":"ros2_topic","name":"Topic话题通信","score":42,"confidence":0.86,"difficulty":2},{"skill_id":"ros2_topic_custom","name":"自定义Topic消息","score":32,"confidence":0.85,"difficulty":3},{"skill_id":"ros2_service","name":"Service服务通信","score":31,"confidence":0.85,"difficulty":3},{"skill_id":"ros2_tf2","name":"TF2坐标变换","score":30,"confidence":0.85,"difficulty":3},{"skill_id":"ros2_launch","name":"Launch启动文件","score":38,"confidence":0.86,"difficulty":2},{"skill_id":"ros2_nav2_basic","name":"Nav2导航基础","score":19,"confidence":0.84,"difficulty":4},{"skill_id":"ros2_slam","name":"SLAM建图","score":18,"confidence":0.84,"difficulty":4},{"skill_id":"ros2_robot_bringup","name":"机器人驱动集成","score":26,"confidence":0.85,"difficulty":3}],"knowledge_gaps":["Linux环境配置","ROS2节点","Topic话题通信","自定义Topic消息","Service服务通信","TF2坐标变换","Launch启动文件","Nav2导航基础","SLAM建图","机器人驱动集成"],"strengths":[],"difficulty_curve":[{"label":"基础","score":53},{"label":"应用","score":41},{"label":"进阶","score":26}],"learning_path":[{"order":1,"skill_id":"linux_environment","name":"Linux环境配置","estimated_minutes":60,"mastery":53},{"order":2,"skill_id":"ros2_node","name":"ROS2节点","estimated_minutes":90,"mastery":43},{"order":3,"skill_id":"ros2_topic","name":"Topic话题通信","estimated_minutes":120,"mastery":42},{"order":4,"skill_id":"ros2_topic_custom","name":"自定义Topic消息","estimated_minutes":90,"mastery":32},{"order":5,"skill_id":"ros2_service","name":"Service服务通信","estimated_minutes":120,"mastery":31},{"order":6,"skill_id":"ros2_tf2","name":"TF2坐标变换","estimated_minutes":150,"mastery":30},{"order":7,"skill_id":"ros2_launch","name":"Launch启动文件","estimated_minutes":60,"mastery":38},{"order":8,"skill_id":"ros2_nav2_basic","name":"Nav2导航基础","estimated_minutes":180,"mastery":19},{"order":9,"skill_id":"ros2_slam","name":"SLAM建图","estimated_minutes":180,"mastery":18},{"order":10,"skill_id":"ros2_robot_bringup","name":"机器人驱动集成","estimated_minutes":120,"mastery":26}],"progress_history":[],"recommended_resources":["linux_environment","ros2_node","ros2_topic","ros2_topic_custom","ros2_service","ros2_tf2","ros2_launch","ros2_nav2_basic","ros2_slam","ros2_robot_bringup"]}`;
const ROS2_REPORT_MECHANICAL_JSON: string = `{"learner_id":"__LEARNER_ID__","overall_mastery":56.4,"domain":"ros2_robotics","skill_mastery":[{"skill_id":"linux_environment","name":"Linux环境配置","score":72,"confidence":0.89,"difficulty":1},{"skill_id":"ros2_node","name":"ROS2节点","score":64,"confidence":0.88,"difficulty":2},{"skill_id":"ros2_topic","name":"Topic话题通信","score":63,"confidence":0.88,"difficulty":2},{"skill_id":"ros2_topic_custom","name":"自定义Topic消息","score":55,"confidence":0.88,"difficulty":3},{"skill_id":"ros2_service","name":"Service服务通信","score":54,"confidence":0.87,"difficulty":3},{"skill_id":"ros2_tf2","name":"TF2坐标变换","score":54,"confidence":0.87,"difficulty":3},{"skill_id":"ros2_launch","name":"Launch启动文件","score":61,"confidence":0.88,"difficulty":2},{"skill_id":"ros2_nav2_basic","name":"Nav2导航基础","score":45,"confidence":0.86,"difficulty":4},{"skill_id":"ros2_slam","name":"SLAM建图","score":44,"confidence":0.86,"difficulty":4},{"skill_id":"ros2_robot_bringup","name":"机器人驱动集成","score":52,"confidence":0.87,"difficulty":3}],"knowledge_gaps":["自定义Topic消息","Service服务通信","TF2坐标变换","Nav2导航基础","SLAM建图","机器人驱动集成"],"strengths":[],"difficulty_curve":[{"label":"基础","score":72},{"label":"应用","score":63},{"label":"进阶","score":51}],"learning_path":[{"order":1,"skill_id":"linux_environment","name":"Linux环境配置","estimated_minutes":60,"mastery":72},{"order":2,"skill_id":"ros2_node","name":"ROS2节点","estimated_minutes":90,"mastery":64},{"order":3,"skill_id":"ros2_topic","name":"Topic话题通信","estimated_minutes":120,"mastery":63},{"order":4,"skill_id":"ros2_topic_custom","name":"自定义Topic消息","estimated_minutes":90,"mastery":55},{"order":5,"skill_id":"ros2_service","name":"Service服务通信","estimated_minutes":120,"mastery":54},{"order":6,"skill_id":"ros2_tf2","name":"TF2坐标变换","estimated_minutes":150,"mastery":54},{"order":7,"skill_id":"ros2_launch","name":"Launch启动文件","estimated_minutes":60,"mastery":61},{"order":8,"skill_id":"ros2_nav2_basic","name":"Nav2导航基础","estimated_minutes":180,"mastery":45},{"order":9,"skill_id":"ros2_slam","name":"SLAM建图","estimated_minutes":180,"mastery":44},{"order":10,"skill_id":"ros2_robot_bringup","name":"机器人驱动集成","estimated_minutes":120,"mastery":52}],"progress_history":[],"recommended_resources":["ros2_topic_custom","ros2_service","ros2_tf2","ros2_nav2_basic","ros2_slam","ros2_robot_bringup"]}`;
const ROS2_REPORT_DEVELOPER_JSON: string = `{"learner_id":"__LEARNER_ID__","overall_mastery":75.5,"domain":"ros2_robotics","skill_mastery":[{"skill_id":"linux_environment","name":"Linux环境配置","score":86,"confidence":0.91,"difficulty":1},{"skill_id":"ros2_node","name":"ROS2节点","score":81,"confidence":0.9,"difficulty":2},{"skill_id":"ros2_topic","name":"Topic话题通信","score":80,"confidence":0.9,"difficulty":2},{"skill_id":"ros2_topic_custom","name":"自定义Topic消息","score":75,"confidence":0.89,"difficulty":3},{"skill_id":"ros2_service","name":"Service服务通信","score":74,"confidence":0.89,"difficulty":3},{"skill_id":"ros2_tf2","name":"TF2坐标变换","score":74,"confidence":0.89,"difficulty":3},{"skill_id":"ros2_launch","name":"Launch启动文件","score":78,"confidence":0.9,"difficulty":2},{"skill_id":"ros2_nav2_basic","name":"Nav2导航基础","score":68,"confidence":0.89,"difficulty":4},{"skill_id":"ros2_slam","name":"SLAM建图","score":67,"confidence":0.89,"difficulty":4},{"skill_id":"ros2_robot_bringup","name":"机器人驱动集成","score":72,"confidence":0.89,"difficulty":3}],"knowledge_gaps":[],"strengths":["Linux环境配置","ROS2节点","Topic话题通信","自定义Topic消息","Launch启动文件"],"difficulty_curve":[{"label":"基础","score":86},{"label":"应用","score":80},{"label":"进阶","score":72}],"learning_path":[{"order":1,"skill_id":"linux_environment","name":"Linux环境配置","estimated_minutes":60,"mastery":86},{"order":2,"skill_id":"ros2_node","name":"ROS2节点","estimated_minutes":90,"mastery":81},{"order":3,"skill_id":"ros2_topic","name":"Topic话题通信","estimated_minutes":120,"mastery":80},{"order":4,"skill_id":"ros2_topic_custom","name":"自定义Topic消息","estimated_minutes":90,"mastery":75},{"order":5,"skill_id":"ros2_service","name":"Service服务通信","estimated_minutes":120,"mastery":74},{"order":6,"skill_id":"ros2_tf2","name":"TF2坐标变换","estimated_minutes":150,"mastery":74},{"order":7,"skill_id":"ros2_launch","name":"Launch启动文件","estimated_minutes":60,"mastery":78},{"order":8,"skill_id":"ros2_nav2_basic","name":"Nav2导航基础","estimated_minutes":180,"mastery":68},{"order":9,"skill_id":"ros2_slam","name":"SLAM建图","estimated_minutes":180,"mastery":67},{"order":10,"skill_id":"ros2_robot_bringup","name":"机器人驱动集成","estimated_minutes":120,"mastery":72}],"progress_history":[],"recommended_resources":[]}`;
const C_REPORT_BEGINNER_JSON: string = `{"learner_id":"__LEARNER_ID__","overall_mastery":38.7,"domain":"c_programming","skill_mastery":[{"skill_id":"c_basic","name":"C语言基础","score":53,"confidence":0.87,"difficulty":1},{"skill_id":"c_variable","name":"变量与常量","score":52,"confidence":0.87,"difficulty":1},{"skill_id":"c_datatype","name":"基本数据类型","score":51,"confidence":0.87,"difficulty":1},{"skill_id":"c_operator","name":"运算符与表达式","score":41,"confidence":0.86,"difficulty":2},{"skill_id":"c_control","name":"程序控制结构","score":40,"confidence":0.86,"difficulty":2},{"skill_id":"c_if","name":"条件语句","score":39,"confidence":0.86,"difficulty":2},{"skill_id":"c_loop","name":"循环语句","score":38,"confidence":0.86,"difficulty":2},{"skill_id":"c_array","name":"数组","score":28,"confidence":0.85,"difficulty":3},{"skill_id":"c_function","name":"函数","score":27,"confidence":0.85,"difficulty":3},{"skill_id":"c_pointer","name":"指针基础","score":18,"confidence":0.84,"difficulty":4}],"knowledge_gaps":["C语言基础","变量与常量","基本数据类型","运算符与表达式","程序控制结构","条件语句","循环语句","数组","函数","指针基础"],"strengths":[],"difficulty_curve":[{"label":"基础","score":52},{"label":"应用","score":40},{"label":"进阶","score":24}],"learning_path":[{"order":1,"skill_id":"c_basic","name":"C语言基础","estimated_minutes":45,"mastery":53},{"order":2,"skill_id":"c_variable","name":"变量与常量","estimated_minutes":45,"mastery":52},{"order":3,"skill_id":"c_datatype","name":"基本数据类型","estimated_minutes":60,"mastery":51},{"order":4,"skill_id":"c_operator","name":"运算符与表达式","estimated_minutes":60,"mastery":41},{"order":5,"skill_id":"c_control","name":"程序控制结构","estimated_minutes":75,"mastery":40},{"order":6,"skill_id":"c_if","name":"条件语句","estimated_minutes":45,"mastery":39},{"order":7,"skill_id":"c_loop","name":"循环语句","estimated_minutes":60,"mastery":38},{"order":8,"skill_id":"c_array","name":"数组","estimated_minutes":90,"mastery":28},{"order":9,"skill_id":"c_function","name":"函数","estimated_minutes":90,"mastery":27},{"order":10,"skill_id":"c_pointer","name":"指针基础","estimated_minutes":120,"mastery":18}],"progress_history":[],"recommended_resources":["c_basic","c_variable","c_datatype","c_operator","c_control","c_if","c_loop","c_array","c_function","c_pointer"]}`;
const C_REPORT_MECHANICAL_JSON: string = `{"learner_id":"__LEARNER_ID__","overall_mastery":61.2,"domain":"c_programming","skill_mastery":[{"skill_id":"c_basic","name":"C语言基础","score":72,"confidence":0.89,"difficulty":1},{"skill_id":"c_variable","name":"变量与常量","score":72,"confidence":0.89,"difficulty":1},{"skill_id":"c_datatype","name":"基本数据类型","score":71,"confidence":0.89,"difficulty":1},{"skill_id":"c_operator","name":"运算符与表达式","score":63,"confidence":0.88,"difficulty":2},{"skill_id":"c_control","name":"程序控制结构","score":62,"confidence":0.88,"difficulty":2},{"skill_id":"c_if","name":"条件语句","score":62,"confidence":0.88,"difficulty":2},{"skill_id":"c_loop","name":"循环语句","score":61,"confidence":0.88,"difficulty":2},{"skill_id":"c_array","name":"数组","score":53,"confidence":0.87,"difficulty":3},{"skill_id":"c_function","name":"函数","score":52,"confidence":0.87,"difficulty":3},{"skill_id":"c_pointer","name":"指针基础","score":44,"confidence":0.86,"difficulty":4}],"knowledge_gaps":["数组","函数","指针基础"],"strengths":[],"difficulty_curve":[{"label":"基础","score":72},{"label":"应用","score":62},{"label":"进阶","score":50}],"learning_path":[{"order":1,"skill_id":"c_basic","name":"C语言基础","estimated_minutes":45,"mastery":72},{"order":2,"skill_id":"c_variable","name":"变量与常量","estimated_minutes":45,"mastery":72},{"order":3,"skill_id":"c_datatype","name":"基本数据类型","estimated_minutes":60,"mastery":71},{"order":4,"skill_id":"c_operator","name":"运算符与表达式","estimated_minutes":60,"mastery":63},{"order":5,"skill_id":"c_control","name":"程序控制结构","estimated_minutes":75,"mastery":62},{"order":6,"skill_id":"c_if","name":"条件语句","estimated_minutes":45,"mastery":62},{"order":7,"skill_id":"c_loop","name":"循环语句","estimated_minutes":60,"mastery":61},{"order":8,"skill_id":"c_array","name":"数组","estimated_minutes":90,"mastery":53},{"order":9,"skill_id":"c_function","name":"函数","estimated_minutes":90,"mastery":52},{"order":10,"skill_id":"c_pointer","name":"指针基础","estimated_minutes":120,"mastery":44}],"progress_history":[],"recommended_resources":["c_array","c_function","c_pointer"]}`;
const C_REPORT_DEVELOPER_JSON: string = `{"learner_id":"__LEARNER_ID__","overall_mastery":78.5,"domain":"c_programming","skill_mastery":[{"skill_id":"c_basic","name":"C语言基础","score":86,"confidence":0.91,"difficulty":1},{"skill_id":"c_variable","name":"变量与常量","score":86,"confidence":0.91,"difficulty":1},{"skill_id":"c_datatype","name":"基本数据类型","score":85,"confidence":0.9,"difficulty":1},{"skill_id":"c_operator","name":"运算符与表达式","score":80,"confidence":0.9,"difficulty":2},{"skill_id":"c_control","name":"程序控制结构","score":79,"confidence":0.9,"difficulty":2},{"skill_id":"c_if","name":"条件语句","score":79,"confidence":0.9,"difficulty":2},{"skill_id":"c_loop","name":"循环语句","score":78,"confidence":0.9,"difficulty":2},{"skill_id":"c_array","name":"数组","score":73,"confidence":0.89,"difficulty":3},{"skill_id":"c_function","name":"函数","score":72,"confidence":0.89,"difficulty":3},{"skill_id":"c_pointer","name":"指针基础","score":67,"confidence":0.89,"difficulty":4}],"knowledge_gaps":[],"strengths":["C语言基础","变量与常量","基本数据类型","运算符与表达式","程序控制结构","条件语句","循环语句"],"difficulty_curve":[{"label":"基础","score":86},{"label":"应用","score":79},{"label":"进阶","score":71}],"learning_path":[{"order":1,"skill_id":"c_basic","name":"C语言基础","estimated_minutes":45,"mastery":86},{"order":2,"skill_id":"c_variable","name":"变量与常量","estimated_minutes":45,"mastery":86},{"order":3,"skill_id":"c_datatype","name":"基本数据类型","estimated_minutes":60,"mastery":85},{"order":4,"skill_id":"c_operator","name":"运算符与表达式","estimated_minutes":60,"mastery":80},{"order":5,"skill_id":"c_control","name":"程序控制结构","estimated_minutes":75,"mastery":79},{"order":6,"skill_id":"c_if","name":"条件语句","estimated_minutes":45,"mastery":79},{"order":7,"skill_id":"c_loop","name":"循环语句","estimated_minutes":60,"mastery":78},{"order":8,"skill_id":"c_array","name":"数组","estimated_minutes":90,"mastery":73},{"order":9,"skill_id":"c_function","name":"函数","estimated_minutes":90,"mastery":72},{"order":10,"skill_id":"c_pointer","name":"指针基础","estimated_minutes":120,"mastery":67}],"progress_history":[],"recommended_resources":[]}`;
const ROS2_GRAPH_JSON: string = `{"domain_id":"ros2_robotics","nodes":[{"id":"linux_environment","name":"Linux环境配置","difficulty":1,"estimated_minutes":60,"objectives":["掌握Linux基本命令","能够安装ROS2 Humble","理解工作空间结构"],"criteria":["能使用source命令配置环境","能使用colcon编译工作空间"]},{"id":"ros2_node","name":"ROS2节点","difficulty":2,"estimated_minutes":90,"objectives":["理解节点的概念和作用","掌握Python/C++创建节点的方法"],"criteria":["能创建并运行一个简单的发布者节点","能使用 ros2 node 命令查看节点信息"]},{"id":"ros2_topic","name":"Topic话题通信","difficulty":2,"estimated_minutes":120,"objectives":["理解发布-订阅模式","掌握Topic的创建、发布和订阅"],"criteria":["能创建发布者和订阅者","能使用 ros2 topic 命令调试Topic"]},{"id":"ros2_topic_custom","name":"自定义Topic消息","difficulty":3,"estimated_minutes":90,"objectives":["理解.msg文件格式","掌握自定义消息的创建和使用"],"criteria":["能定义.msg文件","能在代码中使用自定义消息类型"]},{"id":"ros2_service","name":"Service服务通信","difficulty":3,"estimated_minutes":120,"objectives":["理解请求-响应模式","掌握Service的创建和调用"],"criteria":["能创建Service服务端和客户端","能使用 ros2 service 命令调试"]},{"id":"ros2_tf2","name":"TF2坐标变换","difficulty":3,"estimated_minutes":150,"objectives":["理解TF2树结构","掌握坐标变换的发布和监听"],"criteria":["能发布静态和动态坐标变换","能使用 tf2_echo 查看变换关系"]},{"id":"ros2_launch","name":"Launch启动文件","difficulty":2,"estimated_minutes":60,"objectives":["理解Launch文件的作用","掌握Python Launch文件的编写"],"criteria":["能编写多节点Launch文件","能传递参数到Launch文件"]},{"id":"ros2_nav2_basic","name":"Nav2导航基础","difficulty":4,"estimated_minutes":180,"objectives":["理解导航堆栈架构","掌握地图、定位和路径规划概念"],"criteria":["能配置Nav2参数","能使用RViz2设置导航目标点"]},{"id":"ros2_slam","name":"SLAM建图","difficulty":4,"estimated_minutes":180,"objectives":["理解SLAM原理","掌握使用SLAM Toolbox建图"],"criteria":["能运行SLAM节点","能保存和加载地图"]},{"id":"ros2_robot_bringup","name":"机器人驱动集成","difficulty":3,"estimated_minutes":120,"objectives":["理解URDF模型","掌握机器人硬件驱动配置"],"criteria":["能编写URDF文件","能启动机器人底盘驱动"]}],"edges":[{"from_skill_id":"linux_environment","to_skill_id":"ros2_node","relation_type":"prerequisite"},{"from_skill_id":"linux_environment","to_skill_id":"ros2_topic","relation_type":"prerequisite"},{"from_skill_id":"ros2_node","to_skill_id":"ros2_topic","relation_type":"prerequisite"},{"from_skill_id":"ros2_node","to_skill_id":"ros2_service","relation_type":"prerequisite"},{"from_skill_id":"ros2_topic","to_skill_id":"ros2_topic_custom","relation_type":"prerequisite"},{"from_skill_id":"ros2_topic","to_skill_id":"ros2_tf2","relation_type":"prerequisite"},{"from_skill_id":"ros2_node","to_skill_id":"ros2_launch","relation_type":"prerequisite"},{"from_skill_id":"ros2_topic","to_skill_id":"ros2_nav2_basic","relation_type":"prerequisite"},{"from_skill_id":"ros2_tf2","to_skill_id":"ros2_nav2_basic","relation_type":"prerequisite"},{"from_skill_id":"ros2_tf2","to_skill_id":"ros2_slam","relation_type":"prerequisite"},{"from_skill_id":"ros2_nav2_basic","to_skill_id":"ros2_slam","relation_type":"related"},{"from_skill_id":"ros2_robot_bringup","to_skill_id":"ros2_nav2_basic","relation_type":"prerequisite"},{"from_skill_id":"ros2_robot_bringup","to_skill_id":"ros2_slam","relation_type":"prerequisite"},{"from_skill_id":"ros2_launch","to_skill_id":"ros2_robot_bringup","relation_type":"prerequisite"}]}`;
const C_GRAPH_JSON: string = `{"domain_id":"c_programming","nodes":[{"id":"c_basic","name":"C语言基础","difficulty":1,"estimated_minutes":45,"objectives":["理解程序入口与编译流程"],"criteria":["能编译运行Hello World"]},{"id":"c_variable","name":"变量与常量","difficulty":1,"estimated_minutes":45,"objectives":["掌握变量声明与作用域"],"criteria":["能选择合法标识符"]},{"id":"c_datatype","name":"基本数据类型","difficulty":1,"estimated_minutes":60,"objectives":["理解int、char、float"],"criteria":["能按数据选择类型"]},{"id":"c_operator","name":"运算符与表达式","difficulty":2,"estimated_minutes":60,"objectives":["掌握算术与逻辑表达式"],"criteria":["能判断表达式结果"]},{"id":"c_control","name":"程序控制结构","difficulty":2,"estimated_minutes":75,"objectives":["理解顺序、选择、循环"],"criteria":["能组合基本控制结构"]},{"id":"c_if","name":"条件语句","difficulty":2,"estimated_minutes":45,"objectives":["掌握if与switch"],"criteria":["能实现多分支判断"]},{"id":"c_loop","name":"循环语句","difficulty":2,"estimated_minutes":60,"objectives":["掌握for、while与break"],"criteria":["能编写有边界循环"]},{"id":"c_array","name":"数组","difficulty":3,"estimated_minutes":90,"objectives":["理解连续存储与下标"],"criteria":["能避免数组越界"]},{"id":"c_function","name":"函数","difficulty":3,"estimated_minutes":90,"objectives":["掌握参数与返回值"],"criteria":["能拆分可复用函数"]},{"id":"c_pointer","name":"指针基础","difficulty":4,"estimated_minutes":120,"objectives":["理解地址、解引用和数组关系"],"criteria":["能安全使用基础指针"]}],"edges":[{"from_skill_id":"c_basic","to_skill_id":"c_variable","relation_type":"prerequisite"},{"from_skill_id":"c_variable","to_skill_id":"c_datatype","relation_type":"prerequisite"},{"from_skill_id":"c_datatype","to_skill_id":"c_operator","relation_type":"prerequisite"},{"from_skill_id":"c_operator","to_skill_id":"c_control","relation_type":"prerequisite"},{"from_skill_id":"c_control","to_skill_id":"c_if","relation_type":"prerequisite"},{"from_skill_id":"c_if","to_skill_id":"c_loop","relation_type":"prerequisite"},{"from_skill_id":"c_loop","to_skill_id":"c_array","relation_type":"prerequisite"},{"from_skill_id":"c_array","to_skill_id":"c_function","relation_type":"prerequisite"},{"from_skill_id":"c_function","to_skill_id":"c_pointer","relation_type":"prerequisite"}]}`;
const BENCHMARK_JSON: string = `{"suite":"competition-functional-regression-v4","status":"pass","case_count":60,"profile_count":3,"profiles":["零基础转专业","机械背景本科生","软件开发进阶者"],"domains":["ros2_robotics","c_programming"],"metrics":{"hallucination_rate":0.0,"difficulty_match_accuracy":100.0,"core_knowledge_coverage":100.0,"review_pass_rate":100.0},"checks":{"hallucination":true,"difficulty_match":true,"core_coverage":true,"review_pass":true,"case_count":true,"profile_count":true},"disclaimer":"内置演示展示最近一次随发布包保存的60组合自动回归结果；正式模式可重新运行全部技能与画像组合。"}`;

export class DemoBackend {
  private static learnerId: string = 'learner_demo_guest';
  private static workflows: Map<string, DemoWorkflowData> = new Map<string, DemoWorkflowData>();
  private static assessmentQuestions: Map<string, DemoQuestionRecord[]> = new Map<string, DemoQuestionRecord[]>();
  private static assessmentDomains: Map<string, string> = new Map<string, string>();
  private static assessmentProfiles: Map<string, string> = new Map<string, string>();
  private static assessmentLearners: Map<string, string> = new Map<string, string>();
  private static learnerDomains: Map<string, string> = new Map<string, string>();
  private static learnerProfiles: Map<string, string> = new Map<string, string>();
  private static resourceTestScores: Map<string, number> = new Map<string, number>();
  private static feedbackResponses: Map<string, string> = new Map<string, string>();
  private static masteryUpdates: Map<string, number> = new Map<string, number>();
  private static progressUpdates: Map<string, DemoProgressRow[]> = new Map<string, DemoProgressRow[]>();

  static async handle(path: string, method: http.RequestMethod, body?: string): Promise<Object> {
    const data: DemoRequestBody = DemoBackend.parseBody(body);
    const routePath: string = path.split('?')[0];

    if (routePath === '/health') {
      return DemoBackend.parseJson('{"status":"ok","version":"1.7.3-demo","mode":"embedded-demo"}');
    }
    if (routePath === '/api/v1/learners' && method === http.RequestMethod.POST) {
      DemoBackend.learnerId = 'learner_demo_' + Date.now();
      DemoBackend.learnerProfiles.set(DemoBackend.learnerId, DemoBackend.profileForLearner(DemoBackend.learnerId));
      return DemoBackend.parseJson('{"learner_id":' + DemoBackend.q(DemoBackend.learnerId) + '}');
    }
    if (routePath.indexOf('/api/v1/learners/') === 0 && !routePath.endsWith('/report')) {
      const learnerId: string = DemoBackend.segment(routePath, 4);
      return DemoBackend.parseJson('{"learner_id":' + DemoBackend.q(learnerId) +
        ',"education":"本科","major":"演示画像","target_role":"AI工程学习者",' +
        '"weekly_hours":6,"preferences":{"explanation_style":"通俗","resource_priority":"实践优先"}}');
    }
    if (routePath === '/api/v1/assessments' && method === http.RequestMethod.POST) {
      const learnerId: string = data.learner_id || DemoBackend.learnerId;
      const domainId: string = data.domain_id || 'ros2_robotics';
      const profileId: string = DemoBackend.profileForLearner(learnerId);
      const assessmentId: string = 'assessment_demo_' + Date.now();
      const questions: DemoQuestionRecord[] = DemoBackend.selectQuestions(domainId, profileId);
      DemoBackend.assessmentQuestions.set(assessmentId, questions);
      DemoBackend.assessmentDomains.set(assessmentId, domainId);
      DemoBackend.assessmentProfiles.set(assessmentId, profileId);
      DemoBackend.assessmentLearners.set(assessmentId, learnerId);
      DemoBackend.learnerDomains.set(learnerId, domainId);
      DemoBackend.learnerProfiles.set(learnerId, profileId);
      const publicQuestions: DemoPublicQuestion[] = questions.map(
        (question: DemoQuestionRecord): DemoPublicQuestion => new DemoPublicQuestion(question));
      return DemoBackend.parseJson('{"assessment_id":' + DemoBackend.q(assessmentId) +
        ',"items":' + (JSON.stringify(publicQuestions) || '[]') + '}');
    }
    if (routePath.indexOf('/api/v1/assessments/') === 0 && routePath.endsWith('/submit')) {
      const assessmentId: string = DemoBackend.segment(routePath, 4);
      return DemoBackend.assessmentResult(data, assessmentId);
    }
    if (routePath === '/api/v1/workflows' && method === http.RequestMethod.POST) {
      const learnerId: string = data.learner_id || DemoBackend.learnerId;
      const domainId: string = data.domain_id || DemoBackend.learnerDomains.get(learnerId) || 'ros2_robotics';
      const profileId: string = DemoBackend.profileForLearner(learnerId);
      const targetSkill: string = data.target_skill_id || DemoBackend.defaultSkill(domainId, profileId);
      const requestedDifficulty: string = data.requested_difficulty || DemoBackend.profileDifficulty(profileId);
      const workflow: DemoWorkflowData = DemoBackend.createWorkflow(
        learnerId, domainId, profileId, targetSkill, requestedDifficulty);
      return DemoBackend.workflowCreateResponse(workflow);
    }
    if (routePath.indexOf('/api/v1/workflows/') === 0 && routePath.endsWith('/retry') &&
      method === http.RequestMethod.POST) {
      const previous: DemoWorkflowData = DemoBackend.getWorkflow(DemoBackend.segment(routePath, 4));
      const retried: DemoWorkflowData = DemoBackend.createWorkflow(
        previous.learnerId, previous.domainId, previous.profileId,
        previous.targetSkillId, previous.requestedDifficulty);
      return DemoBackend.workflowCreateResponse(retried);
    }
    if (routePath.indexOf('/api/v1/workflows/') === 0 && routePath.endsWith('/snapshot')) {
      const workflow: DemoWorkflowData = DemoBackend.getWorkflow(DemoBackend.segment(routePath, 4));
      const snapshot: DemoSnapshotResult = new DemoSnapshotResult(
        DemoBackend.statusFor(workflow), DemoBackend.traceFor(workflow));
      DemoBackend.advanceWorkflow(workflow);
      return snapshot;
    }
    if (routePath.indexOf('/api/v1/workflows/') === 0 && routePath.endsWith('/trace')) {
      return DemoBackend.traceFor(DemoBackend.getWorkflow(DemoBackend.segment(routePath, 4)));
    }
    if (routePath.indexOf('/api/v1/workflows/') === 0 && method === http.RequestMethod.GET) {
      return DemoBackend.statusFor(DemoBackend.getWorkflow(DemoBackend.segment(routePath, 4)));
    }
    if (routePath.indexOf('/api/v1/resources/') === 0 && routePath.endsWith('/test')) {
      const resourceId: string = DemoBackend.segment(routePath, 4);
      return DemoBackend.resourceTest(resourceId, data);
    }
    if (routePath.indexOf('/api/v1/resources/') === 0 && routePath.endsWith('/feedback')) {
      const resourceId: string = DemoBackend.segment(routePath, 4);
      return DemoBackend.feedback(resourceId, data);
    }
    if (routePath.indexOf('/api/v1/resources/') === 0) {
      const resourceId: string = DemoBackend.segment(routePath, 4);
      return DemoBackend.resource(DemoBackend.workflowForResource(resourceId));
    }
    if (routePath.indexOf('/api/v1/learners/') === 0 && routePath.endsWith('/report')) {
      const learnerId: string = DemoBackend.segment(routePath, 4);
      const domainId: string = DemoBackend.queryValue(path, 'domain_id') ||
        DemoBackend.learnerDomains.get(learnerId) || 'ros2_robotics';
      return DemoBackend.report(learnerId, domainId, DemoBackend.profileForLearner(learnerId));
    }
    if (routePath.indexOf('/api/v1/knowledge/graph') === 0) {
      return DemoBackend.parseJson(DemoBackend.queryValue(path, 'domain_id') === 'c_programming' ? C_GRAPH_JSON : ROS2_GRAPH_JSON);
    }
    if (routePath === '/api/v1/benchmarks/summary') {
      return DemoBackend.parseJson(BENCHMARK_JSON);
    }
    throw new Error('演示引擎不支持接口：' + method + ' ' + path);
  }

  private static createWorkflow(learnerId: string, domainId: string,
    profileId: string, targetSkillId: string, requestedDifficulty: string): DemoWorkflowData {
    const suffix: string = Date.now() + '_' + Math.floor(Math.random() * 1000);
    const workflow: DemoWorkflowData = new DemoWorkflowData(
      'wf_demo_' + suffix, learnerId, domainId, profileId, targetSkillId,
      'res_demo_' + suffix, requestedDifficulty);
    DemoBackend.workflows.set(workflow.workflowId, workflow);
    DemoBackend.learnerDomains.set(learnerId, domainId);
    DemoBackend.learnerProfiles.set(learnerId, profileId);
    return workflow;
  }

  private static workflowCreateResponse(workflow: DemoWorkflowData): Object {
    return DemoBackend.parseJson('{"workflow_id":' + DemoBackend.q(workflow.workflowId) +
      ',"status":' + DemoBackend.q(WorkflowStatus.QUEUED) + '}');
  }

  private static parseJson(json: string): Object {
    return JSON.parse(json) as Object;
  }

  private static q(value: string): string {
    return JSON.stringify(value) || '""';
  }

  private static parseBody(body?: string): DemoRequestBody {
    if (body === undefined || body.length === 0) return new DemoRequestBody();
    try {
      return JSON.parse(body) as DemoRequestBody;
    } catch (error) {
      LogUtil.warn(TAG, `Ignore malformed demo request body: ${(error as Error).message}`);
      return new DemoRequestBody();
    }
  }

  private static segment(path: string, index: number): string {
    const clean: string = path.split('?')[0];
    const parts: string[] = clean.split('/');
    return parts.length > index ? parts[index] : '';
  }

  private static queryValue(path: string, key: string): string {
    const queryIndex: number = path.indexOf('?');
    if (queryIndex < 0) return '';
    const parts: string[] = path.substring(queryIndex + 1).split('&');
    for (const part of parts) {
      const pair: string[] = part.split('=');
      if (pair.length >= 2 && pair[0] === key) return decodeURIComponent(pair[1]);
    }
    return '';
  }

  private static profileDifficulty(profileId: string): string {
    if (profileId === 'developer') return 'advanced';
    if (profileId === 'mechanical') return 'intermediate';
    return 'basic';
  }

  private static profileForLearner(learnerId: string): string {
    const stored: string | undefined = DemoBackend.learnerProfiles.get(learnerId);
    if (stored !== undefined) return stored;
    if (learnerId.indexOf('developer') >= 0) return 'developer';
    if (learnerId.indexOf('beginner') >= 0) return 'beginner';
    return 'mechanical';
  }

  private static selectQuestions(domainId: string, profileId: string): DemoQuestionRecord[] {
    const all: DemoQuestionRecord[] = JSON.parse(
      domainId === 'c_programming' ? C_QUESTIONS_JSON : ROS2_QUESTIONS_JSON) as DemoQuestionRecord[];
    if (profileId === 'beginner') {
      return all.filter((item: DemoQuestionRecord): boolean => item.difficulty <= 2).slice(0, 6);
    }
    if (profileId === 'developer') {
      return all.filter((item: DemoQuestionRecord): boolean => item.difficulty >= 2).slice(0, 7);
    }
    return all.slice(1, 9);
  }

  private static assessmentResult(data: DemoRequestBody, assessmentId: string): Object {
    const questions: DemoQuestionRecord[] = DemoBackend.assessmentQuestions.get(assessmentId) || [];
    const domainId: string = DemoBackend.assessmentDomains.get(assessmentId) || 'ros2_robotics';
    const profileId: string = DemoBackend.assessmentProfiles.get(assessmentId) || 'mechanical';
    const learnerId: string = DemoBackend.assessmentLearners.get(assessmentId) || DemoBackend.learnerId;
    const answers: DemoAnswerItem[] = data.answers || [];
    if (questions.length === 0) throw new Error('演示诊断不存在或已失效');
    if (answers.length !== questions.length) throw new Error('请完整作答全部演示诊断题');
    const answerIds: string[] = answers.map((item: DemoAnswerItem): string => item.item_id);
    if (new Set<string>(answerIds).size !== answerIds.length) throw new Error('演示诊断包含重复答案');

    const results: DemoAssessmentResultItem[] = new Array<DemoAssessmentResultItem>();
    const masteryParts: string[] = [];
    const gapSet: Set<string> = new Set<string>();
    let correctCount: number = 0;
    for (const question of questions) {
      const answer: DemoAnswerItem | undefined = answers.find((item: DemoAnswerItem): boolean =>
        item.item_id === question.item_id);
      if (answer === undefined) throw new Error('演示诊断缺少题目：' + question.item_id);
      const optionKeys: string[] = question.options.map((option: DemoOption): string => option.key);
      const normalized: string = answer.answer.trim().toUpperCase();
      if (!optionKeys.includes(normalized)) throw new Error('题目答案不在可选项中：' + question.item_id);
      const result: DemoAssessmentResultItem = new DemoAssessmentResultItem(question, normalized);
      if (result.is_correct) correctCount++; else gapSet.add(question.skill_id);
      results.push(result);

      const baseline: number = DemoBackend.profileBaseline(profileId);
      const skillScore: number = result.is_correct ? Math.min(100, baseline + 18) : Math.max(10, baseline - 18);
      DemoBackend.masteryUpdates.set(DemoBackend.masteryKey(learnerId, domainId, question.skill_id), skillScore);
      masteryParts.push(DemoBackend.q(question.skill_id) + ':{"score":' + skillScore + ',"confidence":0.88}');
    }
    const score: number = Math.round(correctCount * 100 / questions.length);
    DemoBackend.addProgress(learnerId, domainId, new DemoProgressRow('assessment', '完成演示诊断', score));
    const gaps: string[] = Array.from(gapSet);
    const level: string = profileId === 'developer' ? 'advanced' :
      (profileId === 'mechanical' ? 'intermediate' : 'basic');
    return DemoBackend.parseJson('{"status":"completed","diagnosis_id":' +
      DemoBackend.q('diagnosis_demo_' + Date.now()) + ',"mastery":{' + masteryParts.join(',') +
      '},"knowledge_gaps":' + (JSON.stringify(gaps) || '[]') + ',"recommended_level":' +
      DemoBackend.q(level) + ',"item_results":' + (JSON.stringify(results) || '[]') + '}');
  }

  private static profileBaseline(profileId: string): number {
    if (profileId === 'developer') return 76;
    if (profileId === 'beginner') return 42;
    return 61;
  }

  private static masteryKey(learnerId: string, domainId: string, skillId: string): string {
    return learnerId + '|' + domainId + '|' + skillId;
  }

  private static progressKey(learnerId: string, domainId: string): string {
    return learnerId + '|' + domainId;
  }

  private static addProgress(learnerId: string, domainId: string, item: DemoProgressRow): void {
    const key: string = DemoBackend.progressKey(learnerId, domainId);
    const rows: DemoProgressRow[] = DemoBackend.progressUpdates.get(key) || [];
    rows.push(item);
    DemoBackend.progressUpdates.set(key, rows.slice(Math.max(0, rows.length - 20)));
  }

  private static getWorkflow(workflowId: string): DemoWorkflowData {
    const workflow: DemoWorkflowData | undefined = DemoBackend.workflows.get(workflowId);
    if (workflow !== undefined) return workflow;
    throw new Error('演示工作流不存在：' + workflowId);
  }

  private static workflowForResource(resourceId: string): DemoWorkflowData {
    let match: DemoWorkflowData | null = null;
    DemoBackend.workflows.forEach((workflow: DemoWorkflowData) => {
      if (workflow.resourceId === resourceId) match = workflow;
    });
    if (match !== null) return match as DemoWorkflowData;
    throw new Error('演示学习资源不存在：' + resourceId);
  }

  private static advanceWorkflow(workflow: DemoWorkflowData): void {
    workflow.phaseIndex = Math.min(6, workflow.phaseIndex + 1);
  }

  private static statusFor(workflow: DemoWorkflowData): Object {
    let status: WorkflowStatus = WorkflowStatus.ASSESSMENT_COMPLETED;
    let currentAgent: string = '';
    let progress: number = 10;
    if (workflow.phaseIndex >= 6) {
      return DemoBackend.parseJson('{"workflow_id":' + DemoBackend.q(workflow.workflowId) +
        ',"status":' + DemoBackend.q(WorkflowStatus.PUBLISHED) +
        ',"progress":100,"resource_id":' + DemoBackend.q(workflow.resourceId) + '}');
    } else if (workflow.phaseIndex === 5) {
      status = WorkflowStatus.REVIEWING; currentAgent = 'review_agent'; progress = 86;
    } else if (workflow.phaseIndex === 4) {
      status = WorkflowStatus.GENERATING; currentAgent = 'generation_agent'; progress = 70;
    } else if (workflow.phaseIndex === 3) {
      status = WorkflowStatus.RETRIEVING; currentAgent = 'retrieval_agent'; progress = 52;
    } else if (workflow.phaseIndex === 2) {
      status = WorkflowStatus.PATH_PLANNING; currentAgent = 'planner_agent'; progress = 35;
    } else if (workflow.phaseIndex === 1) {
      status = WorkflowStatus.DIAGNOSING; currentAgent = 'diagnosis_agent'; progress = 20;
    }
    const agentPart: string = currentAgent ? ',"current_agent":' + DemoBackend.q(currentAgent) : '';
    return DemoBackend.parseJson('{"workflow_id":' + DemoBackend.q(workflow.workflowId) +
      ',"status":' + DemoBackend.q(status) + ',"progress":' + progress + agentPart + '}');
  }

  private static traceFor(workflow: DemoWorkflowData): Object {
    const rows: string[] = [];
    const skillName: string = DemoBackend.skillName(workflow.domainId, workflow.targetSkillId);
    const profileLabel: string = DemoBackend.profileLabel(workflow.profileId);
    const diagnosis: string = profileLabel + '画像完成分层诊断，目标锁定' + skillName;
    const plan: string = '按领域前置依赖生成到' + skillName + '的合法路径';
    const retrieval: string = workflow.domainId === 'c_programming' ?
      '按目标技能排序C17已审核证据' : '按目标技能排序ROS2 Humble已审核证据';
    DemoBackend.appendTrace(rows, workflow.phaseIndex, 1, 'diagnosis_agent', diagnosis, 0.90);
    DemoBackend.appendTrace(rows, workflow.phaseIndex, 2, 'planner_agent', plan, 0.95);
    DemoBackend.appendTrace(rows, workflow.phaseIndex, 3, 'retrieval_agent', retrieval, 0.94);
    DemoBackend.appendTrace(rows, workflow.phaseIndex, 4, 'generation_agent',
      '生成与画像难度匹配的讲义、可验证实操和可作答测试', 0.91);
    DemoBackend.appendTrace(rows, workflow.phaseIndex, 5, 'review_agent',
      '结构、证据、答案和领域一致性检查通过', 0.95);
    return DemoBackend.parseJson('{"runs":[' + rows.join(',') + ']}');
  }

  private static appendTrace(rows: string[], phaseIndex: number, agentPhase: number,
    agent: string, summary: string, confidence: number): void {
    if (phaseIndex < agentPhase) return;
    const status: string = phaseIndex > agentPhase ? 'success' : 'running';
    rows.push('{"agent":' + DemoBackend.q(agent) + ',"status":' + DemoBackend.q(status) +
      ',"summary":' + DemoBackend.q(summary) + ',"confidence":' + confidence + '}');
  }

  private static resourceTest(resourceId: string, data: DemoRequestBody): Object {
    const workflow: DemoWorkflowData = DemoBackend.workflowForResource(resourceId);
    const raw: string = DemoBackend.testsFor(
      workflow.domainId, workflow.targetSkillId, DemoBackend.skillName(workflow.domainId, workflow.targetSkillId), true);
    const items: DemoGradedTestItem[] = JSON.parse(raw) as DemoGradedTestItem[];
    const answers: DemoAnswerItem[] = data.answers || [];
    if (answers.length !== items.length) throw new Error('请完整作答全部演示测试题');
    const answerIds: string[] = answers.map((answer: DemoAnswerItem): string => answer.item_id);
    if (new Set<string>(answerIds).size !== answerIds.length) throw new Error('测试答案包含重复题目');
    const results: string[] = [];
    const errorTags: string[] = [];
    let correctCount: number = 0;
    for (const item of items) {
      const answer: DemoAnswerItem | undefined = answers.find((row: DemoAnswerItem): boolean => row.item_id === item.id);
      if (answer === undefined) throw new Error('测试答案缺少题目：' + item.id);
      const normalized: string = answer.answer.trim().toUpperCase();
      const optionKeys: string[] = item.options.map((option: DemoOption): string => option.key.toUpperCase());
      if (!optionKeys.includes(normalized)) throw new Error('测试答案不在可选项中：' + item.id);
      const correct: boolean = normalized === item.correct_answer.trim().toUpperCase();
      if (correct) correctCount++; else if (!errorTags.includes(item.skill_id)) errorTags.push(item.skill_id);
      results.push('{"item_id":' + DemoBackend.q(item.id) + ',"skill_id":' + DemoBackend.q(item.skill_id) +
        ',"user_answer":' + DemoBackend.q(normalized) + ',"correct_answer":' +
        DemoBackend.q(item.correct_answer) + ',"is_correct":' + correct + ',"explanation":' +
        DemoBackend.q(item.explanation) + '}');
    }
    const score: number = items.length > 0 ? correctCount / items.length : 0;
    DemoBackend.resourceTestScores.set(resourceId, score);
    return DemoBackend.parseJson('{"score":' + score + ',"correct_count":' + correctCount +
      ',"total_count":' + items.length + ',"error_tags":' + (JSON.stringify(errorTags) || '[]') +
      ',"item_results":[' + results.join(',') + ']}');
  }

  private static feedback(resourceId: string, data: DemoRequestBody): Object {
    const cached: string | undefined = DemoBackend.feedbackResponses.get(resourceId);
    if (cached !== undefined) return DemoBackend.parseJson(cached);

    const workflow: DemoWorkflowData = DemoBackend.workflowForResource(resourceId);
    const correctRate: number | undefined = DemoBackend.resourceTestScores.get(resourceId);
    if (correctRate === undefined) throw new Error('请先完成并提交分阶测试');

    const expectedCount: number = DemoBackend.practiceFor(workflow.domainId, workflow.targetSkillId).length;
    const practiceResults: DemoPracticeResult[] = data.practice_results || [];
    if (practiceResults.length !== expectedCount) throw new Error('请逐项确认全部实操步骤');
    const orders: number[] = practiceResults.map((item: DemoPracticeResult): number => item.order);
    if (new Set<number>(orders).size !== expectedCount) throw new Error('实操结果存在重复步骤');
    for (let order: number = 1; order <= expectedCount; order++) {
      if (!orders.includes(order)) throw new Error('实操结果缺少第' + order + '步');
    }
    const practiceScore: number = practiceResults.filter(
      (item: DemoPracticeResult): boolean => item.success).length / expectedCount;
    const subjective: string = data.subjective_difficulty || 'appropriate';
    const previousScore: number = DemoBackend.masteryUpdates.get(
      DemoBackend.masteryKey(workflow.learnerId, workflow.domainId, workflow.targetSkillId)) ||
      DemoBackend.profileBaseline(workflow.profileId);
    const performance: number = Math.round(100 * (0.5 * correctRate + 0.5 * practiceScore));
    const updatedScore: number = Math.round(0.20 * previousScore + 0.80 * performance);
    DemoBackend.masteryUpdates.set(
      DemoBackend.masteryKey(workflow.learnerId, workflow.domainId, workflow.targetSkillId), updatedScore);
    DemoBackend.addProgress(workflow.learnerId, workflow.domainId,
      new DemoProgressRow('resource_feedback', '完成' +
        DemoBackend.skillName(workflow.domainId, workflow.targetSkillId), performance, workflow.targetSkillId));

    let action: string = 'advance';
    let targetSkill: string = DemoBackend.nextSkill(workflow.domainId, workflow.targetSkillId);
    let reason: string = '理论与实操达标，进入下一技能';
    if (correctRate < 0.6) {
      action = 'lower_difficulty';
      targetSkill = workflow.domainId === 'c_programming' ? 'c_basic' : 'linux_environment';
      reason = workflow.domainId === 'c_programming' ?
        '理论正确率偏低，先回补C语言基础' : '理论正确率偏低，先回补Linux与ROS2环境';
    } else if (practiceScore < 0.5) {
      action = 'add_practice';
      targetSkill = workflow.targetSkillId;
      reason = '实操成功率偏低，围绕当前技能增加一轮可验证练习';
    } else if (subjective === 'too_hard') {
      action = 'lower_difficulty';
      targetSkill = workflow.targetSkillId;
      reason = '客观成绩达标但主观难度偏高，当前技能以基础难度重新巩固';
    } else if (subjective === 'too_easy' && correctRate >= 0.8 && practiceScore >= 0.8) {
      reason = '理论、实操均达标且主观难度偏低，下一技能提升资源难度';
    }

    let nextDifficulty: string = DemoBackend.profileDifficulty(workflow.profileId);
    if (action === 'lower_difficulty' || action === 'add_practice') nextDifficulty = 'basic';
    if (subjective === 'too_easy' && correctRate >= 0.8 && practiceScore >= 0.8) nextDifficulty = 'advanced';

    let response: string = '';
    if (action === 'advance' && targetSkill.length === 0) {
      response = '{"decision":"complete","reason":"当前领域的全部技能节点已完成，可查看学情报告复习薄弱项","next_workflow_id":null}';
    } else {
      const next: DemoWorkflowData = DemoBackend.createWorkflow(
        workflow.learnerId, workflow.domainId, workflow.profileId, targetSkill, nextDifficulty);
      response = '{"decision":' + DemoBackend.q(action) + ',"reason":' +
        DemoBackend.q(reason) + ',"next_workflow_id":' + DemoBackend.q(next.workflowId) + '}';
    }
    DemoBackend.feedbackResponses.set(resourceId, response);
    return DemoBackend.parseJson(response);
  }

  private static resource(workflow: DemoWorkflowData): Object {
    const skillName: string = DemoBackend.skillName(workflow.domainId, workflow.targetSkillId);
    const difficulty: string = workflow.requestedDifficulty;
    const profileText: string = workflow.profileId === 'beginner' ?
      '使用生活化类比并把每一步拆成单一动作。' : (workflow.profileId === 'mechanical' ?
        '重点映射到传感器、执行器与机器人调试流程。' :
        '重点分析接口契约、边界条件、失败模式与工程取舍。');
    const concept: string = DemoBackend.skillConcept(workflow.domainId, workflow.targetSkillId);
    const practices: DemoPracticeSpec[] = DemoBackend.practiceFor(workflow.domainId, workflow.targetSkillId);
    const sourceUrl: string = DemoBackend.sourceUrlFor(workflow.domainId, workflow.targetSkillId);
    const sections: string = '[{"heading":"核心定义","content":' +
      DemoBackend.q(skillName + '可以理解为：' + concept + '。' + profileText) + ',"citations":["ev_001"]},' +
      '{"heading":"工程使用流程","content":' + DemoBackend.q(
        '先确认前置条件，再执行最小示例，最后用可观察结果验证' + skillName + '是否工作。') +
      ',"citations":["ev_001"]},{"heading":"常见错误与排查","content":' + DemoBackend.q(
        '出现异常时按环境、输入、接口约束、运行状态和输出结果的顺序排查，不跳过证据。') +
      ',"citations":["ev_001"]}]';
    const steps: string[] = [];
    for (let index: number = 0; index < practices.length; index++) {
      const item: DemoPracticeSpec = practices[index];
      steps.push('{"order":' + (index + 1) + ',"title":' + DemoBackend.q(item.title) +
        ',"command":' + DemoBackend.q(item.command) + ',"expected_result":' +
        DemoBackend.q(item.expected) + ',"skill_id":' + DemoBackend.q(workflow.targetSkillId) + '}');
    }
    const tests: string = DemoBackend.testsFor(workflow.domainId, workflow.targetSkillId, skillName, false);
    const json: string = '{"resource_id":' + DemoBackend.q(workflow.resourceId) +
      ',"workflow_id":' + DemoBackend.q(workflow.workflowId) + ',"difficulty":' +
      DemoBackend.q(difficulty) + ',"target_skill":' + DemoBackend.q(workflow.targetSkillId) +
      ',"lecture":{"title":' + DemoBackend.q(profileText.substring(0, profileText.length - 1) + ' · ' + skillName) +
      ',"estimated_read_time_minutes":12,"sections":' + sections + '},' +
      '"practice_guide":{"title":' + DemoBackend.q(skillName + '可验证实操') +
      ',"prerequisites":[' + DemoBackend.q(workflow.domainId === 'c_programming' ? 'C17编译器' : 'ROS2 Humble环境') +
      '],"safety_notes":["只在教学或测试环境执行命令","修改文件前保留可回滚副本"],"steps":[' +
      steps.join(',') + ']},"graded_test":{"title":' + DemoBackend.q(skillName + '分阶测试') +
      ',"items":' + tests + '},"citations":[{"evidence_id":"ev_001","title":' +
      DemoBackend.q(skillName + '官方参考') + ',"source_url":' + DemoBackend.q(sourceUrl) +
      ',"verification_status":"verified"}],"review":{"decision":"approve","scores":{' +
      '"factuality":0.96,"evidence_coverage":0.95,"difficulty_match":0.94,"actionability":0.96},"issues":[]},' +
      '"metadata":{"profile":' + DemoBackend.q(workflow.profileId) + ',"target_skill":' +
      DemoBackend.q(workflow.targetSkillId) + ',"provider":"embedded-demo-engine"}' +
      DemoBackend.feedbackStateFor(workflow.resourceId) + '}';
    return DemoBackend.parseJson(json);
  }

  private static feedbackStateFor(resourceId: string): string {
    const cached: string | undefined = DemoBackend.feedbackResponses.get(resourceId);
    if (cached === undefined) return ',"feedback_recorded":false';
    const response: Object = DemoBackend.parseJson(cached);
    const row: Record<string, Object> = response as Record<string, Object>;
    const decision: string = String(row['decision'] || 'recorded');
    const reason: string = String(row['reason'] || '反馈已记录');
    const nextValue: Object | undefined = row['next_workflow_id'];
    const nextPart: string = nextValue === undefined || nextValue === null ?
      ',"next_workflow_id":null' : ',"next_workflow_id":' + DemoBackend.q(String(nextValue));
    return ',"feedback_recorded":true,"feedback_decision":' + DemoBackend.q(decision) +
      ',"feedback_reason":' + DemoBackend.q(reason) + nextPart;
  }

  private static practiceFor(domainId: string, skillId: string): DemoPracticeSpec[] {
    if (domainId === 'c_programming') {
      const source: string = DemoBackend.cSourceFor(skillId);
      return [
        new DemoPracticeSpec('生成最小示例', "cat > lesson.c <<'EOF'\n" + source + "EOF", '当前目录生成lesson.c'),
        new DemoPracticeSpec('启用严格警告编译', 'cc -std=c17 -Wall -Wextra -Wpedantic lesson.c -o lesson',
          '编译成功且没有警告'),
        new DemoPracticeSpec('运行并核对输出', './lesson', DemoBackend.cExpectedFor(skillId)),
      ];
    }
    const command: string = DemoBackend.rosCommandFor(skillId);
    return [
      new DemoPracticeSpec('确认ROS2 Humble环境', 'source /opt/ros/humble/setup.bash && ros2 --help',
        '显示ros2命令帮助且无command not found'),
      new DemoPracticeSpec('执行目标技能验证命令', command, '命令正常返回目标技能相关信息'),
      new DemoPracticeSpec('记录可复现证据', command + ' 2>&1 | head -n 20', '保留命令、输出和异常信息'),
    ];
  }

  private static cSourceFor(skillId: string): string {
    if (skillId === 'c_basic') return '#include <stdio.h>\nint main(void){puts("Hello, C17"); return 0;}\n';
    if (skillId === 'c_variable') return '#include <stdio.h>\nint main(void){int count=3; const int step=2; printf("%d\\n",count+step); return 0;}\n';
    if (skillId === 'c_datatype') return '#include <stdio.h>\nint main(void){int n=7; double x=2.5; char c=\'A\'; printf("%d %.1f %c\\n",n,x,c); return 0;}\n';
    if (skillId === 'c_operator') return '#include <stdio.h>\nint main(void){int a=5,b=2; printf("%d %d\\n",a/b,a%b); return 0;}\n';
    if (skillId === 'c_control') return '#include <stdio.h>\nint main(void){int x=2; if(x>0){puts("positive");} for(int i=0;i<2;i++){printf("%d ",i);} return 0;}\n';
    if (skillId === 'c_if') return '#include <stdio.h>\nint main(void){int score=78; if(score>=60){puts("pass");}else{puts("retry");} return 0;}\n';
    if (skillId === 'c_loop') return '#include <stdio.h>\nint main(void){for(int i=0;i<3;i++) printf("%d ",i); return 0;}\n';
    if (skillId === 'c_array') return '#include <stdio.h>\nint main(void){int a[3]={1,2,3}; printf("%d\\n",a[2]); return 0;}\n';
    if (skillId === 'c_function') return '#include <stdio.h>\nint add(int a,int b){return a+b;} int main(void){printf("%d\\n",add(2,3));return 0;}\n';
    return '#include <stdio.h>\nint main(void){int x=7; int *p=&x; printf("%d\\n",*p); return 0;}\n';
  }

  private static cExpectedFor(skillId: string): string {
    if (skillId === 'c_basic') return '输出Hello, C17';
    if (skillId === 'c_variable') return '输出5';
    if (skillId === 'c_datatype') return '输出7 2.5 A';
    if (skillId === 'c_operator') return '输出2 1';
    if (skillId === 'c_control') return '先输出positive，再输出0 1';
    if (skillId === 'c_if') return '输出pass';
    if (skillId === 'c_loop') return '输出0 1 2';
    if (skillId === 'c_array') return '输出3';
    if (skillId === 'c_function') return '输出5';
    return '输出7';
  }

  private static rosCommandFor(skillId: string): string {
    if (skillId === 'linux_environment') return 'printenv ROS_DISTRO && which ros2';
    if (skillId === 'ros2_node') return 'ros2 node list';
    if (skillId === 'ros2_topic') return 'ros2 topic list -t';
    if (skillId === 'ros2_topic_custom') return 'ros2 interface list | grep /msg/ | head';
    if (skillId === 'ros2_service') return 'ros2 service list -t';
    if (skillId === 'ros2_tf2') return 'ros2 run tf2_ros tf2_echo --help';
    if (skillId === 'ros2_launch') return 'ros2 launch --help';
    if (skillId === 'ros2_nav2_basic') return 'ros2 pkg prefix nav2_bringup';
    if (skillId === 'ros2_slam') return 'ros2 pkg prefix slam_toolbox';
    return 'ros2 pkg prefix robot_state_publisher && ros2 interface show sensor_msgs/msg/LaserScan';
  }

  private static sourceUrlFor(domainId: string, skillId: string): string {
    if (domainId === 'c_programming') {
      if (skillId === 'c_pointer') return 'https://en.cppreference.com/w/c/language/pointer';
      if (skillId === 'c_array') return 'https://en.cppreference.com/w/c/language/array';
      if (skillId === 'c_function') return 'https://en.cppreference.com/w/c/language/functions';
      if (skillId === 'c_loop') return 'https://en.cppreference.com/w/c/language/for';
      if (skillId === 'c_if') return 'https://en.cppreference.com/w/c/language/if';
      if (skillId === 'c_operator') return 'https://en.cppreference.com/w/c/language/operator_precedence';
      if (skillId === 'c_datatype') return 'https://en.cppreference.com/w/c/language/type';
      if (skillId === 'c_variable') return 'https://en.cppreference.com/w/c/language/objects';
      if (skillId === 'c_control') return 'https://en.cppreference.com/w/c/language/statements';
      return 'https://en.cppreference.com/w/c/language/main_function';
    }
    if (skillId === 'linux_environment') return 'https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html';
    if (skillId === 'ros2_node') return 'https://docs.ros.org/en/humble/Concepts/Basic/About-Nodes.html';
    if (skillId === 'ros2_topic') return 'https://docs.ros.org/en/humble/Concepts/Basic/About-Topics.html';
    if (skillId === 'ros2_topic_custom') return 'https://docs.ros.org/en/humble/Concepts/Basic/About-Interfaces.html';
    if (skillId === 'ros2_service') return 'https://docs.ros.org/en/humble/Concepts/Basic/About-Services.html';
    if (skillId === 'ros2_tf2') return 'https://docs.ros.org/en/humble/Concepts/Intermediate/About-Tf2.html';
    if (skillId === 'ros2_launch') return 'https://docs.ros.org/en/humble/Tutorials/Intermediate/Launch/Launch-Main.html';
    if (skillId === 'ros2_nav2_basic') return 'https://docs.nav2.org/concepts/index.html';
    if (skillId === 'ros2_slam') return 'https://docs.ros.org/en/humble/p/slam_toolbox/';
    return 'https://docs.ros.org/en/humble/Tutorials/Intermediate/URDF/URDF-Main.html';
  }

  private static testsFor(domainId: string, skillId: string, skillName: string, includeAnswers: boolean): string {
    const records: DemoQuestionRecord[] = JSON.parse(
      domainId === 'c_programming' ? C_QUESTIONS_JSON : ROS2_QUESTIONS_JSON) as DemoQuestionRecord[];
    const selected: DemoQuestionRecord | undefined = records.find((item: DemoQuestionRecord): boolean =>
      item.skill_id === skillId);
    let first: string = '';
    if (selected !== undefined) {
      const answerPart: string = includeAnswers ? ',"correct_answer":' +
        DemoBackend.q(selected.correct_answer) + ',"explanation":' + DemoBackend.q(selected.explanation) : '';
      first = '{"id":' + DemoBackend.q('demo_gt_' + skillId + '_1') + ',"skill_id":' +
        DemoBackend.q(skillId) + ',"difficulty":"basic","stem":' + DemoBackend.q(selected.stem) +
        ',"options":' + (JSON.stringify(selected.options) || '[]') + answerPart + '}';
    } else {
      const answerPart: string = includeAnswers ? ',"correct_answer":"A","explanation":' +
        DemoBackend.q('本轮资源围绕' + skillName + '。') : '';
      first = '{"id":"demo_gt_1","skill_id":' + DemoBackend.q(skillId) +
        ',"difficulty":"basic","stem":"本轮目标技能是什么？","options":[{"key":"A","text":' +
        DemoBackend.q(skillName) + '},{"key":"B","text":"其他技能"}]' + answerPart + '}';
    }
    const secondAnswer: string = includeAnswers ?
      ',"correct_answer":"B","explanation":"可重复输入和可观察输出构成验证证据。"' : '';
    const second: string = '{"id":"demo_gt_2","skill_id":' + DemoBackend.q(skillId) +
      ',"difficulty":"intermediate","stem":"哪种方式能可靠确认实操完成？",' +
      '"options":[{"key":"A","text":"只凭感觉"},{"key":"B","text":"执行命令并比对预期结果"}]' +
      secondAnswer + '}';
    const thirdAnswer: string = includeAnswers ?
      ',"correct_answer":"C","explanation":"保留证据并分层排查可以定位根因。"' : '';
    const third: string = '{"id":"demo_gt_3","skill_id":' + DemoBackend.q(skillId) +
      ',"difficulty":"advanced","stem":"出现异常时最合理的第一步是什么？",' +
      '"options":[{"key":"A","text":"删除项目"},{"key":"B","text":"忽略错误"},' +
      '{"key":"C","text":"保留现场并按环境、接口、运行状态、输出逐层排查"}]' +
      thirdAnswer + '}';
    return '[' + first + ',' + second + ',' + third + ']';
  }

  private static skillConcept(domainId: string, skillId: string): string {
    if (domainId === 'c_programming') {
      if (skillId === 'c_pointer') return '指针保存对象地址，解引用前必须保证地址有效';
      if (skillId === 'c_array') return '数组是固定长度的连续同类型对象，下标范围必须受控';
      if (skillId === 'c_function') return '函数通过参数、返回值和作用域封装可复用逻辑';
      if (skillId === 'c_loop') return '循环通过初始化、条件和更新重复执行受控步骤';
      if (skillId === 'c_if') return '条件语句根据表达式真假选择执行分支';
      return 'C程序通过明确的数据类型、表达式和控制结构完成计算';
    }
    if (skillId === 'linux_environment') return '环境变量和安装路径决定终端能否找到ROS2命令与接口';
    if (skillId === 'ros2_node') return '节点是ROS图中执行计算并通过接口协作的基本进程实体';
    if (skillId === 'ros2_topic') return 'Topic使用发布订阅模式传输持续异步数据流';
    if (skillId === 'ros2_service') return 'Service使用请求响应模式完成有明确返回结果的一次性交互';
    if (skillId === 'ros2_tf2') return 'TF2维护坐标系之间随时间变化的变换关系';
    if (skillId === 'ros2_launch') return 'Launch统一描述多节点、参数和命名空间的启动编排';
    if (skillId === 'ros2_slam') return 'SLAM同时估计机器人位姿并构建环境地图';
    if (skillId === 'ros2_nav2_basic') return 'Nav2组合定位、规划、控制和行为树完成自主导航';
    return '机器人驱动集成把底盘与传感器接口统一接入ROS2通信图';
  }

  private static skillName(domainId: string, skillId: string): string {
    const cIds: string[] = ['c_basic','c_variable','c_datatype','c_operator','c_control','c_if','c_loop','c_array','c_function','c_pointer'];
    const cNames: string[] = ['C语言基础','变量与常量','基本数据类型','运算符与表达式','程序控制结构','条件语句','循环语句','数组','函数','指针基础'];
    const rIds: string[] = ['linux_environment','ros2_node','ros2_topic','ros2_topic_custom','ros2_service','ros2_tf2','ros2_launch','ros2_nav2_basic','ros2_slam','ros2_robot_bringup'];
    const rNames: string[] = ['Linux环境配置','ROS2节点','Topic话题通信','自定义Topic消息','Service服务通信','TF2坐标变换','Launch启动文件','Nav2导航基础','SLAM建图','机器人驱动集成'];
    const ids: string[] = domainId === 'c_programming' ? cIds : rIds;
    const names: string[] = domainId === 'c_programming' ? cNames : rNames;
    const index: number = ids.indexOf(skillId);
    return index >= 0 ? names[index] : skillId;
  }

  private static defaultSkill(domainId: string, profileId: string): string {
    if (domainId === 'c_programming') {
      if (profileId === 'beginner') return 'c_variable';
      if (profileId === 'developer') return 'c_pointer';
      return 'c_array';
    }
    if (profileId === 'beginner') return 'ros2_node';
    if (profileId === 'developer') return 'ros2_topic_custom';
    return 'ros2_topic';
  }

  private static nextSkill(domainId: string, current: string): string {
    const ids: string[] = domainId === 'c_programming' ?
      ['c_basic','c_variable','c_datatype','c_operator','c_control','c_if','c_loop','c_array','c_function','c_pointer'] :
      ['linux_environment','ros2_node','ros2_topic','ros2_topic_custom','ros2_service','ros2_tf2','ros2_launch','ros2_robot_bringup','ros2_nav2_basic','ros2_slam'];
    const index: number = ids.indexOf(current);
    if (index < 0) throw new Error('演示技能不属于当前领域：' + current);
    return index + 1 < ids.length ? ids[index + 1] : '';
  }

  private static profileLabel(profileId: string): string {
    if (profileId === 'beginner') return '零基础';
    if (profileId === 'developer') return '软件开发进阶';
    return '机械工程实践';
  }

  private static report(learnerId: string, domainId: string, profileId: string): Object {
    let template: string = '';
    if (domainId === 'c_programming') {
      template = profileId === 'beginner' ? C_REPORT_BEGINNER_JSON :
        (profileId === 'developer' ? C_REPORT_DEVELOPER_JSON : C_REPORT_MECHANICAL_JSON);
    } else {
      template = profileId === 'beginner' ? ROS2_REPORT_BEGINNER_JSON :
        (profileId === 'developer' ? ROS2_REPORT_DEVELOPER_JSON : ROS2_REPORT_MECHANICAL_JSON);
    }
    const report: DemoReportPayload = JSON.parse(
      template.replace('__LEARNER_ID__', learnerId)) as DemoReportPayload;
    let total: number = 0;
    const basic: number[] = [];
    const application: number[] = [];
    const advanced: number[] = [];
    report.knowledge_gaps = [];
    report.strengths = [];
    report.recommended_resources = [];

    for (const skill of report.skill_mastery) {
      const updated: number | undefined = DemoBackend.masteryUpdates.get(
        DemoBackend.masteryKey(learnerId, domainId, skill.skill_id));
      if (updated !== undefined) {
        skill.score = updated;
        skill.confidence = Math.min(0.98, skill.confidence + 0.04);
      }
      total += skill.score;
      if (skill.score < 60) {
        report.knowledge_gaps.push(skill.name);
        report.recommended_resources.push(skill.skill_id);
      }
      if (skill.score >= 75) report.strengths.push(skill.name);
      if (skill.difficulty <= 1) basic.push(skill.score);
      else if (skill.difficulty === 2) application.push(skill.score);
      else advanced.push(skill.score);
      const pathRow: DemoLearningPathRow | undefined = report.learning_path.find(
        (row: DemoLearningPathRow): boolean => row.skill_id === skill.skill_id);
      if (pathRow !== undefined) pathRow.mastery = skill.score;
    }
    report.overall_mastery = report.skill_mastery.length > 0 ?
      Math.round(total * 10 / report.skill_mastery.length) / 10 : 0;
    report.difficulty_curve = [
      new DemoDifficultyRow('基础', DemoBackend.average(basic), basic.length),
      new DemoDifficultyRow('应用', DemoBackend.average(application), application.length),
      new DemoDifficultyRow('进阶', DemoBackend.average(advanced), advanced.length),
    ];
    report.progress_history = DemoBackend.progressUpdates.get(
      DemoBackend.progressKey(learnerId, domainId)) || [];
    return DemoBackend.parseJson(JSON.stringify(report) || '{}');
  }

  private static average(values: number[]): number {
    if (values.length === 0) return 0;
    return Math.round(values.reduce((sum: number, value: number): number => sum + value, 0) * 10 / values.length) / 10;
  }

}
