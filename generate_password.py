#!/usr/bin/env python3
"""
MQTT密码哈希生成工具

该工具通过 passlib 生成符合 amqtt `FileAuthPlugin` 要求的 `sha512_crypt` 哈希。
"""

import getpass
import sys

from passlib.hash import sha512_crypt


def hash_password(password: str) -> str:
    """使用 passlib 生成 sha512_crypt 哈希。"""
    return sha512_crypt.hash(password)


def main():
    """主函数"""
    print("MQTT密码哈希生成工具")
    print("=" * 30)
    
    # 获取用户名
    username = input("请输入用户名: ").strip()
    if not username:
        print("错误: 用户名不能为空")
        sys.exit(1)
    
    # 获取密码
    password = getpass.getpass("请输入密码: ")
    if not password:
        print("错误: 密码不能为空")
        sys.exit(1)
    
    # 确认密码
    confirm_password = getpass.getpass("请再次输入密码: ")
    if password != confirm_password:
        print("错误: 两次输入的密码不一致")
        sys.exit(1)
    
    # 生成 sha512_crypt 哈希
    hashed_password = hash_password(password)
    
    # 输出结果
    print("\n生成完成!")
    print("-" * 30)
    print(f"用户名: {username}")
    print(f"密码哈希: {hashed_password}")
    print("\n请将以下行添加到passwd文件中:")
    print(f"{username}:{hashed_password}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n发生错误: {e}")
        sys.exit(1)