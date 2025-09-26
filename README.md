# SMS-repeater

![项目宣传图](assets/title.jpeg)

实现短信转发功能，基于 MQTT 协议。
该仓库存放的是 MQTT 代理服务器的实现，以及客户端的实现。
发送短信，推荐使用[短信转发器](https://github.com/pppscn/SmsForwarder)

## 开发环境配置

```bash
conda create -n sms-repeater python=3.13
conda activate sms-repeater
pip install -r requirements.txt
```

## MQTT 服务器
测试：ubuntu22
基于 [amqtt](https://github.com/Yakifo/amqtt) 实现。

### 认证信息

服务器启用了用户认证，不允许匿名连接。密码文件使用 `sha512_crypt` 哈希，生成方式见下文。
> 客户端需使用 MQTT 3.1.1 或更新协议版本（如 MQTT 5.0）。旧版协议名称 `MQIsdp` 会被拒绝。

## MQTT 客户端
测试：windows11
基于 [aiomqtt](https://github.com/empicano/aiomqtt) 实现。

快速启动：

```pwsh
$env:MQTT_USERNAME="user"
$env:MQTT_PASSWORD="password"
python mqtt_client.py
```

> 在 Windows 上脚本会自动切换到 `WindowsSelectorEventLoopPolicy`，以兼容 aiomqtt 对底层 `add_reader`/`add_writer` 的调用。

客户端配置存储在mqtt_client.cfg文件中，可以配置MQTT服务器地址、端口、订阅主题等参数。

## 密码生成工具

项目包含一个密码生成工具generate_password.py，可以用来生成新的用户密码哈希。

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


## nuitka 编译

```bash
nuitka --standalone --onefile --include-module=winrt.windows.foundation --include-module=winrt.windows.foundation.collections mqtt_client.py
nuitka --windows-console-mode=disable --standalone --onefile --include-module=winrt.windows.foundation --include-module=winrt.windows.foundation.collections mqtt_client.py
```