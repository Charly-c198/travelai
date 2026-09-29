# TravelAI 项目状态汇总(记录)

> 更新:2026-09 · 位置:`D:\Program Files\JetBrains\PythonProject\travelai`
> 前端 Vue3+TS+Arco + 后端 FastAPI+LangGraph(Qwen) + ChromaDB(RAG)

## 一、如何运行
- 后端:`cd travelai/backend && ".venv/Scripts/python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
  - venv 在 `D:\Program Files\JetBrains\PythonProject\.venv`(路径含空格,命令里 python 一律加引号)
- 前端:`cd travelai/frontend && npm run dev`(5173;vite 代理 /api→8000)
- 生产:`travelai/frontend/nginx.conf`(history 回退 + /api 代理 + `proxy_buffering off` 供 SSE)

## 二、外部 key(`backend/app/.env`)
| 变量 | 用途 | 位置 |
|---|---|---|
| `QWEN_API_KEY` | 主 LLM(Qwen) | 后端 .env |
| `AMAP_API_KEY` | 高德 Web服务:天气/地理编码 | 后端 .env |
| `VITE_AMAP_JS_KEY` | 高德 JS 地图(Web端 key) | 前端 .env |
| `ROLLINGGO_API_KEY` | 道旅 MCP:真实酒店/预订 | 后端 .env |
| `UNSPLASH_API_KEY` | Unsplash 目的地配图(可商用) | 后端 .env |

- 后端 `Settings` 配了 `extra="forbid"`:新增环境变量必须先加进 `config.py`,否则启动报错。
- 数据库/向量库路径固定"以 backend 为根"绝对路径;禁止引入第二个 `travelai.db`。

## 三、核心自研能力
- **流式对话** `/chat/stream`:SSE 事件 status/token/done/error;停止生成(AbortController);多轮记忆(历史注入 state['messages'])。
- **行程对象化**:`draft_itinerary={content, days[], spots[](真实坐标), spots_used[]}`;done 带 destination/start_date/end_date/hotels。
- **对话Agent共性化改造(2026-09-28, 从"针对改"→"架构化")**:三层通用化取代硬编码 `parse_requirements` 与散落 if/else,让"任何新需求"都走通而不加特例。
  - `agent/schemas.py`:`PlanSpec`(10 字段,含 `constraints`(自由语义原样透传=新需求不改代码)、`changed`(本次改动字段));解析 prompt 由字段描述**自动生成**恒同步。
  - `models/planning_session.py` + `services/planning_state.py`:`planning_sessions` 表按 user+session 存最近 plan;modify 增量合并(`merge_plan_spec`),是"改两天/加一晚/换民宿/换城市"多轮语义的真源,不再现从历史文本重推。
  - `agent/actions.py`:`ACTIONS` 注册表 + `handle_action` dispatcher:`trip_plan/modify_trip`→`_generate`(生成与修改同一链路)、`save_trip`→`_save_trip`、`weather/hotel/chitchat` 各 handler(不耗生成额度)。新增动作=注册一个 handler+加一行 map,路由通用。
  - `streaming.py` 变薄编排层(load 历史+规划态→Schema 解析→merge→dispatch);`nodes.parse/generate` 注入 constraints;`AgentState` 加 `plan_spec`。前端 SSE 事件字段不变。
- **相似行程缓存**:`plan_cache` 表;命中秒回省 LLM;`run_travel_agent(skip_cache=True)` 强制全新。
- **自学习**:`app/agent/learn.py` 在 `knowledge_source=='llm_knowledge'` 时把行程回灌向量库(source='learned')。
- **行程生命周期**:trips/spots/hotels CRUD;我的行程列表/详情/删除/分享(`/s/{token}` 公开)/导出PDF/复制Markdown/一键存为行程/一键生成AI计划(`POST /trips/{id}/generate`)。
- **Dashboard 数据看板**(2026-09-23):`generation_metrics` 表采集每次 LLM 调用的 TTFT/token/成本(config `LLM_PRICE_*` 估算);`/api/v1/dashboard/summary` 聚合生成统计(P50/P95 延迟,总成本,按日趋势)+CPS 漏斗(访问→生成→保存→预订)+ 今日额度;前端 `/dashboard` 页额度条+4指标卡+echarts每日趋势+漏斗条形图。全量聚合非按用户隔离。
- **Maison 编辑社论式视觉**(2026-09-23):Vue 前端注入品牌风格(`src/styles/theme.css`):Fraunces display字体+Inter正文,品牌青绿 `#0b6b5c`/亮 `#6ad7bc`,温纸浅色/深石油色双主题,frosted 半透导航+明暗切换。8张商务图已压缩 WebP(48-189KB)存 `frontend/public/images/`。
- **Unsplash 动态配图**(2026-09-23):后端 `services/unsplash.py`(中文城市→英文搜索词映射,内存缓存24h)+`/api/v1/images` 代理(key 存服务端);前端 `data/remoteImages.ts` 响应式仓库(`useCityImage`)+`components/CityImage.vue`(本地兜底立即显示→后台升级 Unsplash 真图+署名,失败静默降级)。已接入:登录分屏(静态hero)、首页灵感画廊(静态,点卡发起规划)、行程卡封面(本地→远程升级)、详情横幅(本地→远程升级+摄影师署名)。实测行程卡 3 秒内无缝切换到 Unsplash 图。
- **品牌头像组件**(2026-09-23):`components/AvatarAI.vue`(指南针+地平线渐变图形,品牌色)+`AvatarUser.vue`(人形剪影)。已接入:对话消息头像、右上角用户菜单头像。
- **首页历史会话侧边栏**(`Home.vue`,2026-09):左侧 280px,每个历史行程=一个会话,复用 trip store(创建时间倒序、最新置顶);列表项=目的地+天数 / 时间+预算副标题;「新建行程」建空白会话并选中(自动滚回列表顶);点击切换会话主区 0.15s 淡入(消息列表绑 `:key` 重播动画);保存行程时已有行程走 PUT 更新(避免重复建)、新会话创建后回填侧边栏条目;侧边栏项 hover 出垃圾桶+popconfirm 删除,行程会话同步删后端行程,删当前会话后自动切相邻会话、删光则新建空白会话。
- **前端 UI 润色**:AI/用户头像重设计为圆角方形品牌徽章 SVG(`AvatarAI.vue` 纸飞机+星光 / `AvatarUser.vue` 人物剪影),并修复原固定 `id="brandGrad"` 在多个消息时 DOM 重复 id 的隐患(渐变 id 改为每实例唯一);首页加载态改用自己的 AI 头像。
- **高德**:天气(WeatherTool)、地理编码(`services/amap_service`,自动补缺坐标行程)、前端地图(TripMap.vue, city 兜底居中)。
- **RollingGo**:`services/rollinggo.py`(httpx 直连 JSON-RPC,绕开 mcp SDK 的 WouldBlock);`/api/v1/hotels`;bookingUrl 可追踪。
- **画像个性化**:`user_profiles` 表;消息缺风格时用画像补全;回写风格/目的地。
- **自反思**:`_review_plan` 自查天数/预算,`done.review_note` 展示。
- **主动追问**:`done.follow_up`,前端蓝条"查看可订酒店"。
- **商业化**:`tracking_events` 埋点(曝光/点击漏斗) + `quota_usage` 每日额度(免费3/Pro100) + 限流(TokenBucket) + `/api/v1/account/usage|upgrade`。

---

## 四、易踩坑 / 重要经验(本次长会话完整记录)

### A. 环境 / 进程 / 后端
1. **幽灵后端占 8000**:nohup 起的 uvicorn 在 Windows 是跨会话孤儿,`taskkill` 常"找不到进程"却仍 LISTENING;甚至多个 PID 并存。结果:改了代码重启后却是**旧进程在服务**→"改了没生效"。排查:`netstat -ano | findstr :8000`;应对:强杀比较不现实时,用 **8001 起新后端**调试,或重启电脑一次清干净。
2. **venv 在根目录且路径含空格**:`D:\Program Files\JetBrains\PythonProject\.venv\Scripts\python.exe`。bash 里写 `$PY` 必须 `"$PY"`(否则 `D:/Program` 被当命令)。
3. **Git Bash 的 `/tmp` ≠ Python 的 `/tmp`**:curl 写到 `/tmp/x`,Python 读不到(FileNotFound)。统一用**Windows 绝对路径**写/读临时文件。
4. **bash 内联中文 JSON 被 GBK 弄坏**:`curl --data-binary '{"destination":"大理"}'` 单引号里的中文经 Git Bash→GBK 后后端 400/422。应对:用 venv python 写 JSON 文件再 `--data-binary @文件`,或在 node 里发。
5. **后端 `.env` 的 `extra="forbid"`**:往 .env 加任何未在 config.py 声明的变量(如之前把 `AMAP_WEB_KEY` 塞进去)→ 启动 ValidationError。新键一定先加 config 字段。
6. **数据库/向量库路径漂移**:早期 DATABASE_URL 是相对 `./travelai.db`,启动目录不同→出现 `backend/travelai.db` 和 `backend/app/travelai.db` 两个库,登录忽好忽坏。已固定为绝对路径"以 backend 为根",勿再引入第二份。

### B. LangGraph / Agent
7. **向 state 注入的新键会被 LangGraph 丢弃**:`from_cache`、`skip_cache`、`knowledge_source` 若不在 `AgentState`(TypedDict)声明,节点间即被丢掉。表现为:check_cache 明明命中却仍去生成 95s、skip_cache 没生效。**新状态键必须补进 state.py 的 AgentState**。
8. **无头浏览器 Edge user-data-dir 放在 vite 监听的目录内→持续 reload**:Vite 会 watch 到 Edge 的 profile 文件不断 `page reload`,页面/测试乱跳。Edge profile 一律放**项目目录外**(如 C:\Temp)。
9. **测试脚本 `{done, value}` 解构笔误 → 读循环永不结束/卡死**:写 `const{done:dd,v}=await reader.read()` 而不是 `{d,v}`。这是反复"卡 120s"的一大元凶。
10. **Agent 管线里不要硬靠"找景点失败就报错"**:缺城市数据→检索空。已改为:库缺→LLM 通识兜底 + `knowledge_source` 标注;**已知城市但库无数据→返回空**让上层走通识,而不是把别的城市景点兜进来误导生成(那是 bug)。

### C. 前端 / Arco / 高德地图
11. **Arco 图标名必须真实存在**:`icon-environment/team/money/car` 不存在→渲染报错;`icon-circle-close` 应为 `icon-close-circle`。用前先 `ls node_modules/@arco-design/web-vue/es/icon/` 核对。
12. **Arco 抽屉(以及按钮)类名**:关闭按钮是 `arco-drawer-close-btn`(不是 `arco-drawer-close`);找不到会误判"不能关"。
13. **高德 Geocoder 需先加载插件**:`AMap.Geocoder` 不随主 JS 自动加载。脚本须带 `&plugin=AMap.Geocoder`,或用 `AMap.plugin(['AMap.Geocoder'], cb)` 懒加载。否则 `TypeError: AMap.Geocoder is not a constructor` → **渲染树被破坏(`set __vnode null`)** → 抽屉点 X 卡死、内部 loading 卡住——一个错连带一片。
14. **地图无坐标时的体验**:无坐标且有城市→城市兜底居中(`AMap.Geocoder`),而不是空白;且该兜底要在无坐标时**不显示"暂无带坐标的景点"遮罩**(显示条件要排除有城市的情况)。
15. **前端竞态:打开详情异步 GET 覆盖刚生成的结果**:`openDetail` 里 `tripApi.get` 若在"一键生成"之后返回,会把新生成的 `activeTrip` 覆盖回旧数据。用 `genRevision` 版本号守卫:生成成功 +1,只有版本没变的旧 GET 才应用。
16. **Arco `a-spin :loading` 卡住**常是上面渲染树被高德/组件错误打断的连带;先修根因(插件/报错)而非只调 UI。
17. **Arco `a-textarea` 没有 `press-enter` 事件(只有 `a-input` 有)**:`@press-enter` 绑在 textarea 上静默失效 → 按 Enter 变成换行、消息发不出去(核对 `textarea.js` 的 emits 只有 input/change/focus/blur/clear)。改为 `@keydown` 手动处理:Enter 发送、Shift+Enter 换行、中文输入法 composition(`e.isComposing || e.keyCode===229`)不触发发送。且 textarea 的 `@keydown` 走 `INPUT_EVENTS` 白名单透传到原生 `<textarea>`。

### D. 数据 / 上游 API
18. **Chroma 元数据 `tags` 不能为空 list**:`add_spots` 若 `tags=[]` → `Expected metadata list value ... non-empty`。自学习景点给了非空 `["AI整理"]`。
19. **Qwen/阿里 embedding 单批上限 10**:一次 `add_documents` 传 >10 个→ 400 `batch size`。`add_spots` 分批 ≤8 写入。
20. **RAG 目的地解析漂移**:同一句话说解析出"大理"或"云南大理"不定。缓存/检索匹配改为**双向包含**(dest in row.dest or row.dest in dest),并支持"城市名出现在用户消息里"。
21. **相似行程缓存"容差内"返回不符的行程**:一键生成命中旧 7 天缓存→走出 7 天?已修:**一键生成 `skip_cache=True` 强制全新**,且生成消息**带上行程真实起止日期**(`去大理玩3天,日期2026-11-01到2026-11-03`),解析拿到实际天数/区间,严格对应。
22. **mcp SDK `streamable_http_client` 的 WouldBlock**:`streamable_http_client(url, headers=...)` 这版根本不收 `headers`(要传 `http_client=httpx.AsyncClient(headers=...)`),且连 RollingGo 会 WouldBlock 卡死。最终改用 **httpx 直连 JSON-RPC**(先 initialize→再 tools/list→tools/call)最稳。
23. **高德免费天气只给"今天起约4天"**:近期行程显示真实天气,远期回退模拟。`_build_forecast` 对高德窗口外日期用 mock 补齐保证卡片完整。
24. **RollingGo Flight 端点 404**:`mcp/flight` 目前不存在(上游未开放),机票暂时接不了。
25. **echarts `Map 'japan'` 只在 console 报错、try 拦不住**:未注册地图时 echarts 只 `console.error` 不抛,`setOption` 后还想二次 setOption 会报"should not be called during main process"。结论:**不用未注册地图**,直接画散点/占位。

### E. 测试 / 验证
26. **node CDP 脚本的读流解构**(同 9)与"缓存命中 vs 全新 90s 生成"的波动,常让验证看似"没生效"——先确认是否命中了缓存(命中秒回、不显示新字段),再看代码。
27. **先生成再补坐标/依赖**:如"预览酒店""地图坐标"依赖后端异步(撞车/本书):确认该字段在 done 里是**确定性写进**的(构建+单测即可,不必次次烧 90s 实跑)。

### F. Schema 驱动 Agent(2026-09-28 新增)
28. **`plan_spec` 必须补进 `AgentState`(同 7)**:它由 parse_requirements 写入、dispatcher/持久化读取,若不在 state.py 声明,节点间被 LangGraph 丢弃。
29. **`merge_plan_spec` 判断"换城市重置约束"要先抓 orig_dest**:合并循环里 destination 会被新值覆盖,若用"覆盖后的 merged.destination"与 new 对比会永远相等→约束永不重置、跨城污染。必须在字段覆盖循环**之前**用基线 `base.get('destination')` 抓一份原始值再比。
30. **历史 `plan_cache` 行 `itinerary` 可能是 JSON 字符串而非 dict**(老版本),且 `days` 字段可能与正文实际天数不符(早年"规划3天却生成5天"被缓存:row.days=3 但正文 5 天)→ 仅靠 `row.days`±1 或查 `itinerary` 结构都会命中错误天数,返回 5 天。缓存天数校验应**统一从正文标题 `_derive_days(row.content)` 数实际天数**,`abs(请求天数−正文天数)>1` 即跳过(`get_cached_plan` 已加硬条件③;惰性 `from app.agent.nodes import _derive_days` 避开与 nodes 的循环依赖)。同理,带约束/修改的请求 `_generate` 里 `skip_cache=True`,避免复用缺约束的旧版。
31. **改了缓存/解析等被复用的代码,记得重启后端**:实验时 uvicorn 不带 `--reload` 起的老进程一直在服务**旧代码**,导致验证"怎么改了没生效"(netstat 看到自己之前起的进程还在 LISTENING)。改完核心逻辑先确认端口上的进程是新的。

### G. 2026-09-28 补充(实体级图片 / 地图Marker / 智能规划·已实现 / 共性化改造·状态)
- **状态勘误**:上文「一/三」的 `PlanSpec`/`schemas.py`/`models/planning_session.py`/`services/planning_state.py`/`agent/actions.py` 与 F 段 28-31 目前为**已批准·待实现**方案,代码尚未落地(现 `parse_requirements` 仍是硬编码字段、`planning_sessions` 表未建)。下述为**本次已实现并(在本地)验证**的部分。
- **实体级图片解析(图↔地不对应修复)**:新 `services/wikipedia.py`(geosearch按坐标锚定实体+page/summary主图+词元校验防垃圾坐标+许可黑名单拒fair-use,超时4s) + `GET /api/v1/images/spot`(优先级:Wikipedia[config `WIKIPEDIA_ENABLED` 默认关]→`unsplash.llm_english_query` Qwen消歧→`amap_service.poi_photo` 高德POI实拍→`scope_query` 城市锚定→城市兜底→none)。**`zh.wikipedia.org` 在大陆被墙(秒级RST)→ Wikipedia 实体解析默认不可用**,主路径是 Qwen 消歧。实测:洪崖洞→Qwen "Chongqing Hongya Cave"→Unsplash命中;回民街→Qwen输出被后置校验拒(替换成兵马俑)→重启后 Unsplash/scope 均无图→**高德POI实拍图兜底**。响应含 `query` 调试字段。前端 `buildPlaceGallery` 放宽为"name_en 或坐标" + `fetchSpotImage`;封面本地兜底改 hero 中性占位(不再闪圣托里尼)。旧 `/api/v1/images`(封面/城市级)不变。
- **地图 Marker 空白占位框**:AMap v2 默认图标+emoji label(📍/🏨)渲染成空白框 → `TripMap.vue` 的 `makeMarker()` 改**名字气泡+CSS图钉全塞进 Marker `content`(真实DOM,`textContent` 赋值防XSS)**,绕开 label 渲染,蓝`#165dff`=景点/橙`#e8653a`=酒店,`anchor:'bottom-center'` 尖角指向坐标。rollinggo 原始 `hotelInformationList` 字段已确认与前端 `RollingHotel` 一致(name/latitude/longitude/starRating/price 都有),**无需后端映射**。
- **智能规划·已实现部分**:`plan_cache.derive_days` 支持中文数字("三天"→3,"三十一"→31)+`(?<!第)` 排除"第X天"天序误判(堵住"三天"命中 7 天缓存漏洞);`parse_requirements` 提取 `days`+`intent`(trip_plan/save_trip/modify_trip/weather_query/chitchat);`services/trip_service.save_trip_from_plan`(user_id 归一化 UUID,`trips.start_date/end_date` 是 **NOT NULL** 需兜底日期,有 trip_id 走更新否则新建);`streaming` 生成后天数不符→`status{step:'regenerate'}` 前端清屏重生成一次(纠错指令);`intent==save_trip` 短路复用最近行程保存(不生成/不耗额度),`done` 返回 `saved_trip_id`;前端 Home.vue 每轮带 `context:{trip_id}`。**非流式 `POST /chat` 无 save 分支**(前端只用 `chatStream`);`trips.start_date/end_date` NOT NULL 是插入缺日期 Trip 会崩的坑。
- **待办(共性化改造,已批准)**:Phase1 `PlanSpec` schema+`constraints`/`changed` 自由语义透传+校验 → Phase2 `planning_sessions` 表持久化(修改走 plan 对象增量合并,不再现从历史文本重推) → Phase3 `agent/actions.py` `ACTIONS` 注册表 dispatcher(新增动作=注册 handler+加一行 map)。详见 plan 文件 `C:\Users\Charly\.claude\plans\iridescent-bouncing-kite.md`。

---

## 五、路线图
详见 `travelai/ROADMAP.md`(Phases 0-5 + 甘特 + 验收清单)。