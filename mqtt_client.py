#!/usr/bin/env python3
"""SMS验证码监听客户端。

该脚本使用 `aiomqtt` 提供的异步客户端能力，监听短信主题以获取验证码消息，
并提取验证码通过Windows通知显示。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import configparser
import re
import winreg
from windows_toasts import InteractableWindowsToaster, Toast, ToastActivatedEventArgs, ToastButton
from aiomqtt import Client, Message, MqttError
import win32clipboard
import os

LOGGER = logging.getLogger("sms_repeater.client")
def ensure_windows_event_loop_policy(logger: logging.Logger) -> None:
    """在 Windows 上切换到支持 add_reader/add_writer 的事件循环策略。"""
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

def register_hkey(appId: str, appName: str, iconPath):
    """内联的注册函数，用于注册应用程序ID到Windows注册表"""
    winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
    keyPath = f"SOFTWARE\\Classes\\AppUserModelId\\{appId}"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, keyPath) as masterKey:
        winreg.SetValueEx(masterKey, "DisplayName", 0, winreg.REG_SZ, appName)
        if iconPath is not None:
            winreg.SetValueEx(masterKey, "IconUri", 0, winreg.REG_SZ, str(iconPath.resolve()))


def activated_callback(activatedEventArgs: ToastActivatedEventArgs):
    if activatedEventArgs.arguments == "response=copy":
        # 复制到剪贴板
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(Gtitle)
        win32clipboard.CloseClipboard()

def send_windows_notification(title: str, body: str) -> None:
    """发送Windows通知"""
    global Gtitle
    Gtitle = title

    interactableToaster = InteractableWindowsToaster("SMS-Repeater","SMS-Repeater")
    toast = Toast([title, body])
    toast.AddAction(ToastButton('复制到剪贴板', 'response=copy'))
    toast.on_activated = activated_callback
    interactableToaster.show_toast(toast)


def render_payload(message: Message) -> str:
    """渲染消息负载"""
    payload = getattr(message, "payload", b"")
    if not isinstance(payload, (bytes, bytearray)):
        return str(payload)

    payload_bytes = bytes(payload)
    try:
        return payload_bytes.decode('utf-8', errors='replace')
    except UnicodeDecodeError:
        LOGGER.warning("无法解码主题 %s 的负载，退回十六进制显示。",
                      getattr(message, "topic", "<unknown>"))
        return payload_bytes.hex()

def extract_verification_code(message_lines):
    """从短信消息中提取验证码
    
    Args:
        message_lines: 短信消息的行列表
        
    Returns:
        str: 提取到的验证码，如果未找到则返回None
    """
    # 遍历每一行寻找包含验证码的部分
    for line in message_lines:
        # 使用正则表达式匹配"验证码为：数字"的模式
        match = re.search(r'验证码[为是]：(\d+)', line)
        if match:
            return match.group(1)
    
    return None

async def listen_loop(config) -> None:
    """主监听循环，负责自动重连与消息输出。"""
    # 从配置中获取参数
    mqtt_config = config['MQTT']
    
    host = mqtt_config.get('host', '127.0.0.1')
    port = mqtt_config.getint('port', 1883)
    username = os.environ.get('MQTT_USERNAME')
    password = os.environ.get('MQTT_PASSWORD')
    client_id = mqtt_config.get('client_id', None)
    keepalive = mqtt_config.getint('keepalive', 60)
    qos = mqtt_config.getint('qos', 1)
    topic = config['Message'].get('topics')
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    LOGGER.debug(
        "尝试连接 MQTT 服务器 %s:%s (client_id=%s)",
        host,
        port,
        client_id,
    )
    async with Client(
        host,
        port=port,
        username=username,
        password=password,
        identifier=client_id,
        keepalive=keepalive,
    ) as client:
        LOGGER.info(
            "已连接到 %s:%s，准备订阅: %s",
            host,
            port,
            topic,
        )

        await client.subscribe(topic, qos=qos)
        LOGGER.info("已订阅 %s (QoS=%s)", topic, qos)

        async for message in client.messages:
            message = json.loads(message.payload.decode('utf-8', errors='replace'))
            message = message["msg"].split("\n")
            print(message)
            verification_code = extract_verification_code(message)
            message = f"电话号码: {message[0]}\n内容: {message[1]}\nSIM卡槽: {message[2]} 消息ID: {message[3]} 时间: {message[4]}"

            if verification_code:
                send_windows_notification(verification_code, message)
            else:
                send_windows_notification("普通短信", message)
                
def main() -> None:
    # 解析命令行参数，仅用于指定配置文件路径
    parser = argparse.ArgumentParser(description="SMS验证码监听客户端")
    parser.add_argument(
        "--config",
        default="mqtt_client.cfg",
        help="配置文件路径（默认: mqtt_client.cfg）"
    )
    args = parser.parse_args()
    
    config = configparser.ConfigParser()
    config.read(args.config)

    register_hkey("SMS-Repeater", "SMS Repeater", None)
    ensure_windows_event_loop_policy(LOGGER)

    asyncio.run(listen_loop(config))


if __name__ == "__main__":
    main()