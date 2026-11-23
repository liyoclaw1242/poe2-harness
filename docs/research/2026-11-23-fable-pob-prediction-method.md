# 開季時只靠 PoB 資料預測 build 強度：方法設計（Fable 調查摘錄，2026-11-23）

## 前提
- **PoB 資料的時間差**：PoB 的資料是從遊戲檔匯出的（`src/Export`），所以新版資料通常在開服當下或之後才進 `dev` 分支。pipeline 要設計成「資料一進 dev 就自動重跑」。
- **目前的版本**：最新 tag 是 v0.23.1，`TreeData` 只到 `0_5`。

## 現況
- **人工 theorycraft**：找不到成文的方法論，只有 tier list 的評分準則（例如 Fubgun：低預算、能撐完整個 Atlas、清圖與 boss 兼顧）。
- **PoB 內建的半自動工具**：
  - Gem DPS 排序（`GemSelectControl` 搭配 `calcFunc(nil, useFullDPS, fastCalcOptions)`）
  - Node power（`data.powerStatList`）
  - 增量計算器（`calcs.getMiscCalculator`）
  - Trader 的加權查詢（`TradeQueryGenerator`）
- **社群專案**：
  - poe-optimizer（PoE1，用 greedy 和 GA 最佳化天賦樹）
  - pob-mcp（PoE2，greedy 挑天賦、support 與 unique）
  - UNICAMP 的大學報告（把天賦樹建模成 Steiner tree）
- **空白地帶**：沒有任何公開專案從資料枚舉候選 build 再排名。

## 機器可讀的資料（PoB-PoE2）
| 資料 | 內容 |
|---|---|
| `Data/Gems.lua` | 967 顆 gem，其中 567 顆是 support |
| `Data/Skills/*.lua` | `baseMultiplier`、`baseEffectiveness`、`statMap`、`skillTypes` 等欄位 |
| `TreeData/0_5/tree.lua` | 23 個 ascendancy、33 個 keystone、約 1193 個 notable |
| `Data/Uniques/*.lua` | 內含版本 variant，等於內建的 patch diff |
| `Data/ModCache.lua` | 10,023 條 mod 行，其中約 14% PoB 沒有解析，可以當作 PoB 盲區的量化指標 |
| `Modules/ConfigOptions.lua` | 約 1,035 個設定變數 |

## 設計（漏斗）
1. **Patch diff**：比對技能、support、天賦、unique 的數值變化，並列出新增但 PoB 沒解析的 mod 行。這步不需要計算，成本最低，應該先做。
2. **產生候選**：
   - 主技能約 290 個，搭配 ascendancy，用 tag 和武器相容性剪枝。
   - Support 先過濾相容性，再用 greedy 挑選。
   - 天賦樹用每種原型的模板，加上 node power 微調。
   - Keystone 和 unique 只測 patch 有改到的。
3. **標準化評估**：
   - 裝備分三檔：開荒、中期、後期。
   - 情境分清圖和 boss 兩種。
   - 熱機取 0 層、一半、滿層三個點。
   - 輸出 FullDPS、EHP、max hit、續航、清圖指標。
4. **衍生指標**：
   - Ramp ratio：0 層 DPS ÷ 滿層 DPS。
   - Budget slope：後期 DPS 相對開荒 DPS 的成長幅度。
   - Elasticity：每種 stat 加一個單位的 DPS 變化。最大彈性落在便宜詞綴上，是過強 build 的典型特徵。
5. **評分**：
   - 各指標做 percentile 正規化，再取幾何平均，避免單項爆表掩蓋短板。
   - 另外標「過強」旗標：DPS 的 z 值大於 2、buff 落在高彈性項、新技能或新 ascendancy。
   - 信心度 = 1 − 未解析比例。
6. **成本**：約 34 萬次計算，8 個 worker 跑約 2.5 小時。這是以每次 0.2 秒估的，PoE2 需要實測。
7. **驗證**：用 0.4 資料跑一次，對照 0.5 的使用率，算 Spearman 相關和 top-N recall，再用結果擬合評分權重。要注意人氣不等於強度。

## 延伸功能
- **CP 值換裝**：沿用 `TradeQueryGenerator:GenerateModWeights` 算出各 stat 的權重，把交易結果逐件丟回 PoB 實算，再除以價格。跨 slot 的預算分配屬於 knapsack 問題，抗性要當硬約束。
- **trade2 查詢**：
  - 用 `{type:"weight"}` 的加權群組，複雜度上限是 200。
  - 端點是 `api/trade2/search` 和 `fetch`。
  - rate limit 要依回應 header 動態節流。

## 本專案實際實測的結果（相對於上述估計）
- **單次計算速度**：增量計算約 5–20 ms，比估計的 0.2 秒快一個數量級。全技能掃描約 4 分鐘，「技能 × ascendancy」全量掃描約 15–20 分鐘。
- **原版 LuaJIT 相容性**：用原始碼預處理（處理 `+=` 和 `#@`）加上 zlib FFI 解決，不需要 fork PoB。
