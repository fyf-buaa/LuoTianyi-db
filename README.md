# 洛天依知识库 / Luo Tianyi Knowledge Base

> 华风夏韵，洛水天依

本项目是一个结构化知识库（RAG 数据集），围绕全球首位中文 VOCALOID 虚拟歌手 **洛天依 (Luo Tianyi)** 及其所属的 Vsinger 生态，构建系统化的知识体系。内容涵盖角色设定、音乐作品、专辑、创作者（P主）、演出活动、商业合作、衍生文化等多个维度。

## 目录结构

```
├── core/                    # 核心实体——洛天依基础档案
├── members/                 # 相关虚拟歌手成员档案
│   ├── yan-he.md            # 言和
│   ├── xing-chen.md         # 星尘
│   ├── xin-hua.md           # 心华
│   ├── le-zheng-ling.md     # 乐正绫
│   ├── le-zheng-long-ya.md  # 乐正龙牙
│   └── ...                  # 其他成员
├── timeline/                # 时间线——重大事件年表
├── events/                  # 活动事件详录
│   ├── first-birthday-2016.md
│   ├── 10th-anniversary-exhibition.md
│   ├── bocom-credit-card.md
│   └── ...
├── performances/            # 演出/演唱会记录
│   ├── bml-2019.md
│   ├── cctv-spring-festival-2021.md
│   └── ...
├── music/                   # 音乐作品（~4764 首）
├── music_non_luotianyi/     # 非洛天依演唱的 VOCALOID 歌曲
├── albums/                  # 专辑/EP（~297 张）
├── creators/                # 创作者/P主档案（~344 位）
├── relationships/           # 角色关系网
├── lore/                    # 世界观设定
│   ├── luo-tian-yi-bio.md
│   ├── vanaheim.md
│   ├── resonance-ability.md
│   └── ...
├── fandom/                  # 粉丝文化
├── fanworks/                # 同人作品记录
├── media/                   # 社交媒体与平台账号
├── merchandise/             # 官方周边商品
├── albums/                  # 专辑目录
├── creators/                # 创作者目录
│
├── creator-bio-batch.json      # P主简介批量数据
├── creator-id-migration.json   # P主 ID 迁移映射
├── creator-name-map.json       # P主名称映射
├── creator-slug-map.json       # P主别名映射
├── member-name-map.json        # 成员名称映射
├── music-id-migration.json     # 歌曲 ID 迁移映射
├── LICENSE                     # MIT License
└── README.md                   # 本文件
```

## 数据规模

| 类别 | 数量 |
|------|------|
| 音乐作品 | ~4,764 首 |
| 专辑/EP | ~297 张 |
| P主/创作者 | ~344 位 |
| 相关成员 | 15 位 |
| 时间线事件 | 40+ 件 |
| 演出活动 | 30+ 场 |
| 商品/周边 | 22+ 件 |
| 社会媒体账号 | 19 个 |

## 数据格式

每条记录为独立的 Markdown 文件，遵循统一结构：

```markdown
# type:slug
## 标题 (Title)

### 基本信息
| 字段 | 值 |
|------|----|
| key  | value |

### 描述

正文内容...

### 来源

- [source_type](url)
```

其中 `type` 标识记录类别（如 `core`、`music`、`creator`、`event`、`performance` 等），`slug` 为唯一标识符。

## 数据来源与准确性声明

> ⚠️ **重要提示**

本项目的信息是**通过 AI 模型结合搜索引擎进行交叉验证**收集整理的。具体流程包括：

1. **AI 搜索聚合**：使用大语言模型通过搜索引擎（MiniMax Search、Bing 等）检索公开信息
2. **多源交叉验证**：对关键事实进行多来源比对（Bilibili、萌娘百科、维基百科、新闻稿件等）
3. **结构化提取**：将非结构化文本转化为统一的 Markdown 记录格式

### 可能的误差

由于以下原因，数据**可能包含错误或不准确之处**，请审慎对待：

- **AI 幻觉**：大语言模型在信息提取和归纳过程中可能产生不真实的内容
- **来源偏差**：网络公开信息本身可能存在矛盾、过时或不完整
- **交叉验证局限**：并非所有条目都经过了充分的交叉验证
- **时效性**：部分信息可能已过时，尤其是声库版本、运营信息等动态内容
- **翻译/转写误差**：中英文混排、译名差异可能导致不一致

### 建议的使用方式

- 作为**知识检索的起点**而非最终权威来源
- 对关键事实进行**独立核实**
- 发现错误欢迎提交 Issue 或 PR 修正
- 用于 RAG 应用时，建议结合检索结果置信度进行筛选

## 贡献

欢迎通过 Issue 报告错误或通过 Pull Request 提交修正。所有贡献前请先阅读现有数据格式以保持一致。

## 许可

MIT License — 详见 [LICENSE](./LICENSE) 文件。

---

*本项目由 AI 辅助构建，可能存在错误，请审慎使用。*
