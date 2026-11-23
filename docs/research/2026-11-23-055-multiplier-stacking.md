# PoE2 0.5.5：強勢 build 怎麼在單一技能上疊乘數（2026-11-23）

> 問題重新定義：不是「哪個技能最強」，而是「給定一個技能，怎麼構築才能拿到最多加成」。
> 方法：把 126 份公開 0.5.5 build 用 PoB 逐項拆解（leave-one-out），再拿 PoB 自己組出來的 build 對照。
> 數字全部是 PoB 實算；×2.00 代表拿掉這一項，主技能 DPS 減半。

## 更正（同日稍晚，修正 harness 後重跑）

下面的「結論」是第一版，算出來時 harness 有幾個 bug。修正後重跑 125/126 份 build，改動如下（原始內容保留，供對照）：

| 原結論 | 修正後 | 原因 |
|---|---|---|
| 6. 引擎：3,301 組裡 206 組協同值 ≥1.15，分布在 23/94 份 build；Arc 的 Rakiata's Flow × Runeseeker's Call 協同 ×6 | **3,114 組裡只剩 10 組，分布在 9/92 份 build**。Arc 那組是兩者獨立相乘（5.99 × 3.00 ≈ 17.98），不是引擎 | synergy 換裝時用的快取會沿用上一件裝備，裝備的單項乘數被量成 1.00 |
| 1. 天賦樹層中位數 ×7.3 | **×11.7**，現在含 jewel（jewel 層另外列，六個案例的中位數約 ×1.9） | 移除 jewel 插槽時，jewel 原本會殘留 |
| 1. 裝備層中位數 ×8.8 | **×12.6** | 先前只看第 1 組武器，有 20 份 build 實際用第 2 組（Swap 欄） |
| 3. Eldritch Battery 最高 ×12、Megalomaniac ×6.88 等 jewel／節點的極端值 | Eldritch Battery 最高 **×1.81** | 節點乘數用 FullDPS 當基準，移除後卻用 CombinedDPS 來比，兩個口徑混在一起 |
| 2. 最大單一乘數的來源：裝備 44、條件 22、support 16 | **裝備 58、條件 14、support 12**、昇華 7、jewel 4 | 同上，加上武器組 |
| Rakiata's Flow ×2.18 | 數值不變，但**只在 boss 上成立**。它把敵人的元素抗性反轉；PoB 預設 boss 有 50% 抗性，打一般怪就沒有東西可以反轉 | 情境語意 |

不受影響的：support 層（×1.64）、昇華層（×1.24）、條件層（×1.56）的中位數，以及各技能的配方方向。

DPS 的口徑也統一了：主數字一律用**主技能**的 DPS（CombinedDPS）。FullDPS 是作者勾選的所有寶石組加總，可能包含 gem 數量 ×5、Culling、副技能，現在另外列出組成。`buildup_compare`、`ninja_compare` 是修正前跑的，數字尚未重算。

## 結論

1. **乘數分成六層，各層的中位數差很多。** 100 份能量測主技能 DPS 的 build（其餘 26 份是 minion、trigger 等，PoB 量不到主技能 DPS）：

   | 層 | 中位數 | p90 |
   |---|---|---|
   | 裝備（每個 slot 和同 base 白板相比，再連乘） | ×8.8 | ×69 |
   | 天賦樹（全部非昇華節點） | ×7.3 | ×49 |
   | 其中小節點 | ×2.2 | ×4.8 |
   | support | ×1.63 | ×4.7 |
   | 條件／疊層（去水） | ×1.55 | ×6.2 |
   | 昇華 | ×1.28 | ×8.3 |

2. **每份 build「最大的單一乘數」來自哪一層**（不含主武器）：
   - 裝備 44 份（幾乎都是 unique）
   - 條件 22 份（Rage、power charge、Whirlwind 階段）
   - support 16 份（大多是 lineage）
   - 昇華 9 份
   - keystone 和 notable 共 8 份

   換句話說，頂端 build 的關鍵通常是「一件 unique」或「一個能穩定維持的條件」，不是天賦。

3. **0.5.5 反覆出現的乘數來源**（出現次數 × 中位數）：
   - **條件**：Rage（36 份，×1.50）、敵人 Shocked（25 份，×1.20）、Power Charges（20 份，×1.23，最高 ×19）
   - **lineage support**：Rakiata's Flow（15 份，×2.18）、Garukhan's Resolve（12 份，×1.68）、Dominus' Grasp（×1.51）
   - **一般 support**：Elemental Armament II（22 份，×1.24）、Execute III（16 份，×1.30）、Concentrated Area（15 份，×1.30）、Close Combat II（13 份，×1.25）
   - **昇華**：Advanced Thaumaturgy（18 份，×1.38，最高 ×6.8）、Neurological Implants（×1.38）、Hulking Form（×1.29）、Forced Outcome（×1.29）
   - **keystone 與 notable**：Eldritch Battery（11 份，×1.58，最高 ×12）、Pain Attunement（15 份，×1.27）、Arcane Intensity（11 份，×1.42）
   - **unique**：Runeseeker's Call（7 份，×5.7）、Rathpith Globe（4 份，×9.9）、Mageblood（21 份，×1.23）、Kalandra's Touch（19 份，×1.20）

4. **同一個技能的玩家，構築方式高度一致**（技能 × 該技能 build 中出現比例 ≥40% 的來源）：
   - **Twister**：Whirlwind 階段 ×3.4、Rakiata's Flow ×2.4、Garukhan's Resolve ×1.5、Projectile Acceleration III ×1.25。support 層 ×5.7，條件層 ×11。
   - **Arc（Gemling）**：Advanced Thaumaturgy ×6.7、Runeseeker's Call ×5.2、Eldritch Battery ×2.1、Dominus' Grasp ×1.5、Arcane Intensity ×1.4。屬於「法力引擎」型。
   - **Flicker Strike**：Rakiata's Flow ×2.7（3/3）、Power Charges ×1.55、Hit and Run ×1.4、Mageblood ×1.4。
   - **Shred**：Rage ×2.1，加上 Close Combat II、Rapid Attacks II、Crescendo II。6 份 build 全都這樣配，橫跨 6 個不同昇華。
   - **Comet**：Bringer of Flame ×3.5、Pain Attunement ×2.25、Runeseeker's Call ×5.9、Megalomaniac jewel ×1.8。

   完整表格在 `data/results/decomp_analysis.md`。

5. **讓 PoB 一步一步貪婪地組 build，能抓到昇華，但抓不到 support 和天賦。** 拿同技能、同昇華的真實 build 對照：

   | 層 | precision | recall |
   |---|---|---|
   | 昇華 | 58% | 52% |
   | support | 22% | 7% |
   | 天賦 | 14% | 2% |

   貪婪法在 support 上的問題：
   - 會挑 Uhtred 系 lineage。單看最強，但會限制 support 數量。
   - 會挑 Bleed、Zerphi's，但真實 build 走的是元素路線。
   - 抓不到 meta gem（Spell Totem、Cast on Crit）。

   天賦對不上，是因為模板角色沒有真實 build 的條件和裝備，最有價值的天賦也就不同。

6. **少數 build 靠「引擎」，多數 build 是各層獨立相乘。** 把每份 build 前 10 名的來源兩兩一起拿掉，看「兩項合起來」是否大於「各自相乘」：
   - 3,301 組裡只有 206 組協同值 ≥1.15，集中在 23/94 份 build。
   - 最強的引擎是 Arc Gemling：Rakiata's Flow × Runeseeker's Call 協同 ×6（合計 ×18），Eldritch Battery × Runeseeker's Call ×3.4，Advanced Thaumaturgy × Runeseeker's Call ×2.5。
   - 引擎正是貪婪法找不到的東西：單拿 Runeseeker's Call 放進 PoB 模板，它根本不會進各 slot 的 unique 前三名。

## 對產品的意義：「單一技能最大化」該怎麼做

順序建議：
1. **先找條件**：這個技能能穩定吃到哪些條件（Rage、Shocked、power charge、技能自己的階段）？現有的 ramp 偵測加上條件掃描就能做到。
2. **lineage support 要納入**：先前的掃描預設排除，結果漏掉了最大的 support 乘數。
3. **逐 slot 掃 unique**：已實作。PoB 內建 443 件 unique，每個技能約 1 秒。
4. **昇華**：貪婪法已經夠用。
5. **用「引擎搜尋」補貪婪法的盲點**：
   - 對 keystone × unique、unique × lineage 做兩兩搜尋（beam search），找協同值大於 1 的組合。
   - 真實 build 的 `decompose --synergy` 可以當訓練或驗證資料。
6. **天賦樹最後才做**，而且要以真實 build 為模板，不從空白樹貪婪起步。

## harness 新增的功能

| 指令 | 用途 |
|---|---|
| `pob-agent decompose <build> [--synergy]` | 每顆 support、昇華節點、notable、jewel、裝備、條件的 leave-one-out 乘數，加上各層合計。`--synergy` 會列出引擎組合。 |
| `pob-agent build-up "<skill>" --ascendancy "<name>"` | 從裸 gem 開始，依序挑 support、昇華、天賦，每一步都附乘數，最後列出每個 slot 最好的 unique 和有上限的 ramp。約 2 秒。 |

研究腳本：`harness/tools/decompose_sample.py`、`analyze_decomp.py`、`compare_buildup.py`、`synergy_sample.py`。

## 限制

- **leave-one-out 乘數不能直接相乘回總值**，因為各項會互相影響。它代表的是「這件拿掉會掉多少」。
- **裝備層有兩個偏差**：
  - 換成白板會連帶失去屬性和抗性，有些協同值反映的是門檻效應（例如屬性需求不夠），不是真的機制協同。
  - 主武器換白板常常直接讓技能不能用（∞），所以排序時排除主武器。
- **Dark Consequences 這類技能**拿掉一項就歸零，協同值會變成無限大，屬於異常值。
- **樣本偏差**：126 份來自「有出影片和攻略」的 build，每個技能最多 6 份。poe.ninja 上真實的 support 和 keystone 使用率還沒拿到（Chrome 擴充套件當時沒連上）。
- **PoB 本身的盲點**：Hollow Form、trigger 和 totem 的額外施放次數，PoB 面板都沒有算進去。

## 補充：poe.ninja 實際使用率驗證（同日，瀏覽器檢視）

用瀏覽器打開 poe.ninja 的 Forbidden Rites 聯盟（124,112 個角色），讀取 11 個技能篩選後的側欄（每個技能 1.4k 到 19k 個角色）。原始資料存於 `data/ninja/forbiddenrites_2026-11-23.json`，比對結果在 `data/results/ninja_compare.md`。

- **昇華佔比和第三方數字一致**：Gemling 31.9%、Martial Artist 10.7%（LFCarry 是 33.6%、10.4%）。
- **ninja 的數字證實了先前的拆解**：
  - Twister：Projectile Acceleration III 97%、Rakiata's Flow 55%、Garukhan's Resolve 37%、The Taming 92%、Dance with Death 92%。
  - Arc：Dominus' Grasp 56%、Eldritch Battery 56%、Mind Over Matter 58%、Advanced Thaumaturgy 54%。
  - 樣本裡「拆解出的配方」和大樣本的使用率方向一致。
- **`build-up` 和 ninja 比對**（每個技能取 ninja 上最多人用的昇華）：

  | 項目 | 數字 |
  |---|---|
  | 昇華節點 precision | 51% |
  | support precision | 21% |
  | ninja 前五名 support 的 recall | 9% |
  | unique | 11 個技能只命中 2 個（Cadiro's Gambit、Mageblood） |

  unique 命中率低的主因：ninja 上最常見的 unique 是 jewel、flask、charm，例如 Heart of the Well、Rite of Passage、Lavianga's Spirits，而這些不在掃描的 slot 裡。
- **把模板改成和技能相同的傷害型態也沒用**。我照 ninja 的 traits 把 Twister 改成火焰暴擊、Snipe 和 Whirling Assault 改成閃電暴擊，support 命中仍然只有 0–1/5。
  - PoB 一直挑 Heightened Accuracy、Hit and Run、各元素的 Attunement 和 Penetration，是因為模板角色缺少命中值這類基礎屬性。
  - 真實玩家選的多半是「機制型」support：Projectile Acceleration、Salvo、Window of Opportunity、Branching Fissures、Aftershock、Spell Cascade、Efficiency、Boundless Energy。這些不是單純的 DPS 乘數，有的跟施放節奏有關，有的跟法力有關，有的跟範圍有關，所以 PoB 的 DPS 目標選不到。

**結論修正**：
- 昇華用 PoB 計算就能做得不錯。
- support 和 unique 應該以 ninja 使用率當候選池（先驗），再用 PoB 量化每一項的乘數和 CP 值，而不是讓 PoB 從零開始挑。
- 開季第一天還沒有 ninja 資料時，用上一季同技能的使用率當先驗，再拿 PoB 對版本差異重新評分。
