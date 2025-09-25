# SMS-repeater

conda create -n sms-repeater python=3.13
conda activate sms-repeater

pip install -r requirements.txt

## MQTT 服务器

本项目实现了一个基于 amqtt 的 MQTT 服务器，监听 1883 端口。

### 认证信息

服务器启用了用户认证，不允许匿名连接。

### 密码生成工具

项目包含一个密码生成工具 [generate_password.py](file://c%3A/workspace/github/SMS-repeater/generate_password.py)，可以用来生成新的用户密码哈希。

使用方法：
```bash
python generate_password.py
```

按照提示输入用户名和密码后，工具会生成相应的哈希密码，并提供添加到密码文件中的格式化字符串。

如需添加新用户，请使用该工具生成密码哈希，然后将输出的行添加到 passwd 文件中：

```
username:hash
```

注意：生成的密码哈希采用 SHA-256 算法，格式为 `$6$salt$hash`，其中 `$6$` 表示 SHA-256 算法。