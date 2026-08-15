"""Low-cost validation gates used by the runtime ProofGraph.

No command is executed here. Shell syntax is parsed with ``bash -n`` and all
other checks are static. Validators that require a live ROS graph explicitly
return ``unknown`` rather than pretending they ran.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from typing import Any
import xml.etree.ElementTree as ET

import yaml

from app.services.domain_package_service import load_validator_registry


_DESTRUCTIVE = [
    (re.compile(r"\brm\s+-rf\s+/(?:\s|$)", re.I), "禁止递归删除根目录"),
    (re.compile(r"\bmkfs(?:\.|\s)", re.I), "格式化文件系统属于破坏性操作"),
    (re.compile(r"\bdd\s+if=.*\bof=/dev/", re.I), "直接写块设备属于破坏性操作"),
    (re.compile(r"\b(?:fdisk|parted)\b", re.I), "磁盘分区操作需要人工确认"),
    (re.compile(r"\b(?:shutdown|reboot|poweroff)\b", re.I), "系统电源操作需要人工确认"),
]
_CONFIRM = [
    (re.compile(r"\bsudo\b", re.I), "sudo 操作需要人工确认"),
    (re.compile(r"\b(?:iptables|ufw|nmcli)\b", re.I), "网络配置变更需要人工确认"),
    (re.compile(r"/dev/(?:sd|nvme|mmcblk|tty)", re.I), "宿主设备访问需要人工确认"),
    (re.compile(r"\b(?:flash|firmware)\b", re.I), "固件操作需要人工确认"),
]


@dataclass(frozen=True)
class ValidationResultData:
    validator_id: str
    status: str  # pass / fail / unknown / needs_confirmation
    reason: str
    runtime_ms: int = 0
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class ValidationService:
    LIVE_ROS_VALIDATORS = {
        "val_ros_graph", "val_qos", "val_tf", "val_nav2", "val_slam",
    }

    def __init__(self, domain_id: str):
        self.domain_id = domain_id
        self.registry = {str(row.get("id")): row for row in load_validator_registry(domain_id)}

    @staticmethod
    def shell_safety(command: str) -> ValidationResultData:
        command = (command or "").strip()
        if not command:
            return ValidationResultData("val_command_safety", "unknown", "没有可检查的命令")
        for pattern, reason in _DESTRUCTIVE:
            if pattern.search(command):
                return ValidationResultData("val_command_safety", "fail", reason)
        for pattern, reason in _CONFIRM:
            if pattern.search(command):
                return ValidationResultData("val_command_safety", "needs_confirmation", reason)
        try:
            proc = subprocess.run(
                ["bash", "-n", "-c", command],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return ValidationResultData("val_command_safety", "unknown", f"无法完成 shell 静态语法检查：{exc}")
        if proc.returncode != 0:
            return ValidationResultData(
                "val_command_safety", "fail", "shell 语法检查失败",
                details={"stderr": proc.stderr[-500:]},
            )
        return ValidationResultData("val_command_safety", "pass", "命令通过静态安全与 shell 语法检查")

    @staticmethod
    def python_syntax(code: str) -> ValidationResultData:
        try:
            ast.parse(code)
            return ValidationResultData("python_ast", "pass", "Python AST 解析通过")
        except SyntaxError as exc:
            return ValidationResultData("python_ast", "fail", f"Python 语法错误：{exc.msg}")

    @staticmethod
    def structured_syntax(text: str, kind: str) -> ValidationResultData:
        try:
            if kind == "json":
                json.loads(text)
            elif kind == "yaml":
                yaml.safe_load(text)
            elif kind == "xml":
                ET.fromstring(text)
            else:
                return ValidationResultData(f"{kind}_syntax", "unknown", f"不支持的结构化格式：{kind}")
        except Exception as exc:
            return ValidationResultData(f"{kind}_syntax", "fail", f"{kind.upper()} 解析失败：{exc}")
        return ValidationResultData(f"{kind}_syntax", "pass", f"{kind.upper()} 解析通过")

    def validate(self, validator_id: str, claim: dict, *, version_filter: str | None = None) -> ValidationResultData:
        validator_id = str(validator_id or "").strip()
        command = str(claim.get("command", ""))
        code = str(claim.get("code", ""))

        if validator_id == "val_command_safety":
            return self.shell_safety(command)
        if validator_id == "val_ros_env":
            static = self.shell_safety(command) if command else ValidationResultData(validator_id, "pass", "无命令需要安全检查")
            if static.status in {"fail", "needs_confirmation"}:
                return ValidationResultData(validator_id, static.status, static.reason)
            ros_version = str(claim.get("ros_version", "")).lower()
            if version_filter and ros_version and str(version_filter).lower() != ros_version:
                return ValidationResultData(validator_id, "fail", "声明 ROS 版本与工作流版本约束不一致")
            return ValidationResultData(validator_id, "pass", "ROS 环境声明通过静态版本/命令检查")
        if validator_id == "val_launch":
            if command and "ros2 launch" not in command:
                return ValidationResultData(validator_id, "unknown", "未发现可静态确认的 ros2 launch 命令")
            return ValidationResultData(validator_id, "pass", "Launch 命令形态通过静态检查")
        if validator_id == "val_urdf":
            lower = command.lower()
            if command and not any(token in lower for token in ("check_urdf", "xacro", "urdf")):
                return ValidationResultData(validator_id, "unknown", "缺少可静态核验的 URDF/Xacro 输入")
            return ValidationResultData(validator_id, "pass", "URDF/Xacro 检查命令形态有效")
        if validator_id == "val_device":
            safety = self.shell_safety(command)
            if safety.status == "pass":
                return ValidationResultData(validator_id, "unknown", "设备权限需要目标机器环境，静态安全检查已通过")
            return ValidationResultData(validator_id, safety.status, safety.reason)
        if validator_id in self.LIVE_ROS_VALIDATORS:
            safety = self.shell_safety(command) if command else ValidationResultData(validator_id, "pass", "无危险命令")
            if safety.status in {"fail", "needs_confirmation"}:
                return ValidationResultData(validator_id, safety.status, safety.reason)
            return ValidationResultData(validator_id, "unknown", "该验证器需要在线 ROS 图/TF/QoS 状态，当前仅完成静态门控")
        if code:
            return self.python_syntax(code)
        if validator_id in self.registry:
            return ValidationResultData(validator_id, "unknown", "验证器已有规范，但尚无当前环境可执行实现")
        return ValidationResultData(validator_id or "unspecified", "unknown", "未注册验证器")
