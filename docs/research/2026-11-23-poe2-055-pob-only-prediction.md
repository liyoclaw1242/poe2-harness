# PoE2 0.5.5：強勢 build 為什麼強，以及開季時能否只靠 PoB 預測（2026-11-23 夜間研究）

## 結論先講

1. **0.5.5 頂端 build 的強度，大部分藏在「條件」裡。** 126 份公開 build 用 PoB 去水後（把所有條件與疊層設定關掉），DPS 中位數只剩面板的 **64%**。有一半的 build 超過 30% 的 DPS 來自條件，最誇張的 10% 只剩 **16%**。例如「最快的 Gemling Twister」面板寫 12.2M，去水後只有 1.08M，光是 Whirlwind 3 階就貢獻了 +240%。
2. **只用 PoB 資料，抓得到的是「乘數來源」：**
   - **Ascendancy 對傷害的加成**：同一個技能、同一組 support，讓 PoB 用貪婪法替每個 ascendancy 點 8 點。按加成中位數排序，前兩名是 **Gemling Legionnaire ×1.72、Martial Artist ×1.35**，和 0.5.5 的 ladder 占比前兩名（33.6%、10.4%）完全吻合。Gemling 有 123 個技能被放大到 1.5 倍以上，其他 ascendancy 幾乎都是 0。開季前的 tier list 只給 Gemling B 級，主因是 Advanced Thaumaturgy 的 quality 資料當時沒公開；那份資料現在已經進了 PoB（`GemlingQuality` flag 加上每顆 gem 的 `altQualityStats`）。
   - **藏在疊層設定後面的乘數**：Twister 掃出 ×4.8 的 Whirlwind 階段乘數（上限 5 階），在 195 個有傷害的技能中排第 5 名。
3. **只看技能本身的 DPS，幾乎沒有預測力。** 和 126 份樣本的主技能使用率相比，Spearman 相關係數只有 0.15 到 0.22；19 個 meta 技能裡有 4 到 5 個進前 40 名，隨機挑選的期望值約是 3.9 個。主要原因有四個：
   - Meta gem 的額外施放沒算進去。Martial Artist 的 Hollow Form 殘影，在 PoB 面板上只有 6.8k DPS。
   - Trigger loop（CoC Comet）、totem、minion、companion，在模板角色上無法比較。
   - 防禦、清圖速度、操作成本都沒有納入評分。
   - 需要先累積資源才能放的技能，PoB 會當成隨時能放。像 Hammer of the Gods 需要 Glory，已經加上「需要前置」的降權。
4. **「技能 × ascendancy」組合**（4,393 組）：真實 build 的組合有 44% 落在前 1000 名，隨機約為 23%，大約是兩倍，屬於中等程度的信號。

**對產品的意義**：開季當天能可靠交付的是「哪些 ascendancy 和機制是乘數來源」的清單，加上每個 build 的去水報告與熱機曲線。「哪個技能最強」的排名要等第二層建模補上（見下一步）才可信。

## 資料與方法
- **引擎**：PathOfBuilding-PoE2 `dev`，commit 601768b（2026-11-10），v0.23.1，tree 0_5。我們用自己的 headless runner，跑在原版 LuaJIT 上。
- **樣本**：從 poebuilds.cc 的公開清單取得 126 份標記 0.5.5 的 build。它們的 PoB paste 放在 poe.ninja/poe2/pob 或 pobb.in，下載方式和 PoB 的匯入功能相同。樣本偏向「有出影片和攻略」的 build，Mercenary 職業有 42 份。
- **Ladder 占比**：來自第三方（LFCarry，2026-11-21），**沒有向 poe.ninja 驗證**。poe.ninja 的 build API 不開放給第三方，所以這次沒有使用。
- **標準化角色**：
  - start tier：等級 70、gem 16 級、3 顆 support。
  - mid tier：等級 90、gem 20/20、5 顆 support，外加通用的增傷與暴擊 custom mod。
  - 攻擊技能裝備對應武器類型的一般 base。
- **Support 挑選**：用 PoB 的快速計算器做貪婪選擇，預設排除 lineage support。
- **熱機偵測**：讀取主技能 mod 上的 Multiplier/Condition 變數，對照 PoB 每個 config 選項的 `apply()` 會寫入哪些變數，再掃描 0、1、2、3、5、10、20 各值。有上限的曲線才採計。
- **評分**：在同一傷害族群（同一武器類型的攻擊、法術、minion）內，對 log DPS 取 z 值。

## 為什麼強：樣本裡的量化證據

| ascendancy | 樣本數 | DPS 中位數 | EHP 中位數 | 去水後剩下 |
|---|---|---|---|---|
| Gemling Legionnaire | 24 | 1.10M | 18.8k | 62% |
| Acolyte of Chayula | 5 | 994k | 51.2k | 34% |
| Pathfinder | 3 | 733k | 57.0k | 72% |
| Blood Mage | 5 | 231k | 22.8k | 48% |
| Infernalist | 7 | 178k | 15.4k | 67% |
| Oracle | 10 | 143k | 16.3k | 100% |
| Martial Artist | 9 | 113k | 34.4k | 43%（面板沒算 Hollow Form） |
| Titan | 10 | 42k | 39.5k | 82% |

最常見的條件來源（DPS 貢獻超過 1% 的 build 數，以及貢獻中位數）：

| 條件 | build 數 | 貢獻中位數 |
|---|---|---|
| Rage | 36 | +50% |
| 敵人 Shocked | 25 | +20% |
| Power Charges | 21 | +22% |
| Frenzy Charges | 16 | +13% |
| 敵人 Dazed | 15 | +16% |
| 敵人 Armour Broken | 9 | +19% |
| Withered 疊層 | 7 | +28% |
| 敵人 Frozen | 4 | +67% |

機制面的「為什麼」（Twister 的階段乘數、Hollow Form、Gemling 的 quality 第二效果、Snipe 消耗 freeze 等）整理在 `2026-11-23-fable-meta-055.md`。

完整排名表在 `data/results/analysis.md`，原始資料在 `data/results/*.json`。

## 延伸：已經做進 harness 的功能
- **CP 值換裝**：`upgrade` 讀取玩家貼回來的物品與價格，用 PoB 實算後排序，分數是加權後的 DPS/EHP 百分比，再除以價格，並列出抗性變化。
- **交易所查詢**：`trade-query` 直接驅動 PoB 內建的 `TradeQueryGenerator`。每個 slot 約 0.2 秒，輸出 stat 權重和 trade2 搜尋連結。
- **Slot headroom**：把每件裝備換成同 base 的白板，量出它的詞綴貢獻多少，貢獻越少的 slot 通常越值得先升級。
- **`.build` 匯出**：輸出遊戲內 Build Planner 的格式。

## 下一步（依價值排序）
1. **把防禦和 minion 納入 ascendancy 加成**：同一套流程，目標改成 EHP、max hit，以及 minion 的 FullDPS。現在 Titan、Varashta、Spirit Walker 都顯示 ×1.00，是因為只看傷害。
2. **Meta gem 與 trigger 的有效施放模型**：Hollow Form、CoC、totem 數量要修正 PoB 面板。可以先做成手動規則，再用樣本 build 校準。
3. **Patch diff**：對兩個 PoB commit 的 gem、support、tree、unique 做結構化差異比對，列出被 buff 而且落在高彈性 stat 上的項目，再加上「沒被改的強技能、搭上新節點且 tag 吻合」（Fable 的模式 H）。1.0 開服前就能先準備好。
4. **模板校準**：拿樣本裡同一 ascendancy 和技能的真實天賦樹當模板（開季一週後就有），取代通用模板。
5. **回測**：用 0.4 的 PoB 資料重跑，對照 0.5 開季，驗證「事前」的預測力。這次是用同一版資料做「事後」比較。
