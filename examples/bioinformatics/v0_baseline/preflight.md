会话环境预检，快速确认工作环境状态。

逐项检查并输出状态表格：

## 检查项

### 1. 外部驱动器
```bash
ls /Volumes/
```
检查是否有外接硬盘/移动存储

### 2. Bash 版本
```bash
/bin/bash --version | head -1
```
如果是 3.x，提醒：不支持 `declare -A`、`mapfile`、`readarray`、`${var,,}`、`${var^^}`，建议使用 zsh

### 3. 磁盘空间
```bash
df -h / | tail -1
```
可用空间 < 10GB 时警告

### 4. Tailscale
```bash
tailscale status 2>/dev/null | head -5 || echo "NOT_RUNNING"
```

### 5. 常用工具可用性
```bash
which R python3 pandoc 2>/dev/null
R --version 2>/dev/null | head -1
python3 --version 2>/dev/null
pandoc --version 2>/dev/null | head -1
```

### 6. plan.md
```bash
ls plan.md 2>/dev/null || ls 计划.md 2>/dev/null || echo "NOT_FOUND"
```

### 7. Git 状态
```bash
git status --short 2>/dev/null | head -5
```

## 输出格式

```
## 环境预检报告

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 外部驱动器 | ✅/⚠️ | [挂载的卷] |
| Bash 版本 | ✅/⚠️ | [版本号] |
| 磁盘空间 | ✅/⚠️/❌ | [可用空间] |
| Tailscale | ✅/❌ | [在线设备数] |
| R | ✅/❌ | [版本] |
| Python3 | ✅/❌ | [版本] |
| pandoc | ✅/❌ | [版本] |
| plan.md | ✅/❌ | [路径] |
| Git | ✅/⚠️ | [未提交文件数] |
```

如有 ⚠️ 或 ❌ 项，在表格下方给出具体建议。
