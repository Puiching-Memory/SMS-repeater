import asyncio
from pathlib import Path
from amqtt.broker import Broker

# MQTT broker配置
BASE_DIR = Path(__file__).resolve().parent
PASSWORD_FILE = BASE_DIR / "passwd"

config = {
    'listeners': {
        'default': {
            'type': 'tcp',
            'bind': '0.0.0.0:1883',
        }
    },
    'plugins': {
        'amqtt.plugins.sys.broker.BrokerSysPlugin': {
            'sys_interval': 10,
        },
        'amqtt.plugins.authentication.FileAuthPlugin': {
            'password_file': str(PASSWORD_FILE),
        },
        'amqtt.plugins.authentication.AnonymousAuthPlugin': {
            'allow_anonymous': False,
        },
        'amqtt.plugins.topic_checking.TopicTabooPlugin': {},
    }
}

def build_broker(loop=None):
    """构建 Broker 实例，允许注入事件循环以便测试。"""
    return Broker(config, loop=loop)


async def main():
    loop = asyncio.get_running_loop()
    broker = build_broker(loop=loop)

    await broker.start()
    stay_running = asyncio.Future()

    try:
        await stay_running
    except asyncio.CancelledError:
        pass
    finally:
        await broker.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass