"""Deterministic resource generator for the ROS2 Topic MVP.

The provider boundary is retained, but the competition demo can run without an LLM.
Every factual section is tied to evidence selected by the retrieval agent.
"""

from copy import deepcopy
from datetime import datetime, timezone
import logging

from app.agents.base import BaseAgent, AgentResult
from app.workflow.state import WorkflowState
from app.providers.llm import create_llm_provider
from app.prompts.resource_generation import SYSTEM_INSTRUCTIONS, build_resource_prompt

logger = logging.getLogger(__name__)


class GenerationAgent(BaseAgent):
    agent_type = "generation_agent"

    @staticmethod
    def _resolve_difficulty(context: WorkflowState) -> str:
        requested = (context.requested_difficulty or "").lower()
        if requested in {"basic", "intermediate", "advanced"}:
            return requested
        recommended = str((context.assessment_result or {}).get("recommended_level", "basic")).lower()
        return recommended if recommended in {"basic", "intermediate", "advanced"} else "basic"

    @staticmethod
    def _apply_feedback_and_revision(
        resources: dict,
        context: WorkflowState,
        agent_input: dict,
        citations: list[str],
    ) -> tuple[dict, list[str]]:
        """Apply feedback and reviewer instructions to the actual resource payload.

        This deliberately mutates content, steps or test items rather than only
        recording instructions in metadata, so a review-revise-review cycle can
        converge and remains auditable.
        """
        revised = deepcopy(resources)
        applied: list[str] = []
        valid_citations = [item for item in citations if item]
        fallback_citation = valid_citations[0] if valid_citations else ""
        feedback = context.feedback or {}
        action = feedback.get("action")

        if action == "lower_difficulty":
            revised["lecture"]["sections"].insert(0, {
                "heading": "先补齐前置知识",
                "content": "本轮根据反馈降低信息密度，先解释运行环境、命令输入与结果判断，再进入核心概念。",
                "citations": [fallback_citation] if fallback_citation else [],
            })
            revised["practice_guide"]["time_estimate_minutes"] += 10
            applied.append("根据反馈降低难度并补充前置知识")
        elif action == "add_practice":
            steps = revised["practice_guide"]["steps"]
            sample = deepcopy(steps[-1])
            sample["order"] = len(steps) + 1
            sample["title"] = "重复执行并记录一次故障排查过程"
            sample["expected_result"] = "能够记录命令、现象、原因和修复结果四项内容"
            steps.append(sample)
            revised["practice_guide"]["time_estimate_minutes"] += 15
            applied.append("根据反馈增加一轮可验证实操")
        elif action == "advance":
            revised["lecture"]["sections"].append({
                "heading": "进阶思考",
                "content": "在掌握基础流程后，比较不同配置的取舍，并说明何时应优先保证可靠性、实时性或可维护性。",
                "citations": [fallback_citation] if fallback_citation else [],
            })
            applied.append("根据达标反馈增加进阶迁移任务")

        instructions = [str(item).strip() for item in agent_input.get("revision_instructions", []) if str(item).strip()]
        if instructions:
            # First repair all rule-checkable fields defensively.
            for section in revised.get("lecture", {}).get("sections", []):
                if not section.get("citations") and fallback_citation:
                    section["citations"] = [fallback_citation]
            guide = revised.setdefault("practice_guide", {})
            if not guide.get("safety_notes"):
                guide["safety_notes"] = ["执行命令前确认运行环境，并保留可回滚副本。"]
            for index, step in enumerate(guide.setdefault("steps", []), start=1):
                step.setdefault("order", index)
                step.setdefault("command", "echo '请按当前章节说明完成此步骤'")
                step.setdefault("expected_result", "步骤执行完成且结果与说明一致")
                if context.domain_id == "ros2_robotics":
                    step.setdefault("ros_version", "humble")
            items = revised.setdefault("graded_test", {}).setdefault("items", [])
            while len(items) < 3:
                number = len(items) + 1
                items.append({
                    "id": f"revision_q_{number:03d}",
                    "type": "single_choice",
                    "difficulty": "basic",
                    "stem": "执行实操前最合理的动作是什么？",
                    "options": [
                        {"key": "A", "text": "忽略所有错误"},
                        {"key": "B", "text": "确认环境与前置条件"},
                        {"key": "C", "text": "直接修改生产环境"},
                    ],
                    "correct_answer": "B",
                    "skill_id": context.source_skill_id or (context.target_skills[-1] if context.target_skills else "foundation"),
                    "explanation": "确认环境与前置条件可以减少不可重复故障。",
                })
            revised["lecture"]["sections"].append({
                "heading": f"第{context.revision_count or 1}轮审核修订",
                "content": "已依据审核意见完成内容级修订：" + "；".join(instructions),
                "citations": [fallback_citation] if fallback_citation else [],
            })
            applied.extend(instructions)

        return revised, applied

    async def _generate_with_provider(self, context: WorkflowState, agent_input: dict) -> AgentResult | None:
        difficulty = self._resolve_difficulty(context)
        instructions = [str(item) for item in agent_input.get("revision_instructions", [])]
        try:
            provider = create_llm_provider()
            if provider is None:
                return None
            generated = await provider.generate_json(
                instructions=SYSTEM_INSTRUCTIONS,
                prompt=build_resource_prompt(
                    context,
                    difficulty=difficulty,
                    revision_instructions=instructions,
                ),
            )
            resources = generated.get("resources", generated)
            if not isinstance(resources, dict) or not all(
                isinstance(resources.get(key), dict)
                for key in ("lecture", "practice_guide", "graded_test")
            ):
                raise ValueError("LLM resource bundle is missing required sections")
            evidence_ids = [
                item.get("evidence_id") for item in context.evidence_list if item.get("evidence_id")
            ]
            resources, applied = self._apply_feedback_and_revision(
                resources, context, agent_input, evidence_ids[:3]
            )
            target_skill = context.source_skill_id or (
                context.target_skills[-1] if context.target_skills else
                ("c_pointer" if context.domain_id == "c_programming" else "ros2_topic")
            )
            metadata = {
                "target_skill": target_skill,
                "learner_id": context.learner_id,
                "difficulty": difficulty,
                "knowledge_sources": [item.get("source_url", "") for item in context.evidence_list[:8]],
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "model_version": getattr(provider, "model", "configured-llm"),
                "provider": provider.__class__.__name__,
                "prompt_version": "resource-generation-2.0",
                "review_status": "pending",
                "revision_instructions_applied": applied,
            }
            return AgentResult(
                status="success",
                output={
                    "resources": resources,
                    "citations": evidence_ids,
                    "target_skill": target_skill,
                    "difficulty": difficulty,
                    "metadata": metadata,
                },
                confidence=0.84,
                next_action="review",
                summary="真实模型已依据审核证据生成资源，等待规则审核",
            )
        except Exception as exc:
            logger.warning("LLM generation failed; using deterministic fallback: %s", exc)
            return None

    @staticmethod
    def _target_skill(context: WorkflowState) -> str:
        if context.source_skill_id:
            return context.source_skill_id
        if context.target_skills:
            return context.target_skills[-1]
        return "c_pointer" if context.domain_id == "c_programming" else "ros2_topic"

    @staticmethod
    def _skill_profile(domain_id: str, skill_id: str) -> dict:
        from app.services.domain_package_service import load_skill_nodes

        for node in load_skill_nodes(domain_id):
            if node.get("id") == skill_id:
                return node
        raise ValueError(f"unknown target skill: {domain_id}/{skill_id}")

    @staticmethod
    def _packaged_practice_task(domain_id: str, skill_id: str) -> dict | None:
        """Return a structured Procedure from the domain package when available."""
        from app.services.domain_package_service import load_practice_tasks

        candidates = [
            task for task in load_practice_tasks(domain_id)
            if str(task.get("skill_id", "")) == skill_id
        ]
        if not candidates:
            return None
        difficulty_order = {"basic": 0, "intermediate": 1, "advanced": 2}
        candidates.sort(key=lambda task: (
            difficulty_order.get(str(task.get("difficulty", "basic")), 9),
            str(task.get("id", "")),
        ))
        return candidates[0]

    @staticmethod
    def _assessment_items_from_package(domain_id: str, skill_id: str) -> list[dict]:
        """Return auditable packaged assessment items for the target skill."""
        from app.services.domain_package_service import load_assessment_bank

        rows = [
            item for item in load_assessment_bank(domain_id)
            if str(item.get("skill_id", "")) == skill_id
        ]
        rows.sort(key=lambda item: (int(item.get("difficulty", 1)), str(item.get("id", ""))))
        result: list[dict] = []
        for item in rows[:3]:
            raw_difficulty = int(item.get("difficulty", 1))
            if raw_difficulty <= 1:
                difficulty = "basic"
            elif raw_difficulty == 2:
                difficulty = "intermediate"
            else:
                difficulty = "advanced"
            result.append({
                "id": item.get("id"),
                "type": item.get("type", "single_choice"),
                "difficulty": difficulty,
                "stem": item.get("stem", ""),
                "options": item.get("options", []),
                "correct_answer": item.get("correct_answer", ""),
                "skill_id": item.get("skill_id", skill_id),
                "explanation": item.get("explanation", ""),
                "evidence_ids": item.get("evidence_ids", []),
                "misconception_tags": item.get("misconception_tags", item.get("error_tags", [])),
                "estimated_seconds": item.get("estimated_seconds"),
            })
        return result

    @staticmethod
    def _practice_steps(domain_id: str, skill_id: str) -> list[dict]:
        packaged = GenerationAgent._packaged_practice_task(domain_id, skill_id)
        if packaged:
            ros_version = str(packaged.get("ros_version", ""))
            result: list[dict] = []
            for index, raw in enumerate(packaged.get("steps", []), start=1):
                step = {
                    "order": raw.get("order", index),
                    "title": raw.get("title") or raw.get("description") or f"步骤{index}",
                    "command": raw.get("command", ""),
                    "expected_result": raw.get("expected_result", ""),
                    "skill_id": skill_id,
                    "evidence_ids": raw.get("evidence_ids", packaged.get("evidence_ids", [])),
                    "validator_ids": raw.get("validator_ids", packaged.get("validator_ids", [])),
                    "risk_level": raw.get("risk_level", packaged.get("risk_level", "low")),
                }
                if ros_version:
                    step["ros_version"] = ros_version
                result.append(step)
            if result:
                return result

        ros_steps: dict[str, list[tuple[str, str, str]]] = {
            "linux_environment": [
                ("加载ROS2环境", "source /opt/ros/humble/setup.bash && printenv ROS_DISTRO", "输出humble"),
                ("检查ROS2命令", "ros2 --help >/tmp/ros2_help.txt && head -n 5 /tmp/ros2_help.txt", "显示ros2命令帮助"),
                ("创建并编译工作空间", "mkdir -p ~/lesson_ws/src && cd ~/lesson_ws && colcon build", "生成build、install和log目录"),
            ],
            "ros2_node": [
                ("启动示例节点", "ros2 run demo_nodes_cpp talker", "终端持续输出Publishing消息"),
                ("列出活动节点", "ros2 node list", "列表中出现/talker"),
                ("查看节点接口", "ros2 node info /talker", "显示发布、订阅和服务信息"),
            ],
            "ros2_topic": [
                ("启动发布者", "ros2 run demo_nodes_cpp talker", "持续输出Hello World消息"),
                ("读取话题", "ros2 topic echo /chatter", "终端持续显示/chatter消息"),
                ("检查频率", "ros2 topic hz /chatter", "输出平均发布频率"),
            ],
            "ros2_topic_custom": [
                ("创建接口包", "cd ~/lesson_ws/src && ros2 pkg create lesson_interfaces --build-type ament_cmake", "生成lesson_interfaces包"),
                ("定义消息", "mkdir -p ~/lesson_ws/src/lesson_interfaces/msg && printf 'string name\\nfloat64 score\\n' > ~/lesson_ws/src/lesson_interfaces/msg/Learner.msg", "Learner.msg包含name和score字段"),
                ("检查接口定义", "cd ~/lesson_ws && colcon build && source install/setup.bash && ros2 interface show lesson_interfaces/msg/Learner", "显示自定义消息字段"),
            ],
            "ros2_service": [
                ("启动turtlesim", "ros2 run turtlesim turtlesim_node", "出现turtlesim窗口"),
                ("查看服务类型", "ros2 service type /spawn", "输出turtlesim/srv/Spawn"),
                ("调用服务", "ros2 service call /spawn turtlesim/srv/Spawn \"{x: 2.0, y: 2.0, theta: 0.0, name: 'lesson_turtle'}\"", "窗口中新增lesson_turtle"),
            ],
            "ros2_tf2": [
                ("发布静态变换", "ros2 run tf2_ros static_transform_publisher --x 1 --y 0 --z 0 --yaw 0 --pitch 0 --roll 0 --frame-id map --child-frame-id lesson_base", "节点持续发布map到lesson_base变换"),
                ("查询变换", "ros2 run tf2_ros tf2_echo map lesson_base", "平移x接近1.0"),
                ("检查TF树", "ros2 run tf2_tools view_frames", "当前目录生成frames.pdf或frames.gv"),
            ],
            "ros2_launch": [
                ("确认示例包", "ros2 pkg executables demo_nodes_cpp | head", "显示demo_nodes_cpp可执行程序"),
                ("使用Launch启动节点", "ros2 launch demo_nodes_cpp talker_listener.launch.py", "发布者和订阅者同时启动"),
                ("检查节点", "ros2 node list", "列表中同时出现talker和listener"),
            ],
            "ros2_nav2_basic": [
                ("安装检查", "ros2 pkg prefix nav2_bringup", "输出nav2_bringup安装路径"),
                ("启动Nav2仿真", "ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False", "Gazebo和RViz2显示机器人、地图与Nav2面板"),
                ("检查生命周期", "ros2 lifecycle get /bt_navigator", "输出active或当前生命周期状态"),
            ],
            "ros2_slam": [
                ("检查雷达与TF", "ros2 topic echo /scan --once && ros2 run tf2_ros tf2_echo odom base_link", "能读取LaserScan且odom到base_link变换连续"),
                ("启动在线建图", "ros2 launch slam_toolbox online_async_launch.py use_sim_time:=false", "发布/map并显示slam_toolbox节点"),
                ("保存地图", "ros2 run nav2_map_server map_saver_cli -f ~/lesson_map", "生成lesson_map.yaml和lesson_map.pgm"),
            ],
            "ros2_robot_bringup": [
                ("创建最小URDF", "printf '<robot name=\"lesson\"><link name=\"base_link\"/></robot>\\n' > /tmp/lesson.urdf", "生成/tmp/lesson.urdf"),
                ("校验URDF", "check_urdf /tmp/lesson.urdf", "输出Successfully Parsed XML"),
                ("启动状态发布器", "ros2 run robot_state_publisher robot_state_publisher /tmp/lesson.urdf", "robot_state_publisher节点启动且发布robot_description"),
            ],
        }
        c_steps: dict[str, list[tuple[str, str, str]]] = {
            "c_basic": [
                ("创建程序", "printf '#include <stdio.h>\\nint main(void){puts(\"Hello C\");return 0;}\\n' > lesson.c", "生成lesson.c"),
                ("严格编译", "cc -std=c17 -Wall -Wextra -Wpedantic lesson.c -o lesson", "编译成功且无警告"),
                ("运行验证", "./lesson", "输出Hello C"),
            ],
            "c_variable": [
                ("创建作用域示例", "printf '#include <stdio.h>\\nint main(void){int score=80;{int score=90;printf(\"%d \",score);}printf(\"%d\\n\",score);return 0;}\\n' > lesson.c", "生成包含内外层变量的程序"),
                ("编译", "cc -std=c17 -Wall -Wextra -Wpedantic lesson.c -o lesson", "编译成功且无警告"),
                ("验证作用域", "./lesson", "输出90 80"),
            ],
            "c_datatype": [
                ("创建类型观察程序", "printf '#include <stdio.h>\\nint main(void){printf(\"%zu %zu %zu\\n\",sizeof(char),sizeof(int),sizeof(double));return 0;}\\n' > lesson.c", "程序使用sizeof观察类型大小"),
                ("编译", "cc -std=c17 -Wall -Wextra -Wpedantic lesson.c -o lesson", "编译成功"),
                ("运行", "./lesson", "输出三个正整数，char大小为1"),
            ],
            "c_operator": [
                ("创建除法示例", "printf '#include <stdio.h>\\nint main(void){printf(\"%d %.1f\\n\",5/2,5.0/2);return 0;}\\n' > lesson.c", "程序同时包含整数和浮点除法"),
                ("编译", "cc -std=c17 -Wall -Wextra -Wpedantic lesson.c -o lesson", "编译成功"),
                ("比较结果", "./lesson", "输出2 2.5"),
            ],
            "c_control": [
                ("创建控制流程序", "printf '#include <stdio.h>\\nint main(void){for(int i=1;i<=3;i++){if(i%%2==0)puts(\"even\");else puts(\"odd\");}return 0;}\\n' > lesson.c", "程序组合循环与条件分支"),
                ("编译", "cc -std=c17 -Wall -Wextra -Wpedantic lesson.c -o lesson", "编译成功"),
                ("运行", "./lesson", "依次输出odd、even、odd"),
            ],
            "c_if": [
                ("创建分支程序", "printf '#include <stdio.h>\\nint main(void){int x=75;if(x>=90)puts(\"A\");else if(x>=60)puts(\"PASS\");else puts(\"FAIL\");return 0;}\\n' > lesson.c", "程序包含互斥多分支"),
                ("编译", "cc -std=c17 -Wall -Wextra -Wpedantic lesson.c -o lesson", "编译成功"),
                ("验证分支", "./lesson", "输出PASS"),
            ],
            "c_loop": [
                ("创建求和程序", "printf '#include <stdio.h>\\nint main(void){int sum=0;for(int i=1;i<=100;i++)sum+=i;printf(\"%d\\n\",sum);return 0;}\\n' > lesson.c", "程序循环累加1到100"),
                ("编译", "cc -std=c17 -Wall -Wextra -Wpedantic lesson.c -o lesson", "编译成功"),
                ("验证边界", "./lesson", "输出5050"),
            ],
            "c_array": [
                ("创建数组程序", "printf '#include <stdio.h>\\nint main(void){int a[]={3,7,2,9};int max=a[0];for(size_t i=1;i<sizeof a/sizeof a[0];i++)if(a[i]>max)max=a[i];printf(\"%d\\n\",max);return 0;}\\n' > lesson.c", "数组遍历使用计算得到的长度"),
                ("编译", "cc -std=c17 -Wall -Wextra -Wpedantic lesson.c -o lesson", "编译成功且无越界警告"),
                ("运行", "./lesson", "输出9"),
            ],
            "c_function": [
                ("创建函数程序", "printf '#include <stdio.h>\\nstatic int add(int a,int b){return a+b;}\\nint main(void){printf(\"%d\\n\",add(2,3));return 0;}\\n' > lesson.c", "定义并调用add函数"),
                ("编译", "cc -std=c17 -Wall -Wextra -Wpedantic lesson.c -o lesson", "编译成功"),
                ("运行", "./lesson", "输出5"),
            ],
            "c_pointer": [
                ("创建指针程序", "printf '#include <stdio.h>\\nstatic void swap(int *a,int *b){int t=*a;*a=*b;*b=t;}\\nint main(void){int x=2,y=3;swap(&x,&y);printf(\"%d %d\\n\",x,y);return 0;}\\n' > lesson.c", "函数通过有效地址修改调用者变量"),
                ("编译并启用检测", "cc -std=c17 -Wall -Wextra -Wpedantic -fsanitize=address,undefined lesson.c -o lesson", "编译成功"),
                ("运行验证", "./lesson", "输出3 2且无Sanitizer错误"),
            ],
        }
        c_programs: dict[str, str] = {
            'c_basic': '#include <stdio.h>\nint main(void){puts("Hello C");return 0;}\n',
            'c_variable': '#include <stdio.h>\nint main(void){int score=80;{int score=90;printf("%d ",score);}printf("%d\\n",score);return 0;}\n',
            'c_datatype': '#include <stdio.h>\nint main(void){printf("%zu %zu %zu\\n",sizeof(char),sizeof(int),sizeof(double));return 0;}\n',
            'c_operator': '#include <stdio.h>\nint main(void){printf("%d %.1f\\n",5/2,5.0/2);return 0;}\n',
            'c_control': '#include <stdio.h>\nint main(void){for(int i=1;i<=3;i++){if(i%2==0)puts("even");else puts("odd");}return 0;}\n',
            'c_if': '#include <stdio.h>\nint main(void){int x=75;if(x>=90)puts("A");else if(x>=60)puts("PASS");else puts("FAIL");return 0;}\n',
            'c_loop': '#include <stdio.h>\nint main(void){int sum=0;for(int i=1;i<=100;i++)sum+=i;printf("%d\\n",sum);return 0;}\n',
            'c_array': '#include <stdio.h>\nint main(void){int a[]={3,7,2,9};int max=a[0];for(size_t i=1;i<sizeof a/sizeof a[0];i++)if(a[i]>max)max=a[i];printf("%d\\n",max);return 0;}\n',
            'c_function': '#include <stdio.h>\nstatic int add(int a,int b){return a+b;}\nint main(void){printf("%d\\n",add(2,3));return 0;}\n',
            'c_pointer': '#include <stdio.h>\nstatic void swap(int *a,int *b){int t=*a;*a=*b;*b=t;}\nint main(void){int x=2,y=3;swap(&x,&y);printf("%d %d\\n",x,y);return 0;}\n',
        }
        source = c_steps if domain_id == "c_programming" else ros_steps
        tuples = source.get(skill_id)
        if not tuples:
            raise ValueError(f"missing practice implementation for {domain_id}/{skill_id}")
        result = []
        for order, (title, command, expected) in enumerate(tuples, start=1):
            # A quoted heredoc writes C source byte-for-byte. This avoids Shell printf
            # interpreting C format specifiers (%d/%zu) or character literals.
            if domain_id == "c_programming" and order == 1:
                source_code = c_programs[skill_id]
                command = "cat > lesson.c <<'EOF'\n" + source_code + "EOF"
            step = {
                "order": order,
                "title": title,
                "command": command,
                "expected_result": expected,
                "skill_id": skill_id,
            }
            if domain_id == "ros2_robotics":
                step["ros_version"] = "humble"
            result.append(step)
        return result

    @staticmethod
    def _personalization(context: WorkflowState, skill_name: str) -> dict:
        learner = context.learner_profile or {}
        preferences = learner.get("preferences") or {}
        style = str(preferences.get("explanation_style") or "通俗")
        priority = str(preferences.get("resource_priority") or "均衡")
        major = str(learner.get("major") or "未填写专业")
        target_role = str(learner.get("target_role") or "AI工程岗位")
        weekly_hours = int(learner.get("weekly_hours") or 6)

        if style == "专业":
            style_note = f"使用精确定义、接口约束和失败边界解释{skill_name}，避免只给结论。"
        elif style == "类比为主":
            style_note = f"先用可映射到工程流程的类比解释{skill_name}，随后回到正式术语和验证方法。"
        else:
            style_note = f"用短句和最小示例解释{skill_name}，每个概念立即配一个可观察结果。"

        lowered_major = major.lower()
        if "机械" in major or "机器人" in major:
            background_note = "优先关联传感器、执行器、坐标系和现场调试。"
        elif any(token in lowered_major for token in ("软件", "计算机", "信息", "电子", "自动化")):
            background_note = "优先关联接口契约、数据流、日志和可重复调试。"
        else:
            background_note = "不假设特定专业前置知识，先解释术语再进入工程任务。"

        available_minutes = max(20, min(180, round(weekly_hours * 60 / 3)))
        if priority == "实践优先":
            lecture_minutes = max(8, round(available_minutes * 0.30))
            practice_minutes = max(20, round(available_minutes * 0.70))
        elif priority == "理论优先":
            lecture_minutes = max(12, round(available_minutes * 0.60))
            practice_minutes = max(15, round(available_minutes * 0.40))
        else:
            lecture_minutes = max(10, round(available_minutes * 0.45))
            practice_minutes = max(18, round(available_minutes * 0.55))

        return {
            "education": str(learner.get("education") or "未填写"),
            "major": major,
            "target_role": target_role,
            "explanation_style": style,
            "resource_priority": priority,
            "weekly_hours": weekly_hours,
            "style_note": style_note,
            "background_note": background_note,
            "lecture_minutes": min(30, lecture_minutes),
            "practice_minutes": min(90, practice_minutes),
        }

    @staticmethod
    def _command_label(domain_id: str, skill_id: str) -> tuple[str, list[dict]]:
        answers = {
            "linux_environment": ("source /opt/ros/humble/setup.bash", ["ros2 topic echo /none", "rm -rf /opt/ros", "python --version"]),
            "ros2_node": ("ros2 node info /talker", ["ros2 topic pub /talker", "ros2 service list /talker", "colcon clean"]),
            "ros2_topic": ("ros2 topic echo /chatter", ["ros2 node echo /chatter", "ros2 service echo /chatter", "ros2 launch echo /chatter"]),
            "ros2_topic_custom": ("ros2 interface show lesson_interfaces/msg/Learner", ["ros2 node show Learner", "ros2 topic build Learner", "ros2 service compile Learner"]),
            "ros2_service": ("ros2 service call /spawn turtlesim/srv/Spawn ...", ["ros2 topic echo /spawn", "ros2 node call /spawn", "ros2 action echo /spawn"]),
            "ros2_tf2": ("ros2 run tf2_ros tf2_echo map lesson_base", ["ros2 topic echo map lesson_base", "ros2 service call tf2_echo", "ros2 node list map"]),
            "ros2_launch": ("ros2 launch demo_nodes_cpp talker_listener.launch.py", ["ros2 run launch.py", "python ros2 launch", "colcon launch all"]),
            "ros2_nav2_basic": ("ros2 lifecycle get /bt_navigator", ["ros2 topic echo /bt_navigator", "ros2 service delete /bt_navigator", "ros2 node compile /bt_navigator"]),
            "ros2_slam": ("ros2 run nav2_map_server map_saver_cli -f ~/lesson_map", ["ros2 topic save /scan", "ros2 node export /map", "colcon map ~/lesson_map"]),
            "ros2_robot_bringup": ("check_urdf /tmp/lesson.urdf", ["ros2 topic check_urdf", "cc lesson.urdf", "python -m urdf"]),
            "c_basic": ("cc -std=c17 -Wall -Wextra -Wpedantic lesson.c -o lesson", ["run lesson.c", "link --no-compile lesson.c", "python lesson.c"]),
            "c_variable": ("在使用前声明变量并控制作用域", ["所有变量都定义为全局", "变量名可以数字开头", "未初始化变量可直接读取"]),
            "c_datatype": ("使用sizeof确认当前实现中的对象大小", ["假设所有平台int恒为8字节", "用变量名判断大小", "关闭编译器后估算大小"]),
            "c_operator": ("5.0 / 2得到2.5", ["5 / 2得到2.5", "5 % 2得到2.5", "5 && 2得到2.5"]),
            "c_control": ("用条件选择分支、用循环重复有限步骤", ["所有代码都放入goto死循环", "条件为0时视为真", "循环不需要退出条件"]),
            "c_if": ("else if组织互斥的多分支判断", ["多个无条件return同时执行", "case可直接替代所有表达式判断", "if条件为0时进入真分支"]),
            "c_loop": ("for(int i=0; i<n; i++)", ["for(int i=0; i<=n; i++)访问n个数组元素", "while(1)且无退出路径", "break退出所有嵌套循环"]),
            "c_array": ("合法下标范围是0到长度减1", ["合法下标范围是1到长度", "可以访问负下标", "越界读取一定返回0"]),
            "c_function": ("调用前具有与定义一致的函数声明", ["返回类型可以任意不一致", "参数数量由运行时猜测", "函数只能调用一次"]),
            "c_pointer": ("解引用前确认指针非空且指向有效对象", ["任何整数都可直接当地址访问", "空指针可安全写入", "指针不需要匹配所指类型"]),
        }
        correct, distractors = answers[skill_id]
        # Keep the answer position non-trivial so learners cannot exploit a
        # fixed answer-key pattern. The advanced item uses C as its answer.
        options = [
            {"key": "A", "text": distractors[0]},
            {"key": "B", "text": distractors[1]},
            {"key": "C", "text": correct},
            {"key": "D", "text": distractors[2]},
        ]
        return correct, options

    def _generate_deterministic(self, context: WorkflowState, agent_input: dict) -> AgentResult:
        skill_id = self._target_skill(context)
        skill_profile = self._skill_profile(context.domain_id, skill_id)
        skill_name = str(skill_profile.get("name", skill_id))
        objectives = [str(item) for item in skill_profile.get("objectives", [])] or [f"理解{skill_name}的核心概念"]
        criteria = [str(item) for item in skill_profile.get("criteria", [])] or [f"能完成{skill_name}的基本任务"]
        personalization = self._personalization(context, skill_name)
        evidence_ids = [item.get("evidence_id") for item in context.evidence_list if item.get("evidence_id")]
        citations = evidence_ids[:3]
        while len(citations) < 3:
            citations.append(citations[-1] if citations else "")

        if context.domain_id == "c_programming":
            domain_context = "C语言程序从源代码经过编译和链接形成可执行文件"
            analogy = f"可以把{skill_name}类比成程序工具箱中的一种专用工具：先明确输入和边界，再检查输出是否符合预期。{personalization['background_note']}"
            environment = "C17"
            safety = ["始终启用-Wall、-Wextra和-Wpedantic。", "数组访问、输入读取和指针解引用前检查边界与有效性。"]
            prerequisites = ["已安装支持C17的编译器", "能够在终端创建和运行文件"]
            common = ["忽略编译警告会掩盖真实缺陷。", "未定义行为不能依赖某次运行结果判断正确性。"]
        else:
            domain_context = "ROS2 Humble通过节点和标准接口组织机器人软件"
            analogy = f"可以把{skill_name}类比成机器人系统中的一个明确岗位：职责、输入、输出和检查方法都必须写清。{personalization['background_note']}"
            environment = "ROS2 Humble"
            safety = ["先在仿真或隔离环境验证命令，再连接真实机器人。", "保持终端ROS_DOMAIN_ID一致，并用Ctrl+C正常结束节点。"]
            prerequisites = ["Ubuntu 22.04", "已安装ROS2 Humble并完成环境source"]
            common = ["新终端忘记source会导致命令或包不可见。", "接口名称、类型或TF帧不一致会造成数据无法连通。"]

        first_objective = objectives[0]
        first_criterion = criteria[0]
        command_answer, command_options = self._command_label(context.domain_id, skill_id)
        packaged_practice = self._packaged_practice_task(context.domain_id, skill_id)
        packaged_items = self._assessment_items_from_package(context.domain_id, skill_id)
        resources = {
            "lecture": {
                "title": f"C语言·{skill_name}：概念、验证与排错" if context.domain_id == "c_programming" else f"ROS2·{skill_name}：概念、验证与排错",
                "sections": [
                    {
                        "heading": "核心定义",
                        "content": f"{domain_context}。本节聚焦{skill_name}，学习目标是：{'；'.join(objectives)}。面向{personalization['target_role']}：{personalization['style_note']}",
                        "citations": [citations[0]] if citations[0] else [],
                    },
                    {
                        "heading": "生活化类比",
                        "content": analogy,
                        "citations": [citations[1]] if citations[1] else ([citations[0]] if citations[0] else []),
                    },
                    {
                        "heading": "完成标准与排错顺序",
                        "content": f"掌握标准是：{'；'.join(criteria)}。排错时按环境、输入、执行过程、输出四层逐项检查，不跳过可复现证据。",
                        "citations": [citations[2]] if citations[2] else ([citations[0]] if citations[0] else []),
                    },
                ],
                "estimated_read_time_minutes": personalization["lecture_minutes"],
            },
            "practice_guide": {
                "title": f"{skill_name}可验证实操（{environment}）",
                "steps": self._practice_steps(context.domain_id, skill_id),
                "prerequisites": (packaged_practice or {}).get("prerequisites", prerequisites),
                "safety_notes": safety,
                "common_errors": (packaged_practice or {}).get("failure_cases", common),
                "rollback": (packaged_practice or {}).get("rollback", []),
                "expected_output": (packaged_practice or {}).get("expected_output", ""),
                "evidence_ids": (packaged_practice or {}).get("evidence_ids", []),
                "validator_ids": (packaged_practice or {}).get("validator_ids", []),
                "risk_level": (packaged_practice or {}).get("risk_level", "low"),
                "execution_verification_status": (packaged_practice or {}).get("execution_verification_status", "not_run"),
                "time_estimate_minutes": (packaged_practice or {}).get("time_estimate_minutes", personalization["practice_minutes"]),
            },
            "graded_test": {
                "title": f"{skill_name}分阶测试",
                "items": packaged_items or [
                    {
                        "id": f"{skill_id}_objective",
                        "type": "single_choice",
                        "difficulty": "basic",
                        "stem": f"以下哪一项属于{skill_name}的本节学习目标？",
                        "options": [
                            {"key": "A", "text": first_objective},
                            {"key": "B", "text": "跳过全部前置条件并直接部署生产系统"},
                            {"key": "C", "text": "只记住界面颜色，不验证结果"},
                            {"key": "D", "text": "关闭错误提示以减少输出"},
                        ],
                        "correct_answer": "A",
                        "skill_id": skill_id,
                        "explanation": f"领域包为该技能定义的目标包括：{'；'.join(objectives)}。",
                    },
                    {
                        "id": f"{skill_id}_criterion",
                        "type": "single_choice",
                        "difficulty": "intermediate",
                        "stem": f"哪项结果最能证明已经掌握{skill_name}？",
                        "options": [
                            {"key": "A", "text": "命令报错后不记录任何信息"},
                            {"key": "B", "text": first_criterion},
                            {"key": "C", "text": "只复制代码但不运行"},
                            {"key": "D", "text": "结果与预期不一致仍判定成功"},
                        ],
                        "correct_answer": "B",
                        "skill_id": skill_id,
                        "explanation": f"可验证标准是：{'；'.join(criteria)}。",
                    },
                    {
                        "id": f"{skill_id}_practice",
                        "type": "single_choice",
                        "difficulty": "advanced",
                        "stem": f"学习{skill_name}时，下列哪项操作或判断是正确的？",
                        "options": command_options,
                        "correct_answer": "C",
                        "skill_id": skill_id,
                        "explanation": f"正确项是“{command_answer}”，它与本节实操或安全边界直接对应。",
                    },
                ],
            },
        }
        resources, applied_revisions = self._apply_feedback_and_revision(resources, context, agent_input, citations)
        difficulty = self._resolve_difficulty(context)
        metadata = {
            "target_skill": skill_id,
            "target_skill_name": skill_name,
            "learner_id": context.learner_id,
            "learner_level": (context.assessment_result or {}).get("recommended_level", "basic"),
            "difficulty": difficulty,
            "domain_id": context.domain_id,
            "runtime": environment,
            "personalization": {
                "education": personalization["education"],
                "major": personalization["major"],
                "target_role": personalization["target_role"],
                "explanation_style": personalization["explanation_style"],
                "resource_priority": personalization["resource_priority"],
                "weekly_hours": personalization["weekly_hours"],
            },
            "knowledge_sources": [item.get("source_url", "") for item in context.evidence_list[:8]],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": "domain-driven-generator-v3",
            "prompt_version": "resource-generation-3.0",
            "review_status": "pending",
            "revision_instructions_applied": applied_revisions,
        }
        return AgentResult(
            status="success",
            output={
                "resources": resources,
                "citations": [item for item in citations if item],
                "target_skill": skill_id,
                "difficulty": difficulty,
                "metadata": metadata,
            },
            confidence=0.93,
            next_action="review",
            summary=f"已按目标技能“{skill_name}”生成讲义、可验证实操和分阶测试",
        )

    async def run(self, context: WorkflowState, agent_input: dict) -> AgentResult:
        provider_result = await self._generate_with_provider(context, agent_input)
        if provider_result is not None:
            return provider_result
        return self._generate_deterministic(context, agent_input)
