# 📊 每日持仓分析工具

自动抓取**天天基金 / 东方财富**的基金净值与股票行情，每天生成一份可视化日报：计算盈亏、仓位与风险指标，结合**重仓股（成分股）表现**和**当日要闻**做 AI 研判，并推送到微信 / 钉钉 / 邮件。

适合用天天基金、东方财富投资的个人做每日复盘，数据全部来自公开行情接口，**无需登录、无需 cookie**。

---

## ✨ 功能特性

| 模块 | 说明 |
|---|---|
| 📡 数据抓取 | 基金净值（天天基金）、股票行情（东方财富，腾讯行情兜底），无需登录 |
| 💰 盈亏计算 | 累计 / 当日盈亏、收益率、仓位占比 |
| 📊 风险指标 | 年化波动率、最大回撤、夏普比率、近 1 周 / 1 月 / 半年 / 1 年收益 |
| 🏢 成分股分析 | 每只股票型基金前十大重仓股的当日涨跌，解释基金为何涨跌 |
| 📰 今日要闻 | 东方财富 7x24 快讯 |
| 🪙 加密货币 | 支持 OKX 持仓（BTC/ETH 等），CryptoCompare 数据源，自动换算人民币 |
| 🤖 AI 研判 | 接入 DeepSeek 大模型，解读行业新闻、基金动态与成分股异动；不填 Key 自动改用内置规则 |
| 📈 可视化报告 | 总市值走势、净值走势、仓位饼图、收益率柱状图，**买卖点标注**（红买绿卖） |
| 📲 消息推送 | 微信（PushPlus HTML 版 / Server酱）、钉钉机器人、邮件 |
| 🛠 持仓管理 | `update_holdings.py` 交互式维护，支持按金额 / 份额买入、追加、卖出、修改、删除 |
| ⏰ 定时运行 | Windows 任务计划程序 / Linux cron |

---

## 📁 目录结构

```
.
├── main.py               # 入口：抓数据 → 计算 → AI → 报告 → 推送
├── config.yaml           # 设置文件（AI、推送、报告目录）★ 需自己创建
├── config.yaml.example   # 配置模板
├── holdings.yaml         # 持仓清单 ★ 需自己创建
├── holdings.yaml.example # 持仓模板
├── update_holdings.py    # 交互式持仓管理（买/卖/改/删）
├── setup_task.py         # Windows 定时任务一键设置
├── requirements.txt      # Python 依赖
├── invest/               # 核心代码
│   ├── fetch.py          # 数据抓取（东财 + 腾讯兜底）
│   ├── analyze.py        # 盈亏 / 仓位 / 风险计算
│   ├── ai.py             # AI 研判（大模型 / 规则）
│   ├── report.py         # HTML 报告生成
│   └── push.py           # 微信 / 钉钉 / 邮件推送
├── assets/echarts.min.js # 图表库（内嵌报告，离线可看）
└── output/               # 生成的报告（gitignore）
```

---

## 🚀 快速开始

### 1. 安装依赖

需要 Python 3.8+。

```bash
pip install -r requirements.txt
```

### 2. 准备配置文件

```bash
cp config.yaml.example config.yaml
cp holdings.yaml.example holdings.yaml
```

### 3. 填写持仓

编辑 `holdings.yaml`，把你真实的基金 / 股票填进去：

```yaml
holdings:
  - code: "110022"        # 基金代码
    type: fund            # fund=场外基金
    name: ""              # 可留空，自动获取名称
    shares: 10000         # 持有份额
    cost_price: 2.50      # 成本净值

  - code: "600519"        # 股票代码
    type: stock           # stock=股票
    market: "sh"          # 沪市 sh / 深市 sz
    shares: 100           # 持股数
    cost_price: 1500.00   # 成本价
```

> 持仓成本在天天基金 / 东财 App 的持仓页都能查到（「持仓成本价」「持有份额」）。

### 4. 运行

```bash
python main.py
```

报告生成在 `output/` 目录，双击 `latest.html` 即可在浏览器查看。每次运行按时间戳生成独立文件（如 `report_20261006_210000.html`），`latest.html` 永远指向最新一份。

---

## ⚙️ 配置说明

### holdings.yaml —— 持仓清单

| 字段 | 说明 |
|---|---|
| `code` | 基金代码 / 股票代码 |
| `type` | `fund` = 场外基金；`stock` = 股票；`crypto` = 加密货币 |
| `name` | 名称，留空 `""` 自动联网获取 |
| `market` | 仅股票需要：`sh`（沪市）/ `sz`（深市） |
| `shares` | 基金持有份额，或股票持股数 |
| `cost_price` | 基金成本净值，或股票成本价 |
| `trades` | 买卖记录（可选），用于在图表上标注买卖点 |

`trades` 示例（每笔买卖记录一个）：

```yaml
trades:
  - date: "2025-01-10"   # 日期
    action: buy          # buy=买入 / sell=卖出
    amount: 20000        # 金额（元）
```

买卖点会以**红色「买」/ 绿色「卖」**标注在「近一年净值走势」和「组合总市值走势」两张图上。

### 加密货币（OKX 持仓）

想跟踪 OKX 上的币（BTC/ETH 等），在 `holdings.yaml` 里加 `type: crypto`：

```yaml
- code: "BTC-USDT"     # 币种，OKX 现货对
  type: crypto
  name: "比特币"        # 可留空，默认显示 BTC
  shares: 0.05         # 持有数量
  cost_price: 60000    # 成本价（USDT）
```

价格数据来自 **CryptoCompare**（国内服务器可访问），自动换算成人民币。需要免费 API Key：

1. 到 https://min-api.cryptocompare.com 注册获取免费 Key
2. 填入 `config.yaml` 的 `crypto.api_key`

> 说明：OKX 等境外交易所 API 在国内服务器无法直连，故用 CryptoCompare 做数据源；持仓数量、成本由你手动填写，成本价按 USDT 填写、自动换算人民币。

### config.yaml —— 设置

| 字段 | 说明 |
|---|---|
| `report_dir` | 报告输出目录（相对路径或绝对路径） |
| `ai.provider` | `deepseek`（大模型）/ `none`（关闭，用规则） |
| `ai.api_key` | DeepSeek API Key（留空则用内置规则，免费） |
| `crypto.api_key` | CryptoCompare API Key（加密货币价格，免费） |
| `push.pushplus_token` | PushPlus token（微信，HTML 排版，推荐） |
| `push.wechat_sendkey` | Server酱 SendKey（微信，Markdown） |
| `push.dingtalk_webhook` | 钉钉机器人 webhook |
| `push.email.*` | 邮件 SMTP 配置 |

---

## 🛠 持仓管理（update_holdings.py）

不想手动编辑 YAML 的话，用交互式工具：

```bash
python update_holdings.py
```

```
1) 新增持仓（已知份额/成本）   2) 按买入金额新增/追加
3) 修改持仓   4) 删除持仓   5) 记录卖出   0) 退出
```

- **按买入金额追加**（选项 2）：只需输入基金代码、金额、日期，自动查净值换算成份额，并**自动记录买入点**。
- **记录卖出**（选项 5）：输入卖出金额或份额，自动减少持仓并标注卖出点；全部卖出则移出持仓。

---

## 🤖 AI 研判（可选）

- **不填 Key**：报告里仍有「AI 研判」，由内置规则生成（集中度、波动率、回撤、股票占比等），免费、无需联网。
- **用大模型**：到 [DeepSeek 开放平台](https://platform.deepseek.com) 申请 Key，填入 `config.yaml` 的 `ai.api_key`。之后 AI 会结合**当日要闻、重仓股异动、基金近期表现**做每日视角的研判。

---

## 📲 推送配置

每个渠道**留空即跳过**，只生成本地报告。填哪个推哪个：

| 渠道 | 配置项 | 效果 |
|---|---|---|
| 微信 · PushPlus | `push.pushplus_token` | **HTML 排版**（KPI 卡片、表格、红涨绿跌），推荐 |
| 微信 · Server酱 | `push.wechat_sendkey` | Markdown 摘要 |
| 钉钉 | `push.dingtalk_webhook` | Markdown 消息 |
| 邮件 | `push.email.*` | 文本摘要 + 附 HTML 报告 |

> PushPlus 获取 token：https://www.pushplus.plus 微信扫码登录 → 首页「一对一推送」。
> Server酱 获取 SendKey：https://sct.ftqq.com 。
> QQ 邮箱的 `password` 是「授权码」，不是登录密码。

---

## ⏰ 定时运行

### Windows

```bash
python setup_task.py               # 每天 20:00 自动运行（默认）
python setup_task.py --time 21:00  # 自定义时间
python setup_task.py --remove      # 删除定时任务
```

- 建议设在 20:00 之后，因为基金当日净值一般在晚上 7~9 点才陆续公布。
- 运行日志在 `logs/daily.log`。任务在登录电脑时运行，当天关机不会补跑。

### Linux / 服务器（cron）

```bash
# 每天 21:00 运行，输出日志到 daily.log
crontab -e
# 加入这一行：
0 21 * * * cd /path/to/project && /usr/bin/python3 main.py >> daily.log 2>&1
```

服务器上部署后，电脑关机也照常生成报告并推送。依赖仅 `requests`、`pyyaml`：

```bash
# Debian/Ubuntu 可用系统包：
apt-get install -y python3-requests python3-yaml
# 或其他发行版：
pip install requests pyyaml
```

---

## 🌐 在线查看报告（可选）

报告是**自包含的单文件 HTML**（ECharts 已内嵌），可以直接挂到任意静态服务器。加 HTTP Basic 认证保护：

**nginx 示例**（在域名下加 `/report/` 路径 + 密码）：

```nginx
location /report/ {
    auth_basic "Private Report";
    auth_basic_user_file /etc/nginx/conf.d/.htpasswd_report;
    root /var/www;   # 把 report_dir 指向 /var/www/report 即可
    index latest.html;
}
```

生成密码文件：

```bash
apt-get install -y apache2-utils
htpasswd -bc /etc/nginx/conf.d/.htpasswd_report 用户名 密码
```

---

## 📡 数据源说明

| 数据 | 来源 |
|---|---|
| 基金名称、历史净值、重仓股 | 天天基金 `fund.eastmoney.com` |
| 股票实时行情、历史 K 线 | 东方财富 `push2.eastmoney.com` |
| 股票行情兜底 | 腾讯行情 `qt.gtimg.cn` |
| 今日要闻 | 东方财富 7x24 快讯 |
| 加密货币价格、历史 | CryptoCompare |

均为公开接口，无需登录。净值 / 行情与 App 中看到的一致。

---

## ⚠️ 免责声明

本工具仅供个人学习与持仓复盘使用，风险指标基于历史数据计算，AI 研判由大模型生成，均**不构成任何投资建议**。市场有风险，投资需谨慎。

---

## 📄 License

MIT
