# dehydrator.py (OfficeCLI aligned key names + dynamic baseline + state machine)
import json
from collections import Counter

# 1. 基础普查键（用于计算文档基准线，使用内部字段名）
DYNAMIC_CHECK_KEYS = [
    "effective.font.eastAsia", "effective.font.ascii",
    "effective.size", "effective.bold", "effective.italic", "effective.color"
]

# 2. 核心样式键（内部字段名）
CORE_STYLE_KEYS = [
    "effective.font.eastAsia", "effective.font.ascii", "effective.size",
    "effective.bold", "effective.italic", "effective.underline", "effective.strike",
    "effective.color", "effective.highlight", "effective.alignment",
    "effective.indent.firstLine", "effective.indent.left", "effective.indent.right",
    "effective.spaceBefore", "effective.spaceAfter", "effective.lineSpacing",
    "effective.pageBreakBefore", "effective.keepNext", "effective.keepLines",
]

# 字段映射：内部字段名 -> OfficeCLI 参数名
KEY_MAPPING = {
    "effective.font.eastAsia": "font-eastasia",
    "effective.font.ascii": "font-ascii",
    "effective.size": "size",
    "effective.bold": "bold",
    "effective.italic": "italic",
    "effective.underline": "underline",
    "effective.strike": "strike",
    "effective.color": "color",
    "effective.highlight": "highlight",
    "effective.alignment": "alignment",
    "effective.indent.firstLine": "indent-firstline",
    "effective.indent.left": "indent-left",
    "effective.indent.right": "indent-right",
    "effective.spaceBefore": "spacing-before",
    "effective.spaceAfter": "spacing-after",
    "effective.lineSpacing": "line-spacing",
    "effective.pageBreakBefore": "prop.pageBreakBefore.val",
    "effective.keepNext": "prop.keepNext.val",
    "effective.keepLines": "prop.keepLines.val",
    "outlineLevel": "prop.outlineLvl.val",
}

# 计算动态基准线：统计文档中最常见的样式值，作为默认样式的参考
def calculate_dynamic_baseline(raw_nodes):
    style_counters = {key: Counter() for key in DYNAMIC_CHECK_KEYS}

    def scan_node(node):
        if node.get("type") == "paragraph":
            fmt = node.get("format", {})
            for key in DYNAMIC_CHECK_KEYS:
                val = fmt.get(key)
                if key == "effective.color" and not val:
                    val = fmt.get("color")
                if val is not None:
                    style_counters[key][str(val)] = val
        elif node.get("type") == "table":
            for row in node.get("children", []):
                for cell in row.get("children", []):
                    for p in cell.get("children", []):
                        scan_node(p)

    for node in raw_nodes:
        scan_node(node)

    dynamic_baseline = {}
    for key, counter in style_counters.items():
        if counter:
            most_common_str = counter.most_common(1)[0][0]
            dynamic_baseline[key] = style_counters[key][most_common_str]
    return dynamic_baseline

# 提取智能样式：根据当前节点的格式与基准线对比，提取需要保留的样式属性，并映射为 OfficeCLI 参数名
def extract_smart_styles(format_dict, baseline):
    smart_styles = {}
    for internal_key in CORE_STYLE_KEYS:
        val = format_dict.get(internal_key)
        if internal_key == "effective.color" and not val:
            val = format_dict.get("color")

        if val is not None:
            # 如果跟全篇基准一样，忽略
            if val == baseline.get(internal_key):
                continue

            # 如果不是基本属性且值为默认无用状态，忽略
            if internal_key not in baseline and val in ["none", False, "", "0pt"]:
                continue

            # 映射为 OfficeCLI 参数名
            mapped_key = KEY_MAPPING.get(internal_key, internal_key)
            # 特殊处理 color：必须包含 # 或为颜色名称，确保 OfficeCLI 可用
            if mapped_key == "color":
                # 确保是有效颜色值，如果不是一般格式，暂时保留原样
                pass
            smart_styles[mapped_key] = val
    return smart_styles

# 处理段落节点：提取文本、样式，简化相同的json，并处理 Runs 中的局部格式突变
def process_paragraph(node, document_baseline, state_tracker):
    path = node.get("path", "")
    text = node.get("text", "").strip()
    style_name = node.get("style", "Normal")
    format_dict = node.get("format", {})

    if not text:
        return {"path": path, "text": ""}

    clean_node = {"path": path, "text": text}

    if style_name != "Normal" and style_name != "Normal (Web)":
        clean_node["style"] = style_name

    parent_styles = extract_smart_styles(format_dict, document_baseline)

    if parent_styles == state_tracker.get("last_styles"):
        pass
    else:
        if parent_styles:
            clean_node.update(parent_styles)
        state_tracker["last_styles"] = parent_styles

    # 处理 Runs (局部格式突变)
    runs_diff = []
    raw_children = node.get("children", [])
    if len(raw_children) == 1 and raw_children[0].get("type") == "run" and raw_children[0].get("text", "").strip() == text:
        pass
    else:
        for child in raw_children:
            if child.get("type") == "run":
                run_text = child.get("text", "").strip()
                if not run_text:
                    continue
                run_format = child.get("format", {})
                run_specific_styles = extract_smart_styles(run_format, format_dict)
                if run_specific_styles:
                    run_diff_node = {"path": child.get("path"), "text": run_text}
                    run_diff_node.update(run_specific_styles)
                    runs_diff.append(run_diff_node)
    if runs_diff:
        clean_node["runs"] = runs_diff

    return clean_node

# 处理表格节点：递归处理表格结构，提取行、单元格、段落信息，并应用样式基准线
def process_table(node, document_baseline):
    table_node = {"path": node.get("path"), "type": "table", "rows": []}
    for row in node.get("children", []):
        if row.get("type") != "row": continue
        row_data = {"path": row.get("path"), "cells": []}
        for cell in row.get("children", []):
            if cell.get("type") != "cell": continue
            cell_data = {"path": cell.get("path"), "paragraphs": []}
            cell_state_tracker = {"last_styles": None}
            for cell_child in cell.get("children", []):
                if cell_child.get("type") == "paragraph":
                    cell_data["paragraphs"].append(process_paragraph(cell_child, document_baseline, cell_state_tracker))
            row_data["cells"].append(cell_data)
        table_node["rows"].append(row_data)
    return table_node

# 主函数：脱水文档，返回简化的段落和表格结构，包含智能样式提取和动态基准线计算
def dehydrate_document(raw_json):
    try:
        if not raw_json or "data" not in raw_json: return []
        results = raw_json.get("data", {}).get("results", [])
        if not results: return []
        raw_nodes = results[0].get("children", [])
        if not raw_nodes: return []
    except Exception:
        return []

    document_baseline = calculate_dynamic_baseline(raw_nodes)
    dehydrated_list = []
    main_state_tracker = {"last_styles": None}
    global_para_index = 0   # 新增：全局段落计数器

    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        node_type = node.get("type")
        if node_type == "paragraph":
            # 调用处理函数，拿到脱水后的段落节点
            dehydrated_node = process_paragraph(node, document_baseline, main_state_tracker)
            # 加入全局段落索引
            dehydrated_node["index"] = global_para_index
            global_para_index += 1
            dehydrated_list.append(dehydrated_node)
        elif node_type == "table":
            main_state_tracker["last_styles"] = None
            dehydrated_list.append(process_table(node, document_baseline))

    return dehydrated_list