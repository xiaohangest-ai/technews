# Tech Daily — 部署到 GitHub Actions（傻瓜教程版）

每天北京时间早 8:00 自动抓科技新闻 + 推 Lark。下面这份教程**完全不需要终端、不需要 git、不需要装任何东西**，只用浏览器就行。

预计耗时：**10 分钟**。

---

## 你要做的事，分 5 步

```
[第 1 步] 登录 GitHub
[第 2 步] 建一个新仓库
[第 3 步] 把这 5 个文件拖到仓库里
[第 4 步] 配 3 个 Secrets（凭据）
[第 5 步] 手动跑一次验证
```

做完之后明天 8:00 它就会自动推送，你什么都不用管。

---

## 准备工作（重要！）

**Finder 里默认看不到 `.gitignore` `.env.example` `.github` 这些以 `.` 开头的文件 / 文件夹**，但它们是 **必须** 上传的。先打开它们的可见性：

1. 打开 Finder，进入 `Documents/claude coding/test/tech-daily-github/` 这个文件夹
2. 按快捷键 **`Cmd + Shift + .`**（句号键）

你应该能看到 5 个东西出现：

```
.env.example       ← 灰色（之前是隐藏的）
.github            ← 灰色文件夹（之前是隐藏的）
.gitignore         ← 灰色（之前是隐藏的）
README.md
tech_daily.py
```

> 如果还是只看到 README.md 和 tech_daily.py 两个，说明快捷键没生效，再按一次 `Cmd + Shift + .`。

---

## 第 1 步：登录 GitHub

1. 浏览器打开 https://github.com
2. 右上角点 **Sign in**，用你的账号登录

如果想不起密码，用页面上的 "Forgot password?" 重置一下。

---

## 第 2 步：建一个新仓库

1. 登录后，浏览器地址栏直接打开 https://github.com/new
2. 按下面这样填：

   | 字段 | 填什么 |
   | --- | --- |
   | **Repository name** | `tech-daily`（或你喜欢的名字，全英文/数字/连字符） |
   | **Description** | 可选，比如 `每天 8 点推送科技新闻到 Lark` |
   | **Public / Private** | 都行。**Public** 的好处：GitHub Actions 完全免费、无分钟数限制。**Private** 也免费但每月有 2000 分钟额度（一天一次绝对用不完）。我推荐 **Public**，反正密码靠 Secrets 保护，代码本身公开没事。 |

3. **下面这几个框一个都不要勾**（这是新手最容易踩的坑）：
   - ❌ Add a README file
   - ❌ Add .gitignore
   - ❌ Choose a license

   勾了的话仓库会预先有文件，跟你要上传的产生冲突。

4. 点最下面绿色的 **Create repository** 按钮。

3 秒后你会跳到一个新页面，标题大概长这样："Quick setup — if you've done this kind of thing before"。这个页面就是空仓库，下一步开始往里填东西。

---

## 第 3 步：把 5 个文件拖到仓库里

在你刚跳转到的那个空仓库页面上，找页面中部一行字：

> **uploading an existing file**

它是个蓝色链接。**点它。**

> 如果你没看到这行字，把页面拉到中间偏下；或者直接在浏览器地址栏后面加 `/upload/main` 回车（例：`https://github.com/你的用户名/tech-daily/upload/main`）。

进去之后是一个上传页，中间有一个虚线框，写着 "Drag files here to add them to your repository"。

### 操作

1. 用 Finder 打开 `Documents/claude coding/test/tech-daily-github/`
2. **全选 5 个东西**（Cmd+A 一下选完）：
   - `.env.example`
   - `.github`（这是个**文件夹**，里面有 `workflows/tech-daily.yml`）
   - `.gitignore`
   - `README.md`
   - `tech_daily.py`
3. **拖到浏览器那个虚线框里**

GitHub 会扁平化展开 `.github` 这个文件夹，自动显示成 `.github/workflows/tech-daily.yml` 的形式 —— 这是对的，不用管。

### 检查上传清单

虚线框下面应该列出 **5 个条目**：

```
✓ .env.example
✓ .github/workflows/tech-daily.yml
✓ .gitignore
✓ README.md
✓ tech_daily.py
```

如果少了 `.github/workflows/tech-daily.yml`，多半是你 Finder 里没显示隐藏文件。回到"准备工作"那一节，按 `Cmd + Shift + .`。

### 提交

页面拉到最下面，有两个输入框：

- 第 1 个（标题）：输入 `init`（或写 `初始化` 都行）
- 第 2 个（描述）：留空

下面有两个圆点选项：
- ⦿ **Commit directly to the `main` branch** ← 选这个
- ◯ Create a new branch... ← 不要选

点绿色的 **Commit changes** 按钮。

页面会跳回仓库主页，5 个文件应该都列在那里了。

---

## 第 4 步：配 3 个 Secrets（最关键！）

Secrets 是 GitHub 给你存敏感信息（密码/Token）的地方，外人看不到，但 GitHub Actions 跑的时候能读到。

### 进 Secrets 页面

在你的仓库页面：

1. 顶部一排选项卡：`<> Code` `Issues` `Pull requests` `Actions` `Projects` `Wiki` `Security` `Insights` **`Settings`** ← 点最右边的 **Settings**
2. 进去后看左边一长列菜单，往下找到 **Security** 这一段，下面有：
   - Secrets and variables ▾  ← **点它**，会展开
     - **Actions**  ← 然后点这个
3. 你会看到一个页面，中间区域有个绿色按钮 **New repository secret**

### 加第 1 个 Secret：APP_ID

1. 点 **New repository secret**
2. **Name** 框里输入：`APP_ID`（**完全大写，注意拼写，必须一字不差**）
3. **Secret** 框里粘贴：

   ```
   cli_xxxx
   ```

4. 点绿色的 **Add secret**

### 加第 2 个 Secret：APP_SECRET

1. 重新点 **New repository secret**
2. **Name**：`APP_SECRET`
3. **Secret**：

   ```
   xKEDQdNBE4e9m6xxxxxxxxxxxxxxx
   ```

4. **Add secret**

### 加第 3 个 Secret：OPEN_ID

1. 重新点 **New repository secret**
2. **Name**：`OPEN_ID`
3. **Secret**：

   ```
   ou_41ec840bc7195069xxxxxxxx
   ```

4. **Add secret**

### 检查

加完之后页面上应该列出 3 个 secret，名字分别是：

```
APP_ID         Updated now
APP_SECRET     Updated now
OPEN_ID        Updated now
```

值不会显示出来（这是设计如此，安全），只能看到名字。如果 3 个都在，✓ 完成。

> 名字大小写必须**完全一致**：`APP_ID` 不是 `app_id` 也不是 `App_Id`。错了 GitHub Actions 会找不到。

---

## 第 5 步：手动跑一次验证

不能等明天 8:00 才知道有没有配对，现在就跑一次。

1. 仓库顶部选项卡点 **Actions**
2. 第一次进 Actions 可能会让你点一个绿色的 **I understand my workflows, go ahead and enable them** —— 点掉它
3. 左侧能看到一个工作流叫 **Tech Daily**，点它
4. 中部偏右会出现一个灰色提示横条，最右边有个 **Run workflow ▾** 下拉按钮
5. 点 **Run workflow** → 弹出一个小框 → 再点里面绿色的 **Run workflow** 按钮（不用改任何东西）

刷新一下页面（或等 5 秒），会出现一条新的运行记录，状态是黄色圆点（运行中）。点进那条记录。

进去后你会看到一个流程图，再点中间的 **run** 节点。展开后能看到几个步骤：
- Set up job
- Checkout
- Set up Python
- **Run Tech Daily** ← 重点看这个
- Post Set up Python
- ...

整个过程大约 30~60 秒。

### 看结果

点开 **Run Tech Daily** 那一步的日志，**最后一行**：

| 你看到的 | 含义 | 怎么做 |
| --- | --- | --- |
| `✅ Sent. message_id=om_xxxxxxxx` | **成功！部署完成！** | 关掉浏览器去 Lark 检查有没有收到卡片消息。明天 8:00 它会自动跑，你什么都不用管。 |
| `❌ Missing required env var: APP_ID`（或别的名字） | Secret 没配好 | 回到第 4 步检查名字大小写、有没有都加上 |
| `❌ Send failed: {'code': 99991663, ...}` | App ID 或 Secret 写错了 | 回第 4 步重新粘贴，注意首尾不要带空格 |
| `❌ Send failed: {'code': 230002, ...}` | OPEN_ID 不对，或 Lark 应用没拉到目标用户的对话里 | 检查 OPEN_ID；确保你那个 Lark 应用对接收人可见 |
| `! No items selected, abort.` | RSS 源都抓失败了 | 罕见，等几小时重新跑一次 Run workflow |

---

## 完成之后

### 把 Cowork 里那个调度任务删掉

你之前在 Cowork 里设的 `tech-daily-8am` scheduled task 还在跑（虽然每天都会失败）。GitHub Actions 这边确认能成功推送之后，把 Cowork 那个删掉，避免重复或混淆。

### 以后想改东西怎么办

**改 cron 时间 / 改 RSS 源 / 改主题词**：

1. 仓库主页找到对应文件（`.github/workflows/tech-daily.yml` 或 `tech_daily.py`）
2. 点开
3. 右上角有个**铅笔图标 ✎**（Edit this file），点它
4. 直接在网页里改
5. 拉到最下面，标题填一句简单说明（比如 `调整推送时间到 8:30`），点 **Commit changes**

完全不需要终端。

**改 Secret 值**（比如 Lark 凭据更新了）：

回到 Settings → Secrets and variables → Actions，点对应 Secret 旁边的 **Update**，粘贴新值，保存。

### 关闭失败邮件通知（可选）

GitHub 默认每次 workflow 失败都会发邮件给你。烦的话：右上角头像 → Settings → Notifications → 找到 **Actions** 这一段 → 把 "Send notifications for failed workflows only" 关掉，或者改成只在网页提醒。

---

## 关于 cron 时间漂移

GitHub Actions 的 cron **不是分秒精确的**。官方文档明说：

> 在 Actions 高负载时段（特别是整点），定时任务可能延迟 5~30 分钟，极端情况下甚至跳过。

我设的是 `0 0 * * *`（北京 8:00 整点），整点是高峰，可能会迟到 5~10 分钟。如果你对到点性要求高：

- 想错开高峰：把 `cron: "0 0 * * *"` 改成 `cron: "7 0 * * *"` → 北京 8:07
- 想保证不晚：改成 `cron: "50 23 * * *"` → 北京 7:50

改的方法见上面"以后想改东西怎么办"那一节。

---

## 故障排查速查

| 症状 | 看哪里 / 怎么修 |
| --- | --- |
| 找不到 `.gitignore` / `.github` | Finder 按 `Cmd+Shift+.` 显示隐藏文件 |
| Run workflow 按钮灰色 / 不能点 | 你可能没登录 / 或者文件没传完整。先确认仓库主页能看到 `.github/workflows/tech-daily.yml` |
| Actions 页面没看到 Tech Daily | `.github/workflows/tech-daily.yml` 没传上去；回第 3 步重新拖一遍这个文件 |
| 一直 queued 不开始 | GitHub Actions 偶尔抖动，等 1-2 分钟自动开跑 |
| 跑成功了但 Lark 没收到 | 检查 Lark 应用是否被加到目标用户的对话里；OPEN_ID 是否对 |
| 中文乱码 | 不会发生，脚本全程 UTF-8。如果出现联系我 |

---

## 文件清单

```
tech-daily-github/
├── .github/workflows/tech-daily.yml   # GitHub Actions 调度配置
├── tech_daily.py                       # 主脚本
├── .env.example                        # 本地调试模板（云端不用）
├── .gitignore
└── README.md                           # 本文件
```
