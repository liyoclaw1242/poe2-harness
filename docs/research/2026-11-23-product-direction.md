# pob-agent 產品方向彙整（2026-11-23）

本文件整理當天討論與三輪 Fable 調查的結論，取代先前「技能排名」的產品主軸。數字與原始碼位置都已查證，標【推測】的部分尚未確認。

## 1. 目標用戶

- **對象**：至少打到過一次終局的 PoE2 老玩家。裝備到位後，可以靠自己的走位打過 Boss。
- **不處理**：
  - 劇情路線與繞路耗時
  - Boss 機制
  - 掉落與商店
  - 金幣收入
- **他們真正缺的**：
  - 不知道這季改了什麼。
  - 不知道這些改動對「我想玩的技能」有什麼影響。
  - 賽季前與賽季中的規劃決策，現有工具（poe.ninja、PoB）回答不了。

## 2. 新主軸（依優先順序）

| # | 能力 | 回答的問題 |
|---|---|---|
| 1 | 改版影響 `patch-diff` | 這季改了什麼？上季的強勢 build 在新版本重算後是升還是降？ |
| 2 | 依現有裝備的天賦路徑與洗點 | 用我現在的裝備，接下來點哪些、退哪些，每點和每金幣各換到多少？ |
| 3 | 昇華選擇檢查點 | 試煉當下選哪個昇華？在 2/4/6/8 點時各自的傷害與生存？ |
| 4 | 開荒流派與轉型規劃 | 用什麼起手？幾級轉？轉之前什麼必須成立？ |
| 5 | 單技能疊乘 `decompose` / `gap` | 在新版本上這個技能怎麼堆？和目標 build 差什麼？ |
| 6 | `upgrade` 與 trade 連結 | 通貨花在哪裡最划算？ |

各指令的定位調整：

- **降為研究用**：`scan`、`lift`、`build-up`。
  - Spearman 只有 0.15–0.22。
  - support 的 precision 21%，天賦樹 14%。
- **併入每個數字**：去水與熱機不再是獨立報告，改成附在每個數字上的情境標籤（剛進場／熱機後／面板）。

## 3. 設計原則

- **support 和 unique**：以 poe.ninja 使用率當候選池（先驗），PoB 負責量化。不要讓 PoB 從零開始挑。
- **機制型 support 列白名單**：Projectile Acceleration、Efficiency、Spell Cascade 這類在 DPS 上顯示 ×1.0，不可以建議移除。
- **轉型點看啟動件**：轉型點由離散的啟動件決定（昇華節點、寶石等級、Spirit、屬性、unique），不是兩條 DPS 曲線的交點。
- **天賦路徑以目標樹引導**：只在目標樹的範圍內尋路，用「增益 ÷ 點數」排序並往前看 2 步，做「退 k 加 k」的局部搜尋。另外標出「依你的裝備，偏離目標樹更划算」的點。
- **目標有先後順序**：先滿足硬限制（屬性、當章抗性、Spirit ≥ 0），再看 DPS 與 EHP 的加權分數。PoB 估不出價值的節點保留，並標註原因。
- **輸出給玩家**：一句結論、最多三個數字、最多三個下一步。第一行列出 Life、ES、三抗，請玩家先和遊戲內角色面板核對。

## 4. 已查證的 PoB 事實（vendor commit 601768b）

| 項目 | 內容 | 位置 |
|---|---|---|
| 任務獎勵 | 29 筆（Act 1–4、Interlude 1–3、Epilogue），全部在 config 裡且**預設全開** | `Data/QuestRewards.lua`、`Modules/ConfigOptions.lua:68-108` |
| 永久抗性 | 冰 +10（AreaLevel 2）、雷 +10（30）、火 +10（37）。Act 4 三個試煉各自「+5 屬性」或「+5% 單抗」二選一。Seven Pillars 七選一 | 同上 |
| Spirit | +30（11）、+30（36）、+40（61） | 同上 |
| 任務天賦點 | 12 個任務各給 +2，全部是 Weapon Set Passive Skill Points，共 24 點。總上限為 `99 + 24 + extra`【遊戲內是否也是如此，待實機確認】 | `Modules/Build.lua:84-102, 1031` |
| 昇華點 | 寫死上限 8 點，**沒有取得時機的資料**（`labSuggest` 是 PoE1 殘留） | `Modules/Build.lua:1031, 1044-1050` |
| 抗性懲罰 | Act 1 為 0，每章 −10，Act 6 −50，終局 −60（預設值） | `Modules/ConfigOptions.lua:113` |
| 經驗懲罰 | 安全區 = 3 + floor(等級/16)；超出時倍率 = ((L+5)/(L+5+diff^2.5))^1.5 | `Modules/Build.lua:216-240` |
| 洗點金價 | `goldRespecPrices[等級]`；昇華節點 ×5。65 級每點 1,829，90 級每點 5,081 | `Data/Misc.lua:380`、`Classes/TreeTab.lua:84-104` |
| 換樹成本 | 現有但目標沒有的節點數 × 單價 | `Classes/TreeTab.lua:84-104` |
| 試算整棵樹 | misc calculator 可傳 `override.spec` | `Modules/CalcSetup.lua:866` |
| 多棵樹與 loadout | 一個 build 可以有多個 PassiveSpec，各自有 treeVersion | `Classes/TreeTab.lua`、`Modules/Build.lua:637, 779-809` |
| 天賦樹歷史版本 | vendor 內有 0_1 到 0_5 五版樹，**天賦樹的改版差異今天就能做** | `TreeData/` |
| 怪物數值 | 等級 1–100 的怪物生命與傷害表。Boss 資料是 PoE1 殘留 | `Data/Misc.lua` |
| 版本歷史 | vendor 是 shallow clone，只有一個 commit。gem、unique、詞綴的改版差異需要先取得 PoB 歷史 | — |

## 5. 需要人工維護的資料表

- **昇華點取得時機**【推測】：Act 2 Sekhemas 拿 2 點、Act 3 Trial of Chaos 拿 2 點、終局試煉拿 4 點。由使用者確認，1.0 開季當天再核對一次。
- **檢查點階梯**：每章結尾大約幾級、當時的抗性懲罰、累計的任務獎勵。

## 6. 方法論發現：decompose 的盲點（以巫妖 Shred 為例）

- **現象**：昇華層的 leave-one-out 乘數是 ×1.00，但這個 build 的核心正是昇華。
- **原因**：
  - Eternal Life（有 ES 時生命不會變動）讓角色能常駐 Low Life。
  - Low Life 在 PoB 裡是一個 config 條件（×2.13），拿掉昇華節點不會連帶關掉這個條件。
- **結論**：「把條件變成可以穩定維持」的昇華、keystone、unique（即**促成者**）會被低估。
- **修法**：decompose 移除節點時，同時關掉它所促成的條件。需要一張「節點 → 條件」的對照表，可以從節點文字和 config 的 `ifCond` 推導。

## 7. 18 天時程（距 1.0 開季 2026-12-11）

| 天 | 工作 |
|---|---|
| 1–2 | 檢查點表與套用（依 AreaLevel 開關任務獎勵）；驗證路過屬性點在 `addNodes` 試算時算成哪一種屬性 |
| 3–7 | 依現有裝備的路徑與洗點優化器；用 poe.ninja 同流派「早期→終局」的天賦樹驗證 |
| 8–9 | 昇華選擇檢查點 |
| 10–11 | 天賦樹改版差異（用 0_4 → 0_5 演練） |
| 12–14 | 啟動件抽取 + 開荒轉型規劃器 |
| 15–16 | gem、unique、詞綴的改版差異（需要 PoB 歷史）；上季 build 在新版重算 |
| 17–18 | 用 1.0 的 PoB 資料實跑，更新 SKILL.md |

## 8. 仍待確認

- 昇華點的實際取得時機（使用者提供）。
- 任務天賦點是否全部是武器組點（實機確認）。
- PoB-PoE2 過去大改版的更新延遲。這會決定開季當天能不能用。

## 9. 三份案例找出的 harness 問題（Gemling Twister、巫妖 Shred、MA Falling Thunder；由 Fable 驗證）

**必須在主軸工作之前修好（第 1 天）**

| # | 問題 | 影響 |
|---|---|---|
| 1 | synergy 用的快速計算帶 `requirementsItems=true`（`rpc.lua:966`），換過一次裝備後，之後的試算都沿用那件裝備 | 每一組 synergy 都可能被污染。`synergy_055.json` 和報告裡的「引擎」結論（包括 Arc 的 ×6）在重跑前不可信。MA 手套的 ×1.22 協同就是假象 |
| 2 | decompose 拿 FullDPS 當基準，移除節點後卻用快速計算的 CombinedDPS 比較（`rpc.lua:897-903`） | 有 FullDPS 群組的 build，每個節點都虛增約 6–9%。MA 昇華層的 ×1.13 大多是這個造成的 |
| 3 | poe.ninja 匯出時，Absent Amulet 給的 Eternal Rage 被存成重複的寶石組，重複的那組照算 Spirit 保留 | 三份 build 的 Spirit 都顯示超用。修正後分別是 +20、+5、+1 |
| 4 | 沒有處理武器組，`EQUIP_SLOTS` 只有 Weapon 1/2 | Twister 真正在用的武器放在 Swap 欄（×7.0），完全沒被量到 |
| 5 | `scales` 寫入 `input.customMods`，但 PoB-PoE2 改用 `configSets[].customModsList`（`ConfigTab.lua:1200-1240`） | stat 彈性和 upgrade 權重都失效 |

**方法論**

- **促成者 ↔ 條件對照表**：兩端可以從 PoB 自動取得。消費端用 `conditionsUsed`／`ifCond`；候選促成者是已配置節點和裝備上 PoB 解析不了的行，每份 build 約 3–8 行。中間的對應關係由關鍵字搭配 LLM 初篩，再人工審核。decompose 對每個促成者回報兩個數字：「本身」以及「連同它保證的條件」。沒有任何促成者保證的條件，才算「靠操作維持」，去水只去掉這一部分。
  - 實測：Eternal Life ×2.13（Low Life）、The Taming ×2.08（三種元素，不是先前估的 ×1.73）、Martial Master ×1.40（Combo）。
- **資源循環**：持續 DPS ＝（消耗技一發傷害 + m × 產生技傷害）÷（消耗技耗時 + m × 產生技耗時）。不給單一數字，改給「要達到面板，每秒需要多少資源」的門檻，加上三個錨點（無資源、一半、滿）。
  - MA 的例子：要每秒回 11.5 顆 Power Charge 才能達到面板。每秒 3 顆約 2,000 萬，每秒 1 顆約 1,000 萬。
- **ramp**：count 型的 `override` 設 0 時 PoB 會略過，等於「滿層」；Power Charge 不是 Multiplier，所以沒被納入 ramp。
- **EHP 也要去水**：MA 的 EHP 從 15.2 萬降到 6.2 萬。

**修正後的第 1–2 天**

- 第 1 天：修上面 1–5 項，重跑 decomp 和 synergy。
- 第 2 天：促成者機制第一版（先收這三筆）、修 ramp 的 0 語意與 Power Charge。
- 檢查點表往後順延半天。
- 消耗型技能模型要在第 10–11 天 patch-diff 重算之前完成。

## 10. 修正進度（2026-11-23 晚）

**已完成**（6 個 smoke test 通過；拿 6 份 build 驗證：Twister、MA、巫妖、Arc、Oracle、Deadeye）：
- custom mods 改寫進 `customModsList`，scan 的模板 mods 也改走同一條路徑
- 快速計算的基準統一，不再用會沿用裝備的快取
- 新增 jewel 層
- 依武器組量裝備
- 匯入時合併「物品給的技能」的重複寶石組。遇到模糊的情況（例如 Oracle 有 4 組 CoC）不動它，只提示
- ramp 納入 Power Charge，並修正 0 層的語意；ramp 曲線會掃到 build 自己的設定值
- 主數字改用主技能 DPS，FullDPS 另外列出組成
- custom mods 逐行稽核，並納入去水
- 批次工具每 20 份重啟引擎，逐筆寫出結果，失敗太多時不覆寫舊檔

**第 2 天：促成者表第一版（已完成，8 個 smoke test 通過）**
- 程式：`harness/pob_agent/enablers.py`（表、量測）、`rpc.lua` 的 `enablers` 指令、CLI 新增 `enablers` 子指令；`diagnose`、`audit`、`decompose` 都已接上。
- 每個促成者量三個數字：本身（拿掉它，跟原本的 decompose 一樣）、只關條件（只關掉它保證的勾選）、兩者一起（真正的分量）。
- 去水基準不再扣掉「有促成者撐著」的勾選。巫妖：去水後從 17.3 萬變成 42.6 萬（Low Life 不再被當成水分；面板 144 萬）。decompose 新增 `enabler` 層，被撐著的條件會標上「由 X 撐著」。
- 自動偵測：已配置節點或裝備的詞綴中，若有無條件的 `Condition:X` 旗標，而且某個玩家端勾選也會設這個旗標，就列出來，代表那個勾選是多餘的。只比對玩家端的效果，不然「敵人被致盲」會誤配。
- 6 份案例的結果：

  | build | 促成者 | 本身 | 只關條件 | 兩者一起 |
  |---|---|---|---|---|
  | 巫妖 Shred | Eternal Life | ×1.00 | ×2.13 | ×2.13 |
  | Gemling Twister | The Taming | ×1.04 | ×2.00 | ×2.08 |
  | MA Falling Thunder | Martial Master | ×1.00 | ×1.40 | ×1.40 |
  | MA Falling Thunder | Way of the Stonefist | ×1.00 | — | ×1.29（含手套，屬於上限值） |

- 125 份樣本（`data/results/enablers_055.json`）的結果：
  - 表內命中：Stonefist 8 份、The Taming 2 份、Eternal Life 2 份、Martial Master 1 份。
  - 其中 1 份 Twister 裝了 The Taming 卻沒勾三元素，代表 PoB 低估了它，報告會提示。
  - 另一份 Abyssal Lich 勾了 Low Life，但這個條件對主技能沒有貢獻（×1.0）。
  - 自動偵測到的條件：Arcane Surge 13 份（多半是有條件觸發）、Onslaught 5 份（Dusk Fist、Thrillsteel、Torment Clutches 是無條件）。
- **第二版的候選**：貢獻 ≥20%、卻沒有促成者撐著的勾選。依出現份數：
  - Rage：36 份
  - 敵人被 Shock：14 份
  - Power Charge：12 份
  - 敵人被 Blind、Daze、Armour Break：各 4–5 份
  - Withered：4 份

  這些多半不是「件」撐住的，而是「自己的技能產生的」，屬於另一類問題：
  - Shock、Blind、Daze 可以從 PoB 的施加機率驗證
  - Rage、Power Charge 要靠資源循環模型
  - 第二版要把這類「自產條件」分開處理

**情境假設說明（已完成，10 個 smoke test 通過）**
- 程式：`harness/pob_agent/scenario.py`、`rpc.lua` 的 `scenarios` 指令、CLI 新增 `scenarios` 子指令。`diagnose` 會一併列出；`decompose --scenarios` 會加上各情境欄位；`decompose` 標頭會註明敵人假設。
- 同一份 build 依 PoB 的四種敵人情境各算一次：一般怪、地圖王、Pinnacle（PoB 預設）、Uber。每種情境都列出 DPS、EHP，以及敵人的等級、元素抗性（已算進自己的詛咒和 exposure）、護甲、受傷倍率（Uber 為 ×0.30）。
- 作者在 Enemy Stats 手填的值，例如 −60% 抗性，會先清掉，四種情境一律用 PoB 預設；手填了哪些另外列出。
- 每種情境都量測主技能組的所有 support，以及最強的節點和裝備。打一般怪和打 Pinnacle 的乘數差 ≥15% 時，標為「情境依賴」。
- 結果：

  | build | 打一般怪 vs 面板 | 情境依賴的件 |
  |---|---|---|
  | Gemling Twister | −27% | Rakiata's Flow：一般怪 ×1.02 → Pinnacle ×2.18 |
  | Arc Gemling | −33% | Rakiata's Flow：×1.00 → ×3.00 |
  | MA Falling Thunder | −35% | Rakiata's Flow：×1.00 → ×2.18；武器 ×6.25 → ×7.40 |
  | Oracle Comet | −32% | Rakiata's Flow：×1.00 → ×2.00 |
  | Deadeye Lightning Rod | −32% | Rakiata's Flow：×1.00 → ×1.81 |
  | 巫妖 Shred | +27% | 無（物理傷害，一般怪護甲較低） |

- **方法論發現**：
  - 0.5.5 的熱門 build 普遍帶 Rakiata's Flow，面板數字其實是「打 Boss 的數字」，打圖大約只剩七成。
  - 有一份 Comet 作者手填敵人抗性 −60%：反轉之後變成正抗，DPS 反而變低。打一般怪時 Rakiata's Flow 是 ×0.82，帶著反而掉傷害。

**headroom 門檻警示（已完成，12 個 smoke test 通過）**
- 程式：`harness/pob_agent/thresholds.py`、`rpc.lua` 的 `thresholds` 指令。`headroom` 和 `diagnose` 都會列出。
- 逐件檢查：把一件裝備換成白板後，哪些門檻會失守。
  - **斷崖類，標 ⚠**：MoM 100%、Spirit ≥ 0、屬性需求。
  - **漸進類，只列說明不標 ⚠**：抗性上限。
- 整份 build 的門檻餘裕：MoM 封頂前的總和、各抗性溢出多少、未保留的 Spirit、屬性比需求多多少。快失守的會列出來，已經不成立的標「NOT MET」。
- Arc Gemling：未保留生命只有 91，MoM 是 101%（只多 1%）。三件 EHP 顯示 +663% 到 +1209% 的裝備（兩只戒指和胸甲），現在都改成說明「撐住 MoM 100%」。
- Oracle：MoM 剛好 100%，未保留生命只有 1。Spirit −276、Str 不足 19，兩項都標為不成立。這類情況 PoB 不會把技能關掉，所以面板偏樂觀。
- 巫妖：Spirit −29、閃電和混沌抗性各差 4% 才到上限，兩項都標為不成立。

**待做**（照 Fable 的排序）：
1. 促成者第二版：處理自產條件（從 PoB 的 Shock、Blind 機率驗證）；從 PoB 解析不了的詞綴中初篩更多促成者
2. synergy 支援裝備×裝備和 jewel
3. 資源循環模型
4. 圖騰與觸發次數建模

**待查**：巫妖的 Spirit 仍為 −29（可能是 PoB 少算 Crystalline Phylactery）、Oracle 的 4 組 CoC 何者由護符提供、Arc 未開啟的 Lightning Infused（×3.78）。
