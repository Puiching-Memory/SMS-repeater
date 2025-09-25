#!/usr/bin/env python3
"""MQTT 系统消息监听客户端。

该脚本使用 `aiomqtt` 提供的异步客户端能力，持续监听指定主题（默认 `$SYS/#`）
以获取服务器当前的状态消息。

Contract:
- 输入: 目标主机、端口、凭据以及一个或多个订阅主题（可从命令行或环境变量提供）。
- 处理: 建立到 MQTT Broker 的安全连接，订阅主题并逐条解析消息。
- 输出: 将时间戳、主题、QoS、保留标记与消息内容打印到标准输出。
- 异常: 连接异常可按配置自动重连；解码失败时退回十六进制表示。

Edge cases handled:
- 凭据缺失（立即报错并退出）。
- 主题未提供（退回 `$SYS/#` 以获取服务器状态）。
- 消息内容非 UTF-8 时的解码问题（可配置错误策略，必要时自动退回 HEX 表示）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Iterable, Sequence

try:
    from windows_toasts import Toast, WindowsToaster
except ImportError:  # pragma: no cover - windows-toasts may缺失
    Toast = None
    WindowsToaster = None

try:
    from aiomqtt import Client, Message, MqttError
except ImportError:  # pragma: no cover - fallback for alternative packaging
    import aiomqtt

    Client = aiomqtt.Client  # type: ignore[attr-defined]
    Message = getattr(aiomqtt, "Message", object)  # type: ignore[misc]
    MqttError = getattr(aiomqtt, "MqttError", Exception)  # type: ignore[misc]

LOGGER = logging.getLogger("sms_repeater.client")
DEFAULT_TOPICS = ("$SYS/#",)
_TOAST_APP_NAME = "SMS-Repeater"
_windows_toaster: WindowsToaster | None = None  # type: ignore[name-defined]
_windows_toast_disabled = False
_CODE_PATTERN = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")
_CODE_KEYWORDS = ("验证码", "校验码", "驗證碼", "verification code", "auth code")


def ensure_windows_event_loop_policy(logger: logging.Logger) -> None:
    """在 Windows 上切换到支持 add_reader/add_writer 的事件循环策略。"""
    if not sys.platform.startswith("win"):
        return

    policy_name = "WindowsSelectorEventLoopPolicy"
    if not hasattr(asyncio, policy_name):
        logger.debug("当前 Python/asyncio 不支持 %s，跳过事件循环调整。", policy_name)
        return

    policy_cls = getattr(asyncio, policy_name)
    current_policy = asyncio.get_event_loop_policy()
    if isinstance(current_policy, policy_cls):
        return

    asyncio.set_event_loop_policy(policy_cls())
    logger.info("已切换到 %s 以兼容 aiomqtt。", policy_name)


def _extract_verification_code(snippets: Iterable[str]) -> str | None:
    candidates: list[str] = []
    for snippet in snippets:
        if not snippet:
            continue
        candidates.append(snippet)

        lowered = snippet.lower()
        has_keyword = any(keyword in snippet for keyword in _CODE_KEYWORDS)
        if not has_keyword:
            has_keyword = any(keyword in lowered for keyword in ("verification code", "auth code"))

        if has_keyword:
            match = _CODE_PATTERN.search(snippet)
            if match:
                return match.group(1)

    merged = "\n".join(candidates)
    matches = _CODE_PATTERN.findall(merged)
    if len(matches) == 1:
        return matches[0]
    if matches:
        return matches[0]
    return None


def prepare_notification_content(topic: str, payload: str) -> tuple[str, str]:
    """将原始主题与负载整理成适合通知展示的标题与正文。"""
    default_headline = f"MQTT: {topic or '<unknown>'}"
    raw_text = (payload or "").strip()
    snippets: list[str] = []

    if not raw_text:
        return default_headline, "<空消息>"

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        body = raw_text
        snippets.append(raw_text)
    else:
        if isinstance(data, dict):
            lines: list[str] = []
            msg = data.get("msg")
            if isinstance(msg, str) and msg.strip():
                msg_clean = msg.strip()
                lines.append(msg_clean)
                snippets.append(msg_clean)

            for key, value in data.items():
                if key == "msg":
                    continue
                if value is None:
                    continue
                if isinstance(value, (dict, list)):
                    serialized = json.dumps(value, ensure_ascii=False)
                    lines.append(f"{key}: {serialized}")
                    snippets.append(serialized)
                else:
                    lines.append(f"{key}: {value}")
                    if isinstance(value, str):
                        snippets.append(value)

            body = "\n".join(lines) if lines else raw_text
            if not snippets:
                snippets.append(raw_text)
        elif isinstance(data, list):
            pretty = json.dumps(data, ensure_ascii=False, indent=2)
            body = pretty
            snippets.append(pretty)
        else:
            body = json.dumps(data, ensure_ascii=False)
            snippets.append(body)

    snippets.append(body)
    code = _extract_verification_code(snippets)
    headline = code or default_headline

    return headline, body


def send_windows_notification(title: str, body: str, logger: logging.Logger) -> None:
    if not sys.platform.startswith("win"):
        return

    global _windows_toaster, _windows_toast_disabled

    if _windows_toast_disabled:
        return

    if WindowsToaster is None or Toast is None:
        if not _windows_toast_disabled:
            logger.warning(
                "缺少 windows-toasts 包，无法发送 Windows 通知。请运行 `pip install windows-toasts`。"
            )
            _windows_toast_disabled = True
        return

    if _windows_toaster is None:
        try:
            _windows_toaster = WindowsToaster(_TOAST_APP_NAME)
        except Exception:
            _windows_toast_disabled = True
            logger.exception("初始化 Windows 通知失败")
            return

    body = (body or "<空消息>").replace("\r", "")
    lines = [line.strip() for line in body.split("\n")]
    cleaned_lines = [line for line in lines if line]
    if not cleaned_lines:
        cleaned_lines = ["<空消息>"]

    max_lines = 6
    truncated = cleaned_lines[:max_lines]
    if len(cleaned_lines) > max_lines:
        truncated.append("…")

    safe_body = "\n".join(truncated)
    if len(safe_body) > 500:
        safe_body = safe_body[:497] + "…"

    safe_title = title.strip() or "MQTT 通知"
    if len(safe_title) > 200:
        safe_title = safe_title[:197] + "…"

    try:
        toast = Toast([safe_title, safe_body])
        _windows_toaster.show_toast(toast)  # type: ignore[union-attr]
    except Exception:
        _windows_toast_disabled = True
        logger.exception("发送 Windows 通知失败")


def parse_topics(raw_topics: Sequence[str] | None) -> list[str]:
    """将命令行/环境变量提供的主题字符串解析为唯一列表。"""
    if not raw_topics:
        return list(DEFAULT_TOPICS)

    topics: list[str] = []
    for entry in raw_topics:
        for topic in entry.split(","):
            topic = topic.strip()
            if topic and topic not in topics:
                topics.append(topic)

    return topics or list(DEFAULT_TOPICS)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="使用 aiomqtt 持续监听 MQTT 服务器的系统消息。",
        epilog=(
            "可以通过环境变量 MQTT_USERNAME 和 MQTT_PASSWORD 预先配置凭据。"
        ),
    )

    parser.add_argument("--host", default="127.0.0.1", help="MQTT 服务器主机名或 IP。")
    parser.add_argument(
        "--port",
        type=int,
        default=1883,
        help="MQTT 服务器端口号（默认 1883）。",
    )
    parser.add_argument(
        "-u",
        "--username",
        default=os.getenv("MQTT_USERNAME"),
        help="认证用用户名（默认读取 MQTT_USERNAME 环境变量）。",
    )
    parser.add_argument(
        "-p",
        "--password",
        default=os.getenv("MQTT_PASSWORD"),
        help="认证用密码（默认读取 MQTT_PASSWORD 环境变量）。",
    )
    parser.add_argument(
        "-t",
        "--topic",
        "--topics",
        dest="topics",
        action="append",
        metavar="TOPIC",
        help="要订阅的主题，可多次使用或用逗号分隔。默认 `$SYS/#`。",
    )
    parser.add_argument(
        "--client-id",
        default=None,
        help="自定义 Client ID（默认为随机分配）。",
    )
    parser.add_argument(
        "--keepalive",
        type=int,
        default=60,
        help="MQTT keepalive 秒数（默认 60）。",
    )
    parser.add_argument(
        "--qos",
        type=int,
        default=1,
        choices=(0, 1, 2),
        help="订阅 QoS 等级（0/1/2，默认 1）。",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="消息解码使用的字符集（默认 utf-8）。",
    )
    parser.add_argument(
        "--errors",
        dest="decode_errors",
        default="replace",
        choices=("strict", "ignore", "replace", "backslashreplace"),
        help="消息解码出错时的处理策略（默认 replace）。",
    )
    parser.add_argument(
        "--raw-payload",
        action="store_true",
        help="以十六进制显示负载，忽略文本解码。",
    )
    parser.add_argument(
        "--utc",
        action="store_true",
        help="时间戳使用 UTC（默认使用本地时区）。",
    )
    parser.add_argument(
        "--reconnect-delay",
        type=float,
        default=5.0,
        help=(
            "发生连接错误后自动重连前的等待秒数；<=0 表示不自动重连。"
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL，默认 INFO）。",
    )

    return parser


def resolve_log_level(level_name: str) -> int:
    """解析用户传入的日志级别字符串。"""
    if level_name.isdigit():
        return int(level_name)

    mapped = getattr(logging, level_name.upper(), None)
    if isinstance(mapped, int):
        return mapped

    raise ValueError(f"未知的日志级别: {level_name!r}")


def current_timestamp(use_utc: bool) -> str:
    """格式化当前时间戳。"""
    now = datetime.now(timezone.utc if use_utc else None)
    return now.isoformat(timespec="seconds")


def render_payload(message: Message, encoding: str, errors: str, raw: bool) -> str:
    """根据配置渲染消息负载。"""
    payload = getattr(message, "payload", b"")
    if not isinstance(payload, (bytes, bytearray)):
        return str(payload)

    payload_bytes = bytes(payload)
    if raw:
        return payload_bytes.hex()

    try:
        return payload_bytes.decode(encoding, errors=errors)
    except UnicodeDecodeError:
        LOGGER.warning(
            "无法按 %s 解码主题 %s 的负载，退回十六进制显示。",
            encoding,
            getattr(message, "topic", "<unknown>"),
        )
        return payload_bytes.hex()


def format_message_line(
    message: Message, args: argparse.Namespace, payload: str | None = None
) -> str:
    """生成要输出的单行文本。"""
    timestamp = current_timestamp(args.utc)
    topic = getattr(message, "topic", "<unknown>")
    qos = getattr(message, "qos", "?")
    retain = getattr(message, "retain", False)
    if payload is None:
        payload = render_payload(
            message, args.encoding, args.decode_errors, args.raw_payload
        )

    props = getattr(message, "properties", None)
    props_display = f" props={props}" if props else ""

    return (
        f"[{timestamp}] topic={topic} qos={qos} retain={retain}{props_display}\n"
        f"  payload: {payload}"
    )


def validate_credentials(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """确保用户名与密码已经提供。"""
    if args.username is None:
        parser.error("缺少用户名：请使用 --username/-u 或设置环境变量 MQTT_USERNAME。")
    if args.password is None:
        parser.error("缺少密码：请使用 --password/-p 或设置环境变量 MQTT_PASSWORD。")


def sanitize_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """解析并校验命令行参数。"""
    args = parser.parse_args()
    args.topics = parse_topics(args.topics)
    validate_credentials(args, parser)

    try:
        log_level = resolve_log_level(args.log_level)
    except ValueError as exc:
        parser.error(str(exc))
    else:
        args.log_level = log_level

    return args


def summarize_topics(topics: Iterable[str]) -> str:
    """将主题列表格式化为便于日志输出的字符串。"""
    return ", ".join(topics)


async def listen_loop(args: argparse.Namespace) -> None:
    """主监听循环，负责自动重连与消息输出。"""
    reconnect = args.reconnect_delay

    while True:
        try:
            LOGGER.debug(
                "尝试连接 MQTT 服务器 %s:%s (client_id=%s)",
                args.host,
                args.port,
                args.client_id,
            )
            async with Client(
                args.host,
                port=args.port,
                username=args.username,
                password=args.password,
                identifier=args.client_id,
                keepalive=args.keepalive,
            ) as client:
                LOGGER.info(
                    "已连接到 %s:%s，准备订阅: %s",
                    args.host,
                    args.port,
                    summarize_topics(args.topics),
                )

                for topic in args.topics:
                    await client.subscribe(topic, qos=args.qos)
                    LOGGER.info("已订阅 %s (QoS=%s)", topic, args.qos)

                async for message in client.messages:
                    payload_text = render_payload(
                        message, args.encoding, args.decode_errors, args.raw_payload
                    )
                    print(format_message_line(message, args, payload_text))
                    title, body = prepare_notification_content(
                        getattr(message, "topic", "<unknown>"), payload_text
                    )
                    send_windows_notification(title, body, LOGGER)
        except asyncio.CancelledError:
            LOGGER.info("监听任务已取消，准备退出。")
            break
        except MqttError as exc:  # type: ignore[misc]
            LOGGER.warning("MQTT 连接异常: %s", exc)
            if reconnect <= 0:
                raise
            LOGGER.info("%.1f 秒后尝试重新连接…", reconnect)
            await asyncio.sleep(reconnect)
        except Exception:  # pragma: no cover - 兜底日志
            LOGGER.exception("监听循环发生未预期的异常")
            raise


def main() -> None:
    parser = build_arg_parser()
    args = sanitize_args(parser)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    ensure_windows_event_loop_policy(LOGGER)

    try:
        asyncio.run(listen_loop(args))
    except KeyboardInterrupt:
        LOGGER.info("收到中断信号，程序结束。")
    except MqttError as exc:  # type: ignore[misc]
        LOGGER.error("最终连接失败: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
