# 外贸客户发现工具

简单网页工具：按产品画像自动搜索潜在客户、抓取官网邮箱、AI 打分，导出 Excel 后人工发邮件。

## 支持产品

| 产品 | 目标客户 | 市场 |
|------|----------|------|
| 卤素水分仪 | 经销商 / 批发商 | 东南亚 |
| 在线水分仪 | 经销商 + 终端工厂 | 全球 |

## 快速开始

```bash
cd foreign-trade-tool
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./start.sh
```

浏览器打开：http://127.0.0.1:8000

> 注意：如果你的终端里 `python` 指向系统 Python（macOS 常见），请用 `python3` 或 `./start.sh`，不要用 `python run.py`。
> 安装依赖时命令后面不要加 `# 注释`，否则 pip 会报错。

## 搜索方案（无需 SerpAPI）

| 方案 | 费用 | 配置 | 适合 |
|------|------|------|------|
| **DuckDuckGo（默认）** | 免费 | 无需配置 | 个人使用，每天几十次搜索 |
| **Google Custom Search** | 免费 100 次/天 | `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` | 需要 Google 结果质量 |
| **SerpAPI** | ~$50/月 | `SERPAPI_KEY` | 大量搜索、要完整 Google 结果 |

### Google 免费搜索配置（可选）

1. 打开 [Google Programmable Search](https://programmablesearchengine.google.com/) 创建一个搜索引擎（搜索整个 web）
2. 在 [Google Cloud Console](https://console.cloud.google.com/) 启用 Custom Search API，创建 API Key
3. 填入 `.env`：
   ```
   GOOGLE_API_KEY=你的key
   GOOGLE_CSE_ID=你的搜索引擎ID
   ```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` | 可选 | Google 免费搜索，100 次/天 |
| `SERPAPI_KEY` | 可选 | 付费 Google 搜索 |
| `OPENAI_API_KEY` | 可选 | AI 生成搜索词 + 线索打分 |

## 费用参考（个人使用）

- 搜索：**免费**（DuckDuckGo 默认）或 Google 免费 100 次/天
- OpenAI：按量，通常 $5–20/月

## 部署到 Vercel

### 方式一：GitHub + Vercel 控制台（推荐）

1. 把项目推到 GitHub
2. 打开 [vercel.com/new](https://vercel.com/new) → Import 你的仓库
3. Framework Preset 选 **Other**，Root Directory 留空
4. **Environment Variables**（可选）：
   - `OPENAI_API_KEY`
   - `GOOGLE_API_KEY` / `GOOGLE_CSE_ID`
5. 点 Deploy

### 方式二：Vercel CLI

```bash
npm i -g vercel
cd foreign-trade-tool
vercel login
vercel --prod
```

### Vercel 注意事项

- 搜索在服务端**同步完成**（一次请求返回结果），无需轮询
- 单次搜索自动限制为 **最多 8 条关键词、每条 5 个结果**（避免超时）
- 函数最长运行 **60 秒**（Pro 计划；免费版仅 10 秒，可能超时）
- 环境变量在 Vercel 控制台配置，网页里无法保存 Google Key
- 推荐搜索引擎选 **DuckDuckGo**

## 注意事项

- 请遵守目标网站 robots.txt 与当地数据法规
- 冷邮件需符合 CAN-SPAM 等法规
- 建议每次搜索词数量 8–15，避免 API 超额
