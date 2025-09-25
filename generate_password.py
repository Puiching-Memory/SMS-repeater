#!/usr/bin/env python3
"""
MQTT密码哈希生成工具

该工具用于生成适用于amqtt密码文件的SHA-256哈希密码。
"""

import getpass
import sys
import hashlib
import secrets


def generate_salt(length=16):
    """生成随机盐值"""
    return secrets.token_hex(length)


def hash_password_sha256(password, salt=None):
    """
    使用SHA-256算法哈希密码
    
    Args:
        password (str): 明文密码
        salt (str): 盐值，默认为None时自动生成
        
    Returns:
        str: 格式化的哈希密码字符串
    """
    if salt is None:
        salt = generate_salt()
    
    # 使用hashlib生成SHA-256哈希
    salted_password = password + salt
    hashed = hashlib.sha256(salted_password.encode('utf-8')).hexdigest()
    
    # 返回格式化的字符串，模拟crypt输出格式
    return f"$6${salt}${hashed}"


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
    
    # 生成盐值和哈希
    salt = generate_salt()
    hashed_password = hash_password_sha256(password, salt)
    
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