# dehydrator.py (自适应基准 + 状态机继承 + 无用值净化)
import json
from collections import Counter

# 1. 基础样式普查（不含缩进、段前段后等结构化属性，防止格式污染）
DYNAMIC_CHECK_KEYS = [
    "effective.font.eastAsia", "effective.font.ascii", 
    "effective.size", "effective.bold", "effective.italic", "effective.color"
]

# 2. OfficeCli拆解的json中，所保留的样式元素清单
CORE_STYLE_KEYS = [
    "effective.font.eastAsia", "effective.font.ascii", "effective.size",
    "effective.bold", "effective.italic", "effective.underline", "effective.strike",
    "effective.color", "effective.highlight", "effective.alignment",
    "effective.indent.firstLine", "effective.indent.left", "effective.indent.right",
    "effective.spaceBefore", "effective.spaceAfter", "effective.lineSpacing",
    "effective.pageBreakBefore", "effective.keepNext", "effective.keepLines",
    "outlineLevel", "effective.verticalAlignment"
]

def calculate_dynamic_baseline(raw_nodes):
    """
    【第一遍扫描】：全文档基本样式动态普查
    """
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


def extract_smart_styles(format_dict, baseline):
    """
    【智能过滤】：去基准线 + 剔除无用冗余(none/False)
    """
    smart_styles = {}
    for key in CORE_STYLE_KEYS:
        val = format_dict.get(key)
        if key == "effective.color" and not val:
            val = format_dict.get("color")
            
        if val is not None:
            # 1. 如果跟全篇样式相同则忽略
            if val == baseline.get(key):
                continue
                
            # 2. 如果不是基本属性，且值是默认的无用状态 (none/False/0pt)忽略
            if key not in baseline and val in ["none", False, "", "0pt"]:
                continue

            clean_key = key.replace("effective.", "")
            smart_styles[clean_key] = val
                
    return smart_styles


def process_paragraph(node, document_baseline, state_tracker):
    """
    【状态机段落处理】：携带游标记忆，实现相同格式隐身继承
    """
    path = node.get("path", "")
    text = node.get("text", "").strip()
    style_name = node.get("style", "Normal")
    format_dict = node.get("format", {})

    # 遇到空行：直接返回，且【不更新】状态机，让下一段能隔空继承上一段的状态
    if not text:
        return {"path": path, "text": ""}

    clean_node = {"path": path, "text": text}

    if style_name != "Normal" and style_name != "Normal (Web)":
        clean_node["style"] = style_name

    parent_styles = extract_smart_styles(format_dict, document_baseline)
    
    # 状态继承法 (Run-Length Encoding)
    # 如果当过滤后的样式，跟状态机里记录的上一个段落一模一样
    if parent_styles == state_tracker.get("last_styles"):
        pass # 直接忽略什么都不往 clean_node 里加
    else:
        # 否则，挂载新样式，并更新状态机
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


def process_table(node, document_baseline):
    """
    处理表格：为每个单元格注入独立的状态机
    """
    table_node = {"path": node.get("path"), "type": "table", "rows": []}
    for row in node.get("children", []):
        if row.get("type") != "row": continue
        row_data = {"path": row.get("path"), "cells": []}
        for cell in row.get("children", []):
            if cell.get("type") != "cell": continue
            cell_data = {"path": cell.get("path"), "paragraphs": []}
            
            # 每个单元格拥有独立的微型状态机，防止错乱继承
            cell_state_tracker = {"last_styles": None}
            
            for cell_child in cell.get("children", []):
                if cell_child.get("type") == "paragraph":
                    cell_data["paragraphs"].append(process_paragraph(cell_child, document_baseline, cell_state_tracker))
            row_data["cells"].append(cell_data)
        table_node["rows"].append(row_data)
    return table_node


def dehydrate_document(raw_json):
    """
    【总阀门】
    """
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
    
    # 初始化主线文本的状态机
    main_state_tracker = {"last_styles": None}
    
    for node in raw_nodes:
        if not isinstance(node, dict): continue
        node_type = node.get("type")
        
        if node_type == "paragraph":
            dehydrated_list.append(process_paragraph(node, document_baseline, main_state_tracker))
        elif node_type == "table":
            # 遇到表格，切断主线状态继承，防止表格后的正文错误继承表格内的数据
            main_state_tracker["last_styles"] = None
            dehydrated_list.append(process_table(node, document_baseline))

    return dehydrated_list