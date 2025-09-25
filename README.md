# SMS-repeater

conda create -n sms-repeater python=3.13
conda activate sms-repeater

pip install -r requirements.txt

## MQTT 服务器

本项目实现了一个基于 amqtt 的 MQTT 服务器，监听 1883 端口。

### 认证信息

服务器启用了用户认证，不允许匿名连接。密码文件使用 `sha512_crypt` 哈希，生成方式见下文。

> ⚠️ 客户端需使用 MQTT 3.1.1 或更新协议版本（如 MQTT 5.0）。旧版协议名称 `MQIsdp` 会被拒绝。

### 系统消息监听客户端

项目提供了基于 `aiomqtt` 的异步客户端 [`mqtt_client.py`](file://c%3A/workspace/github/SMS-repeater/mqtt_client.py)，用于订阅 `$SYS/#` 等主题并输出服务器当前状态消息。

快速使用：

```pwsh
$env:MQTT_USERNAME="user"
$env:MQTT_PASSWORD="password"
python mqtt_client.py --topic '$SYS/#'
```

> ℹ️ 在 Windows 上脚本会自动切换到 `WindowsSelectorEventLoopPolicy`，以兼容 aiomqtt 对底层 `add_reader`/`add_writer` 的调用。

常用参数：

- `--host` / `--port`：指定服务器地址（默认 `127.0.0.1:1883`）。
- `-t/--topic`：可多次指定或使用逗号分隔多个主题，默认监听 `$SYS/#`。
- `--reconnect-delay`：设置重连间隔，传入 `0` 或负数可禁用自动重连。
- `--raw-payload`：以十六进制输出负载，便于调试非文本数据。
- Windows 平台上，客户端会为每条消息触发系统通知（依赖 `windows-toasts` 包）；如未安装将提示补装。

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

注意：生成的密码哈希采用 `sha512_crypt` 算法，与 amqtt 默认的 passlib 检验兼容。