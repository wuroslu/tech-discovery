# 拾新 · 科技观察站

面向手机阅读的中文科技发现站。**最近动态**与**常青发现**各自独立，也分别提供 RSS。

- 计划站点：<https://wuroslu.github.io/tech-discovery/>
- 动态订阅：<https://wuroslu.github.io/tech-discovery/rss.xml>
- 常青发现：<https://wuroslu.github.io/tech-discovery/discoveries.xml>

这些是部署目标地址；本地构建成功不代表已上线。首次部署后应实际打开站点与两份 XML 检查。

## 内容与边界

- 自动读取 8 个公开来源：OpenAI、Hugging Face、Google AI、Raspberry Pi、Arduino、Hackaday、GitHub Blog、Mozilla。
- 仅保留原文标题、链接和来源时间。不抓取全文，不调用付费模型、搜索或翻译接口。**界面为中文，动态标题保持原文语言。**
- 常青发现是独立维护的中文条目，已有 10 个官方来源支持的项目。记录收录日期和核对日期，不把旧项目当作新品。
- 分类依据来源配置，URL 和长标题规则去重。**这是订阅聚合，不是逐条独立核验、完整性保证或“绝不漏报”的情报服务。**
- 首次运行只拿到源站当前 RSS 中提供的条目，不能恢复已从上游消失的旧内容。
- 默认显示近 14 天具有明确发布时间的动态。无发布时间的条目只出现在“全部缓存”，并明确标记；不会把抓取时间当成发布时间。
- 页面显示最近尝试、最近成功时间及各来源状态。失败来源保留上次成功内容；其他来源继续正常更新。
- 搜索、分类、时间范围、收藏全部在浏览器运行。收藏只存当前浏览器的 localStorage，不同步，不上传。
- 无广告、无分析脚本、无外部字体或图片请求。打开原文后，目标网站自身的隐私政策仍适用；GitHub 也会按其政策处理托管访问。

## 本地使用

只需 **Python 3.10+**，运行时无第三方 Python 或 npm 依赖。

```sh
python3 -m unittest discover -s tests -v
python3 scripts/aggregate.py
python3 scripts/build.py --site-url https://wuroslu.github.io/tech-discovery/
```

也可以不抓取，直接用已有缓存构建。离线双击 `public/index.html` 可预览已有数据，RSS 在线订阅需要真实的公开 HTTPS 地址。

普通电脑预览：

```sh
python3 -m http.server 8000 --directory public
```

然后打开 `http://localhost:8000/`。在具有自带预览服务的开发环境中，使用该环境指定的预览方式。

## GitHub Pages 部署

本项目已准备好 `.github/workflows/update.yml`，但写入文件不会自行激活任何任务。

1. 使用自己的 **公开仓库** `wuroslu/tech-discovery`，默认分支为 `main`。不要向公开仓库提交私人资料、口令或 API 密钥。
2. 将本目录内容提交到该仓库。无需自定义域名，无需付款信息，无需第三方 API 密钥。
3. 仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
4. 确认仓库允许官方 GitHub Actions，且没有阻止工作流写入缓存的规则。该工作流的构建 job 需要 `contents: write` 保存缓存；部署 job 使用 `pages: write` 与 `id-token: write`，均为当前运行的临时权限，不创建长期凭证。
5. 在 **Actions → Refresh and deploy tech discovery → Run workflow** 手动运行第一次。等待 `build` 与 `deploy` 都成功。
6. 打开上述站点和两份 RSS，确认状态时间更新。工作流使用 GitHub Pages API 返回的真实 `html_url` 设置 RSS 的绝对地址，不要求手填变量。

如果仓库名称或所有者变化，不必修改流水线中的 URL。README 中的链接也应同步更新。

### 更新计划

工作流 cron 为 `30 9 * * *`：每天 UTC **09:30**，即北京时间 **17:30**，沿用用户选择的每日频率。这只是计划触发时间，**不是准点保证**。

- 页面代码、聚合脚本、来源配置、常青清单或测试变更时也会触发部署。
- 常青清单由人工按需更新；定时任务只抓取动态，不会声称每天自动找到新的常青项目。
- 已有邮件或其他自动化不由本项目管理或变更。
- GitHub 可能延迟或丢弃高负载时段的计划任务。公开仓库长期无活动时，计划任务可能被禁用；需检查 Actions 并手动恢复。工作流保存缓存不等于对这项平台政策的豁免保证。
- 页面距上次尝试超过 30 小时会显示更新较久的提示。

### 零额外成本的适用条件

按 GitHub 官方文档，GitHub Free 的公开仓库可以使用 Pages；公开仓库使用标准 GitHub 托管 runner 的 Actions 免费。本项目只使用 `ubuntu-latest` 标准 runner、静态文件和公开 RSS，单次最长 10 分钟，部署产物仅保留 1 天。工作流在私有仓库中会跳过，避免误用不符合本方案的计费环境。

免费不等于没有限制，也不保证平台永久不变。不要改用 larger runners、付费服务、付费域名或私有部署后仍假定同样免费。项目介绍中的第三方工具可能提供可选付费服务或需要本地硬件资源；这不属于本站运行费用。

官方说明：
- [GitHub Pages 可用范围](https://docs.github.com/en/pages/getting-started-with-github-pages/about-github-pages)
- [Actions 计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [计划任务的延迟与停用限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [自定义 Pages 工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

## 维护

### 添加或关闭来源

编辑 `config/sources.json`。每个来源包含唯一 `id`、名称、HTTPS feed `url`、官网 `homepage`、类别 `ai / hardware / software`、来源类型及 `enabled`。来源类型只说明出处，不是可信度评分。RSS 接口会变化，修改后应实际抓取验证。

`lookback_days` 控制默认显示范围；`retention_days` 控制成功抓取后的保留窗口。每个成功来源最多保留 250 条；失败来源不清空旧缓存。暂停来源会停止抓取并从公开显示中移除，但不会删除磁盘中的已有缓存。

### 添加常青发现

编辑 `data/discoveries.json`，至少提供唯一 `id`、`title`、官方 `url`、`category`、简短中文 `note`、`source_name`、真实的 `added_at` 与 `verified_at`；可加 `use_case`。先打开原始资料核对，不从旧新闻推断今天仍存在的功能或价格。`added_at` 是本站收录时间，不是项目发布日期。

### 文件结构

```text
config/sources.json              来源与保留配置
scripts/aggregate.py             RSS/Atom 抓取、校验与逐源保留
scripts/build.py                 静态 JSON、JS、RSS 构建
site/                           页面源码
public/                         可部署的静态产物
  rss.xml                       动态 RSS，最多 100 条
  discoveries.xml               常青 RSS，最多 100 条
  data.json                     公开可复用数据
  data.js                       离线预览数据
  index.html / style.css / app.js
  favicon.svg / .nojekyll
data/news.json                  成功抓取缓存，不含全文
data/source_status.json         最近抓取状态
data/discoveries.json           人工维护的独立常青清单
tests/test_pipeline.py          确定性单元测试
.github/workflows/update.yml     定时更新与 Pages 部署
```

### 故障处理

- **某个来源失败**：先看页面来源区。HTTP 403、限流或 XML 异常不会清空旧数据，下一次计划任务会重试。不要绕过网站访问限制。
- **所有来源失败**：仍发布上次缓存和真实失败状态，避免页面空白或把故障误报为零新闻。
- **Pages API 404 / 权限失败**：确认 Pages 已启用且 Source 是 GitHub Actions；核对仓库权限。不要通过创建长期 token 来绕过授权。
- **缓存提交失败**：检查分支保护和 Actions 写权限。未解决前该次运行不会声称部署成功。
- **自动更新停止**：检查 Actions 是否禁用，仓库是否仍公开，计划是否还在默认分支。RSS 阅读器缓存也可能造成显示延迟。

## 本次验证

- 28 个确定性测试：RSS/Atom、日期缺失/溢出/未来值、相对链接、去重、已知日期保留、空源/失败源保留、混合成功、XML DTD/实体拒绝、CDATA 示例文字、RSS 转义、脚本转义、站点 URL 校验。
- JavaScript 语法检查。
- 真实抓取：8/8 来源成功，348 条缓存，其中浏览器默认 14 天视图显示 88 条；10 条常青发现。此为 2026-11-04 的一次结果，不承诺未来各源始终可用。
- 桌面与 390px 移动视图浏览器检查，搜索、类别、收藏与弹窗流程检查。
- GitHub 远端运行和最终公开部署状态需以实际 Actions 与 Pages 结果为准。
