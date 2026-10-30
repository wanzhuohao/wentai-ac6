#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文泰刻绘 AC6 生成器（离线改写）
读取文泰 v115 模板 .ac6，把用户文字映射到模板的文本模块后，
调用 ac6-tool/generate_ac6.py 离线改写生成新的 .ac6 文件。

用法:
  python wentai_ac6_gen.py --text '{"1":"文字1","2":"文字2"}' --template template.ac6 --output output.ac6
  python wentai_ac6_gen.py --text-file text.json

模板、改写脚本和输出路径可在 config.json 中配置（见 config.example.json），
命令行参数优先级高于 config.json。
字段映射动态读取模板模块：默认用模块 ID 作为字段名；字段名与模块 ID 不同时，
用 --module-map '{"big":1,"title":2}' 显式指定，或在 config.json 的 moduleMap 里自定义。
"""
import json
import os
import sys
import tempfile
import datetime
import subprocess

# 字段/模块映射动态读取模板：config.json 的 moduleMap 优先，
# 否则用模板模块 ID 本身作为字段名（如 {"1": "...", "2": "..."}）

# generate_ac6.py 候选相对路径
AC6_SCRIPT_CANDIDATES = [
    os.path.join('..', '..', 'stele-desktop', 'ac6-tool', 'generate_ac6.py'),
    os.path.join('..', '..', '..', 'stele-desktop', 'ac6-tool', 'generate_ac6.py'),
]

# template.ac6 候选相对路径
AC6_TEMPLATE_CANDIDATES = [
    os.path.join('..', '..', 'stele-desktop', 'ac6-tool', 'template.ac6'),
    os.path.join('..', '..', '..', 'stele-desktop', 'ac6-tool', 'template.ac6'),
]

# 默认输出目录（相对技能根目录）
DEFAULT_OUTPUT_DIR = 'output'


def _decode_console(raw):
    """Windows 控制台输出字节解码：优先 UTF-8，失败后按 GBK 兜底"""
    if raw is None:
        return ''
    for enc in ('utf-8', 'gbk'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def load_config(base_dir):
    """读取技能根目录下的 config.json；缺失或损坏时返回空配置"""
    cfg_path = os.path.join(base_dir, 'config.json')
    if not os.path.isfile(cfg_path):
        return {}
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:
        return {}
    return cfg if isinstance(cfg, dict) else {}


def resolve_path(base_dir, value):
    """把配置/命令行里的路径解析为绝对路径；相对路径按技能根目录计算"""
    value = str(value or '').strip()
    if not value:
        return ''
    if os.path.isabs(value):
        return value
    return os.path.normpath(os.path.join(base_dir, value))


def resolve_script(base_dir, config):
    """定位 generate_ac6.py：config.json 的 generateScript 优先，其次候选相对路径"""
    candidates = []
    configured = resolve_path(base_dir, config.get('generateScript'))
    if configured:
        candidates.append(configured)
    for rel in AC6_SCRIPT_CANDIDATES:
        candidates.append(os.path.join(base_dir, rel))
    for path in candidates:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    return None


def resolve_template(base_dir, template_path, config):
    """模板路径：命令行优先，其次 config.json，最后候选相对路径"""
    candidates = []
    if template_path:
        candidates.append(resolve_path(base_dir, template_path))
    configured = resolve_path(base_dir, config.get('templateAc6'))
    if configured:
        candidates.append(configured)
    for rel in AC6_TEMPLATE_CANDIDATES:
        candidates.append(os.path.join(base_dir, rel))
    for path in candidates:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    return ''


def resolve_output(base_dir, output_path, config):
    """输出路径：命令行优先，其次 config.json；为空时生成唯一默认路径"""
    path = resolve_path(base_dir, output_path or config.get('outputPath'))
    if path:
        return path
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out_dir = os.path.join(base_dir, DEFAULT_OUTPUT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, '文泰排版-%s.ac6' % ts)


def list_template_modules(script, template):
    """读取模板的模块 ID 列表（动态，不写死个数）"""
    cmd = [sys.executable, '-X', 'utf8', script, 'list', template]
    proc = subprocess.run(cmd, capture_output=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError('读取模板模块失败: %s' % _decode_console(proc.stderr))
    info = json.loads(_decode_console(proc.stdout))
    return [module['id'] for module in info['modules']]


def resolve_module_map(config, module_ids, override=None):
    """模块映射：命令行 override 优先，其次 config.json 的 moduleMap，否则用模块 ID 本身作为字段名"""
    custom = override if override else config.get('moduleMap')
    if isinstance(custom, dict):
        merged = {}
        for key, value in custom.items():
            if isinstance(value, int) and value in module_ids:
                merged[key] = value
        return merged
    return {str(mid): mid for mid in module_ids}


def build_replacements(text_fields, module_map):
    """把用户文字映射为 {模块ID: 文本}；保留换行，空文字和空模块跳过"""
    replacements = {}
    for field, text in text_fields.items():
        module_id = module_map.get(field)
        if module_id and str(text).strip():
            replacements[str(module_id)] = str(text)
    return replacements


def build_payload(text_fields):
    """构造输入文本 JSON（保留原始字段，仅用于回查）"""
    return {field: str(value) for field, value in text_fields.items()}


def generate(base_dir, text_fields, template_path, output_path, module_map=None):
    """读取配置 → 构建替换表 → 调用 generate_ac6.py 离线改写 → 返回结果"""
    config = load_config(base_dir)

    script = resolve_script(base_dir, config)
    if not script:
        raise RuntimeError('找不到 generate_ac6.py；请在 config.json 的 generateScript 指定')

    template = resolve_template(base_dir, template_path, config)
    if not template or not os.path.isfile(template):
        raise RuntimeError('找不到 AC6 模板: %s' % (template or '(未配置)'))

    module_ids = list_template_modules(script, template)
    module_map_resolved = resolve_module_map(config, module_ids, module_map)
    replacements = build_replacements(text_fields, module_map_resolved)
    if not replacements:
        raise RuntimeError('文字全为空，至少需要提供一处文字')

    output = resolve_output(base_dir, output_path, config)
    if output.lower().endswith('.ac6') and os.path.exists(output):
        raise RuntimeError('输出文件已存在，不覆盖: %s' % output)

    payload = build_payload(text_fields)
    tmpdir = tempfile.mkdtemp(prefix='wentai_ac6_')
    json_path = os.path.join(tmpdir, 'text.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    replacements_path = os.path.join(tmpdir, 'replacements.json')
    with open(replacements_path, 'w', encoding='utf-8') as f:
        json.dump(replacements, f, ensure_ascii=False, indent=2)

    cmd = [sys.executable, '-X', 'utf8', script, 'replace', template,
           '--replacements', replacements_path, '--output', output]

    proc = subprocess.run(cmd, capture_output=True, timeout=150)
    out = _decode_console(proc.stdout)
    err = _decode_console(proc.stderr)

    ac6_path = output if os.path.isfile(output) else ''
    return {
        'exit_code': proc.returncode,
        'ac6_path': ac6_path,
        'input_json': json_path,
        'stdout': out,
        'stderr': err,
    }


if __name__ == '__main__':
    text_json = ''
    text_file = ''
    template_path = ''
    output_path = ''
    module_map_json = ''
    for i, arg in enumerate(sys.argv):
        if arg in ('--text', '--text-file', '--template', '--output', '--module-map') and i + 1 < len(sys.argv):
            value = sys.argv[i + 1]
            if arg == '--text':
                text_json = value
            elif arg == '--text-file':
                text_file = value
            elif arg == '--template':
                template_path = value
            elif arg == '--output':
                output_path = value
            elif arg == '--module-map':
                module_map_json = value

    base_dir = os.path.dirname(os.path.abspath(__file__))
    if not text_json and not text_file and not template_path and not output_path:
        print('用法: python wentai_ac6_gen.py --text \'<JSON>\' [--template <模板.ac6>] [--output <输出.ac6>]')
        print('     也可 python wentai_ac6_gen.py --text-file <JSON文件>')
        print('字段默认用模板模块 ID 作为 key（如 {"1":"文字1","2":"文字2"}），可在 config.json 的 moduleMap 自定义')
        print('若字段名与模块 ID 不同，可用 --module-map \'{"big":1,"title":2}\' 显式指定映射')
        print('模板/脚本/输出路径可在 config.json 配置（见 config.example.json）')
        print('示例: python wentai_ac6_gen.py --text-file text.json')
        sys.exit(2)
    try:
        if text_file:
            with open(text_file, 'r', encoding='utf-8-sig') as f:
                text_fields = json.load(f)
        else:
            text_fields = json.loads(text_json) if text_json else {}
        if not isinstance(text_fields, dict):
            raise ValueError('文字必须是 JSON 对象')
        module_map = json.loads(module_map_json) if module_map_json else None
        if module_map is not None and not isinstance(module_map, dict):
            raise ValueError('--module-map 必须是 JSON 对象')
        result = generate(base_dir, text_fields, template_path, output_path, module_map)
        print(json.dumps({
            'exit_code': result['exit_code'],
            'ac6_path': result['ac6_path'],
            'input_json': result['input_json'],
        }, ensure_ascii=False))
        if result['stdout']:
            print(result['stdout'])
        if result['stderr']:
            print(result['stderr'], file=sys.stderr)
    except Exception as exc:
        print('生成失败: %s' % exc, file=sys.stderr)
        sys.exit(2)
