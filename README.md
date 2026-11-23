# pob-agent

給 PoE2 玩家和 AI agent 用的 Path of Building harness（POV 階段）。

它在本機以 headless 方式執行 **PathOfBuilding-PoE2**，所有數字都來自 PoB 的計算引擎，不靠 LLM 記憶。在引擎之上提供以下功能：

- **build 診斷（含去水）**：把 config 條件逐項拆開，算出每項貢獻多少 DPS/EHP，並比較「去水後」「熱機起手」「清圖」「Uber」四種情境。
- **熱機曲線**：找出主技能會讀取的層數、階段、條件設定，畫出 DPS 隨層數變化的曲線，並標出上限在哪。
- **stat 彈性**：每種 stat 加一個標準單位，看各值多少 DPS/EHP，藉此判斷 build 吃哪種 stat。
- **slot headroom**：算出每件裝備的詞綴貢獻多少，貢獻越少的 slot 通常是最便宜的升級點。
- **交易所查詢**：用 PoB 內建的 `TradeQueryGenerator` 為每個 slot 產生加權 trade2 搜尋連結。工具不會幫你買，也不會密人。
- **CP 值換裝**：把玩家貼回來的物品逐件丟進 PoB 實算，再除以價格排序。
- **`.build` 匯出**：輸出遊戲內 Build Planner 可讀的官方格式。
- **只靠 PoB 資料的強度掃描**：在標準化角色上掃描所有技能（support 由 PoB 貪婪挑選，並量測藏在層數設定後面的乘數），再加上「技能 × ascendancy」的加成。開季時還沒有 ladder 資料，這是預測強勢 build 的核心。

## 安裝

```bash
scripts/setup.sh        # LuaJIT + lua-utf8 + PoB-PoE2 checkout, then a smoke test
```

PoB 用的是自訂方言的 LuaJIT（支援 `x += 1` 這類寫法），原版 LuaJIT 跑不起來。`harness/lua/pob_headless.lua` 會在載入時預處理原始碼，並用 FFI 綁定系統的 zlib 來處理分享碼，因此不需要修改 PoB。

## 使用

```bash
export PYTHONPATH=harness
python3 -m pob_agent.cli diagnose https://pobb.in/XXXX          # 一次完成診斷
python3 -m pob_agent.cli trade-query build.code --league "Standard" --slot Gloves
python3 -m pob_agent.cli upgrade build.code --candidates examples/ring_candidates.txt
python3 -m pob_agent.cli export-build build.code --out my.build
python3 -m pob_agent.cli scan --tier start --top 40               # PoB-only 技能排名
python3 -m pob_agent.cli lift Twister Spark                        # 技能 × ascendancy
```

`<build>` 可以是 `.code` 或 `.xml` 檔、分享碼、`pobb.in` 連結或 `poe.ninja/poe2/pob` 連結。下載方式和 PoB 內建的匯入功能相同。

給 agent 用的說明在 [`harness/SKILL.md`](harness/SKILL.md)。研究報告在 [`docs/research/`](docs/research/)。

## 架構

```
harness/lua/pob_headless.lua   stock-LuaJIT bridge (dialect preprocessing, zlib FFI)
harness/lua/rpc.lua            JSON-lines daemon: load/stats/variants/try_items/ramp/
                               trade_query/skill_scan/ascendancy_lift/export_build
harness/pob_agent/             Python: engine client, analysis, scan, trade, CLI
harness/tools/                 research scripts (build harvesting, overnight scan)
```

## 資料使用原則

- poe.ninja：只使用官方文件公開的 economy API，以及使用者分享的 PoB paste 連結（與 PoB 匯入相同）。不呼叫 builds/ladder 的內部 API。
- trade2：只產生搜尋連結；評估的是玩家貼回來的物品文字，不會自動抓取掛單。
- 本工具為非官方粉絲工具，與 Grinding Gear Games 無關。

## 現況（2026-11-23）

產品方向已從「哪個技能最強」改成服務打過終局的老玩家：改版影響（patch-diff）、依現有裝備的天賦路徑與洗點、昇華選擇檢查點、開荒流派與轉型規劃、單技能疊乘。細節與 1.0（2026-12-11）前的時程見 `docs/research/2026-11-23-product-direction.md`；研究結論與更正見 `docs/research/2026-11-23-055-multiplier-stacking.md`。

資料來源與原則：所有數字來自 PoB-PoE2 的計算；不呼叫 poe.ninja 的內部 API；交易所只產生搜尋連結，不會自動搜尋、購買或密人。`vendor/`（PoB 原始碼）與 `data/builds/`（下載的公開 build）不在版本庫內，由 `scripts/setup.sh` 與研究腳本取得。
