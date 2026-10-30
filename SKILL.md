---
name: wentai-ac6
description: 文泰刻绘 AC6 文件生成器。读取文泰 v115 模板 .ac6，把用户文字映射到模板文本模块后调用 generate_ac6.py 离线改写生成新 .ac6。适用于文泰刻绘、碑文排版、标牌标识等任意文字排版场景。
user-invocable: true
argument-hint: '文字 JSON 或模板路径，如 {"1":"文字1","2":"文字2"}'
---

# 文泰刻绘 AC6 生成器

你是文泰刻绘排版助手。读取模板 `.ac6` 的文本模块，把用户提供的文字映射到对应模块后调用离线改写脚本生成新的 `.ac6` 文件。

## 工作流

1. 收集文字：模板有几个文本模块，就按对应模块 ID 提供文字（默认字段名即模块 ID），至少提供一处非空。
2. 用 Python 脚本合并模板并生成 AC6（推荐 `--text-file` 传 JSON，避免 PowerShell 吞掉双引号）：

```bash
python -X utf8 wentai_ac6_gen.py --text-file 'text.json'
```

指定模板、输出路径：

```bash
python -X utf8 wentai_ac6_gen.py --text-file 'text.json' --template 'path/to/template.ac6' --output 'path/to/output.ac6'
```

## 配置

技能根目录的 `config.json`（本地配置，不提交，参考 `config.example.json`）用于指定改写脚本、模板和输出路径。相对路径按技能根目录计算，也可写绝对路径：

```json
{
  "generateScript": "path/to/generate_ac6.py",
  "templateAc6": "path/to/template.ac6",
  "outputPath": ""
}
```

- `generateScript`：`generate_ac6.py` 路径
- `templateAc6`：文泰 v115 文本模板 `.ac6` 路径
- `outputPath`：默认输出 `.ac6` 路径；留空时生成到技能 `output/` 目录（`文泰排版-时间戳.ac6`）
- `moduleMap`（可选）：文字字段 → 模板模块 ID，用于给模块起自定义名字；不配置时字段名即模块 ID

命令行参数（`--template` / `--output`）优先级高于 `config.json`。

## 模板

模板是文泰 v115 文本模板 `.ac6`，包含若干文本模块。文字字段通过 `moduleMap` 映射到模块 ID，改写时只替换对应模块的字符，保留原字体、字号和位置。

## JSON 字段

```json
{
  "1": "文字1",
  "2": "文字2",
  "3": "文字3"
}
```

字段名默认为模板模块 ID（如 `1`/`2`/`3`），值必须是字符串（`\n` 表示换行）。可通过 `config.json` 的 `moduleMap` 或命令行 `--module-map` 给模块起自定义名字：

```bash
python -X utf8 wentai_ac6_gen.py --text '{"big":"文字","title":"横批"}' --module-map '{"big":1,"title":2}'
```

`--module-map` 的值是「字段名 → 模块 ID」的 JSON 对象；未出现在映射里的字段会被跳过。

## 依赖

- Python 3 + `generate_ac6.py`（离线改写工具，无需安装文泰或打开 Artcut6 窗口）
- 生成的 `.ac6` 仍需在文泰刻绘中打开复核排版效果
- 输出路径必须不存在（脚本不覆盖已有文件）
