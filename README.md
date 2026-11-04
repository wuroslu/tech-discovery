# 拾新 · 每日中文科技精选

**每天少量中文摘要，附中文或英文原文。**最新一期最多五条，常青发现另放，不再默认展示几百条原始订阅标题。

- 站点目标：<https://wuroslu.github.io/tech-discovery/>
- 中文精选 RSS：<https://wuroslu.github.io/tech-discovery/rss.xml>
- 常青发现 RSS：<https://wuroslu.github.io/tech-discovery/discoveries.xml>

部署状态以 GitHub Actions 最近运行和公开页面实际内容为准。更新代码后需检查页面与 RSS，不能只凭网址或本地构建结果判断上线状态。

## 阅读体验

- 首页只显示一期，最多五条；旧期通过日期选择，不混成信息流。
- 每条分别写“发生了什么”和“为什么值得看”，后者明确是编辑判断。
- 中文标题与摘要、中外原文链接、原文发布日期、实际核对时间各自清楚标注。
- 研究演示、开发者预览与正式产品不混淆。不将抓取时间包装成新闻发布时间。
- 常青工具和项目独立维护、独立订阅，不把老项目当成今日新品。
- 没有新稿时保留上期并标明日期，不用自动标题补位。
- 无广告或分析脚本；收藏只在当前浏览器，不跨设备同步。目标来源和托管平台仍有各自隐私政策。

## 架构

```text
公开 RSS → data/news.json（候选缓存，不直接发布）
                 ↓ 原文阅读、选择、中文编辑、核对
           data/digests.json（唯一新闻发布入口）
                 ↓ 结构/日期/上限/审核状态校验
         首页 + public/data.json + rss.xml

data/discoveries.json → 独立常青页面集合与 discoveries.xml
```

RSS中每条有中文事实摘要、编辑判断和对应原文。GUID取自稳定ID，编辑文字不产生新ID。RSS日期是本期编辑发布时间，原文日期在正文另列。

**定时抓取不是定时编辑。**当前Actions不会调用模型，不会自动把英语标题变成中文摘要。每天自动生成并发布少量中文稿需要独立的已授权编辑任务，详见 [EDITORIAL.md](EDITORIAL.md)。代码不假装拥有这项能力。

## 本地构建

Python 3.10+，运行时无第三方Python/npm依赖。

```sh
python3 -m unittest discover -s tests -v
python3 scripts/aggregate.py
python3 scripts/candidates.py --days 3 --limit 30
python3 scripts/build.py --site-url https://wuroslu.github.io/tech-discovery/
```

候选读取可跳过，直接构建已有精选。离线双击 `public/index.html` 可看内容。普通电脑可运行 `python3 -m http.server 8000 --directory public`；托管开发环境使用自己的预览服务。

## 核心文件

- `data/digests.json`：已核对的中文新闻，每期1–5条。
- `schema/digests.schema.json`：编辑接口字段定义。
- `EDITORIAL.md`：选题、事实核对、发布步骤和每日自动化要求。
- `data/discoveries.json`：独立常青清单。
- `data/news.json`、`data/source_status.json`：候选缓存和抓取健康状态，不进入精选列表。
- `config/sources.json`：8个候选来源及缓存保留设置。
- `scripts/aggregate.py`：RSS/Atom采集、去重准备、逐来源失败保留。
- `scripts/candidates.py`：把近期候选输出给编辑，永不发布。
- `scripts/build.py`：检查精选稿并生成静态页面与两份RSS。
- `site/`：HTML/CSS/JS源码；`public/`：可部署静态产物。
- `tests/`：45项确定性测试，包含“原始候选绝不补入精选”与“第六条拒绝发布”。

公开仓库内的候选缓存本身也可被查看，不要把私人信息写入这些文件。

## 更新和部署

使用公开仓库 `wuroslu/tech-discovery`，默认分支 `main`。Settings → Pages → Source 选择 **GitHub Actions**。提交页面代码或 `data/digests.json` 后，工作流验证、构建并部署。首次或排错可在 Actions 手动运行 **Refresh and deploy tech discovery**。

现有计划 `30 9 * * *` 每天北京时间 **17:30**触发候选收集与重建。**这一计划不包含中文稿件编辑**，也不保证准点执行。没有更新的 `data/digests.json` 时，精选内容不变。

工作流只用公开仓库标准 `ubuntu-latest` runner，私有仓库会跳过。构建job使用当前运行的 `contents: write` 保存候选缓存，部署job使用 `pages: write` 和 `id-token: write`；不创建长期凭证。Pages URL从GitHub API获取，保留子路径。

站点工作流只负责本站候选采集与发布，不管理邮件或其他提醒。

## 零额外成本的范围

本站不使用付费搜索、翻译或模型接口，不需自定义域名。GitHub Free公开仓库支持Pages；公开仓库标准GitHub托管runner的Actions免费，仍受平台规则和限制约束。免费部署不代表自动具备免费、无限的编辑服务。

- [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/about-github-pages)
- [Actions计费](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [计划任务延迟与停用规则](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

GitHub可能延迟或丢弃计划任务；公开仓库长期无活动可能被禁用。来源可能临时失败，失败时保留旧候选，但不会把它们标成今日的新稿。无法核对的事实不能靠规则过滤补足。

## 本次种子内容与核对

11月3日内容日期的一期，共3条；原文于11月4日实际核对，不回填编辑发布时间：

1. OpenAI硬件设计实验：不到一周完成的是设计，小批量原型制造另用了不到一个月，不是宣布消费产品销售。
2. Siri AI开发者预览：27.3系列测试版中的接入能力；相关新能力面向用户仍需数月，不等于中国大陆Apple Intelligence开放。
3. Fedora 45正式发布：GNOME 51 / Plasma 6.8、RPM签名强制检查，提示旧VPN插件退役。

每条在数据与页面中直接链接官方中文或英文原文。另保留10条常青发现。验证包含45项测试、JavaScript语法、两份RSS XML、稳定GUID、中文摘要与原文日期分离、桌面与移动视图检查。每次远端部署后应检查公开页面与两份 RSS。
