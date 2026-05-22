# Cursor Slime

[English](README.md) · **简体中文**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)]()
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)]()

一只**像素史莱姆桌面宠物**,实时反映你 Cursor IDE / agent 的活动状态。无边框、透明背景、总在最前,不占程序坞图标。

<table align="center">
  <tr>
    <td align="center">
      <img src="docs/screenshots/state-idle.png" alt="idle — 青色史莱姆,平静" width="280"><br>
      <sub><b>空闲</b> · 青色</sub>
    </td>
    <td align="center">
      <img src="docs/screenshots/state-thinking.png" alt="thinking — 蓝色史莱姆带问号气泡" width="280"><br>
      <sub><b>思考</b> · 蓝色 · <code>?</code></sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="docs/screenshots/state-working.png" alt="working — 绿色史莱姆,眼睛瞪大,正在调用工具" width="280"><br>
      <sub><b>工作</b> · 绿色</sub>
    </td>
    <td align="center">
      <img src="docs/screenshots/state-sleeping.png" alt="sleeping — 紫色史莱姆带 zZz" width="280"><br>
      <sub><b>睡眠</b> · 紫色 · <code>zZz</code></sub>
    </td>
  </tr>
</table>

<p align="center"><em>史莱姆会按 agent 状态切换颜色和表情。状态切换由 Cursor hook 事件实时驱动。</em></p>

## 它做了什么

- 读取 Cursor agent 的 **hook 事件**(配置在 `~/.cursor/hooks.json`)
- 按"会话(conversation)"聚合统计指标:工程名、模型、工具调用频率(tools/min)、token 估算量、空闲时长
- 渲染一只 8-bit 风格的像素史莱姆,**按状态切换颜色和表情**:
  - 空闲 idle(青色) — 缓慢呼吸 + 偶尔眨眼
  - 思考 thinking(蓝色) — `?` 气泡,嘴巴平直
  - 工作 working(绿色) — 眼睛瞪大、嘴巴张开、有腮红、快速弹跳
  - 睡眠 sleeping(紫色) — `zZz` 气泡,超过 60 秒无事件后进入
- 头顶气泡显示实时指标;拖动史莱姆时气泡尾巴会自动跟着指向它头顶
- 史莱姆右下角有两个迷你按钮:`↻`(重启)和 `✕`(退出)

## 环境要求

- macOS(在 Sonoma / Sequoia 上测试过,10.15+ 理论可用)
- **Python 3.11 及以上**,带 `venv` 支持
  - 推荐 `brew install python@3.13`(自带 Tk 9.0,如果以后想回退到 tkinter 也能用)
- `jq`(hook 脚本需要)— `brew install jq`
- Cursor IDE,需要开启 hook 支持

## 安装

```bash
git clone https://github.com/SeaAndy/cursor-slime.git
cd cursor-slime
./install.sh
```

安装脚本是**幂等**的:

- 已有的 `~/.cursor/hooks.json` 会被保留,我们只**合并**自己的 hook 条目进去
- 如果 venv 已经装好了 PyQt6,会跳过 pip install 直接复用
- 重复跑 `install.sh` 是安全的升级路径

## 启动方式

| 方式 | 怎么做 |
|------|--------|
| **Spotlight** | `Cmd + Space` → 输入 `Cursor Slime` → 回车 |
| **访达 Finder** | 打开 `~/Applications/CursorSlime.app`(双击) |
| **程序坞 Dock** | 把 `~/Applications/CursorSlime.app` 拖到 Dock,以后随时点 |
| **终端** | `~/.cursor/pet/slimectl start` |
| **启动台 Launchpad** | 搜 `Cursor Slime` |

## 交互方式

| 操作 | 效果 |
|------|------|
| 拖动史莱姆身体 | 移动桌宠位置 |
| 双击 | 切换头顶气泡显示/隐藏 |
| 点 `↻` | 重启桌宠 |
| 点 `✕` | 退出 |

桌宠是**单实例**运行的 —— 已经在跑的时候再次打开 `.app` 只会闪一下通知。

## 安装后的文件位置

```text
~/.cursor/pet/
├── slime.py                   # 主程序
├── make_icon.py               # 图标生成器
├── slimectl                   # 终端控制脚本
├── venv/                      # ~250 MB;PyQt6 + pyobjc
├── CursorSlime.app/           # macOS 应用包
└── pet-stats.jsonl            # 首次 hook 事件触发时自动创建

~/.cursor/hooks/log-stats.sh   # hook 脚本
~/.cursor/hooks.json           # 合并后的 hook 配置
~/Applications/CursorSlime.app # 指向真正应用包的软链
```

## 卸载

```bash
./uninstall.sh
```

干净地移除所有安装内容,但**会保留** `hooks.json` 中你自己的其它 hook 条目。

## 自定义

编辑 `~/.cursor/pet/slime.py`,文件顶部有几个常用旋钮:

| 改什么 | 在哪 | 说明 |
|--------|------|------|
| 像素大小 | `PIXEL = int(os.environ.get("SLIME_PIXEL", "10"))` | 数字越大史莱姆越胖 |
| 状态调色板 | `STATE_PALETTES` | 每个状态的颜色组合 |
| 史莱姆形状 | `BASE`、`EYES_*`、`MOUTH_*` | 14×10 的字符网格,直接改字符 |
| 窗口大小 | `WIDGET_W`、`WIDGET_H` | 如果气泡溢出可以调大 |
| 启动位置 | `__init__` 最后几行 | 默认右下角 |

改完跑 `~/.cursor/pet/slimectl restart` 生效。

如果你改了 sprite 想让 `.app` 的图标也跟着变:

```bash
~/.cursor/pet/venv/bin/python3 ~/.cursor/pet/make_icon.py
```

## 注意事项

- **Token 数是估算值**。Cursor 的 hook payload 没有真实的 `usage` 字段,我们按 `(tool_input_chars + tool_output_chars) / 4` 估算。要准确账单请看 [cursor.com/dashboard](https://cursor.com/dashboard)。
- **没有实时缓存命中率 / 费用**。同样是 hook payload 不提供 —— Cursor 现在不通过 hook 暴露这些。
- **跨工程作用域**。用户级 hook 对所有 Cursor 工程生效,桌宠反映的是"最后触发事件的那个会话"。如果想做"每个工程一只史莱姆",把 `~/.cursor/hooks.json` 挪到对应工程的 `.cursor/hooks.json` 里即可。
- **没有签名**。首次打开 `.app` 时 Gatekeeper 可能报"未识别的开发者" —— 右键 → 打开 即可绕过。
- **只支持 macOS**。Linux/Windows 移植需要把 bash 安装脚本和 `.app` bundle 替换成对应平台的方案;PyQt6 桌宠本体大体是跨平台的。欢迎 PR。

## 工程结构

```text
cursor-slime/
├── README.md                   # 英文文档(主)
├── README.zh-CN.md             # 中文文档
├── LICENSE
├── install.sh                  # macOS 安装脚本
├── uninstall.sh                # 干净卸载
├── slime.py                    # PyQt6 桌宠主程序
├── make_icon.py                # 用 sprite 生成 .icns 图标
├── slimectl                    # start/stop/restart/status/logs
├── hooks/
│   └── log-stats.sh            # Cursor hook → ~/.cursor/pet-stats.jsonl
├── app/
│   └── Contents/               # .app bundle 骨架(图标在 install 时填入)
│       ├── Info.plist
│       ├── MacOS/CursorSlime
│       └── Resources/
└── docs/
    └── screenshots/            # README 用的截图
```

## 参与贡献

欢迎 PR 和 issue。几个不错的切入点:

- Linux 移植(把 `.app` bundle 换成 `.desktop` 文件)
- Windows 移植(bash → PowerShell;`.app` → `.lnk` + `pythonw.exe`)
- 等 Cursor 在 hook payload 里暴露真实 `usage` 字段后,替换掉估算逻辑
- 更多史莱姆 sprite / 动画
- 工程独立模式(读 `.cursor/hooks.json` 而不是 `~/.cursor/hooks.json`)

提 PR 之前请:

1. 跑一遍 `./uninstall.sh && ./install.sh`,确认你的改动还能干净安装
2. 保持 `slime.py` 自包含 —— 不要引入新的第三方依赖(除非先讨论过)
3. 如果改了安装路径或 hook 名,同步更新本 README

## 许可证

[MIT](LICENSE) © 2026 [SeaAndy](https://github.com/SeaAndy)
