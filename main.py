import asyncio
import os
from amqtt.broker import Broker

# MQTT broker配置
config = {
    'listeners': {
        'default': {
            'type': 'tcp',
            'bind': '0.0.0.0:1883',
        }
    },
    'sys_interval': 10,
    'auth': {
        'allow-anonymous': True,
    },
    'topic-check': {
        'enabled': True,
        'plugins': ['topic_taboo'],
    }
}

# 创建Broker实例
broker = Broker(config)

async def broker_coro():
    await broker.start()

async def main():
    # 启动MQTT broker
    await broker_coro()
    
    # 保持broker运行
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())