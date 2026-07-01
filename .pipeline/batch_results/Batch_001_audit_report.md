# Batch_001 清洗校验报告

## 基本信息
- **批次**: Batch_001
- **文件范围**: 10from-bottom-to-the-top.md ~ aiwuyujingdairichu.md
- **文件数量**: 50
- **处理时间**: 2026-06-07

---

## 阶段二：格式清洗结果

| 指标 | 数值 |
|------|------|
| 总文件数 | 50 |
| 成功处理 | 50 |
| 已修改 | 41 |
| 无需修改 | 9 |
| 来源标签修正 | 51处 |
| URL修正 | 1处 (aidehuaerzi.md 补充BV URL) |
| 数据损坏 | 0 |

## 阶段三：联网校验结果

| 判决类型 | 数量 |
|----------|:----:|
| ✅ confirmed (完全确认) | 9 |
| ⚠️ partial (部分确认) | 12 |
| 🔴 conflict (数据矛盾) | 1 |
| ❌ unverifiable (无法验证) | 28 |

### ✅ 完全确认的文件 (9个)
| 文件 | 曲名 | P主 | 核心信源 |
|------|------|-----|----------|
| 10from-bottom-to-the-top.md | 10（From bottom to the top） | 潜移默化 | 萌娘百科 |
| 2015.md | Dolores | 野良犬P | 萌娘百科, 网易云 |
| 67p-c-g-2.md | 67P·C·G | 稗子/踏云社 | 萌娘百科 |
| a-fairy-of-dreams.md | a fairy of dreams | rinu | 萌娘百科 |
| aidehuaerzi.md | 爱的华尔兹 | 沙雕少年可乐君 | bilibili (BV11MgPzfEU2) |
| aigeluotianyiailezhenglongyaver.md | 哀歌（洛天依AI＆乐正龙牙ver.） | 雨古白寂语 | bilibili (BV1ha4y1c7fE) |
| aijiangshangengaimeiren.md | 爱江山更爱美人 | 樱吹雪 | bilibili, 网易云 |
| aikepaon.md | 【艾可】PAON | taoli | 百度百科, 萌娘百科 |
| aiqingzuiming.md | 爱情罪名 | 永远幻影 | 网易云, bilibili |

### 🔴 数据冲突文件 (1个)
| 文件 | 问题 | 详情 |
|------|------|------|
| **aidemolizhuanquanquanchudian.md** | 发行日期错误 | 1999-01-01是原曲《触电》发行日期，洛天依2012年才出道，此日期不可能是洛天依翻唱版的发行日期。已复制到suspicious_music/ |

### ❌ 无法验证的文件 (28个)
主要问题：来源仅链接到 `https://www.bilibili.com/` (通用首页)，无具体BV ID/视频链接，无法进行独立验证。
其中3个文件自身承认无法在公开数据库中检索到 (airuyangguang.md, aishishenme.md, aiwuyujingdairichu.md)
2个文件标题标注"星尘infinity"但文件内写洛天依演唱，存在演唱者矛盾。

## 阶段四：交叉审计结果

### 冲突处理记录

| 文件名 | 字段 | 原始值 | 认定 | 操作 |
|--------|------|--------|------|------|
| aidemolizhuanquanquanchudian.md | 发行日期 | 1999-01-01 | 确认冲突 | 已复制到suspicious_music/，等待人工确认正确日期 |

### 异常上报
1. **aidemolizhuanquanquanchudian.md**: 发行日期1999-01-01明显为原曲日期而非洛天依翻唱版本日期。需人工核实洛天依版正确发行日期并修正。
2. **ailikadeaichou-you-no-harm-verxingcheninfinity.md**: 标题含【星尘infinity】但文件内写洛天依演唱，演唱者矛盾。
3. **ailikadeaichou-you-vocal-onlyxingcheninfinity.md**: 同上，标题含【星尘infinity】但写洛天依演唱。

## 阶段五：结果整合

### 处理统计
| 指标 | 数值 |
|------|------|
| 格式修正数 | 51项 (标签标准化) |
| 校验通过数 | 9 (完全确认) |
| 部分确认数 | 12 |
| 冲突数 | 1 |
| 无法验证数 | 28 |
| 存疑文件复制数 | 22 |

### 已复制到 suspense_music/ 的存疑文件
- aidemolizhuanquanquanchudian.md (日期冲突)
- 8-d.md, ababadege.md (无独立信源)
- acecovernibuzhidaodeshi.md (无独立信源)
- after-school.md (来源仅bilibili首页)
- ahong-qihedejiezou.md, ai.md, ai-2.md (无独立信源)
- aiaiaishenaizheshenaizheshenaizhe.md (翻唱版无独立信源)
- aiaoniyahaidechenxi.md, aiguozhekusededong.md (无独立信源)
- aikeqianqiumengsuohun.md, aiketixianmuou.md, aikewanmeibaojunsuohun.md (无独立信源)
- aiknow.md, aikoaikeliunianrugefanzi-cangqiong.md (无独立信源)
- ailikadeaichou-* (演唱者冲突)
- airuyangguang.md, aishishenme.md, aiwuyujingdairichu.md (文件自身承认不可查)
- aiweishengkai.md (来源不完整)

---
*下一批次: Batch_002 (aiyanye.md ~ bad-end-len-version.md)*
