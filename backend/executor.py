import subprocess

def build_command_args(properties: dict) -> list:
    args = []
    for key, value in properties.items():
        # 统一转换为 --prop 路径，确保所有属性都被 OfficeCLI 识别
        # 根据 OfficeCLI 文档映射：
        prop_map = {
            "bold": "rPr.b.val",
            "italic": "rPr.i.val",
            "underline": "rPr.u.val",
            "strike": "rPr.strike.val",
            "size": "rPr.sz.val",
            "font-eastasia": "rPr.rFonts.eastAsia",
            "font-ascii": "rPr.rFonts.ascii",
            "color": "rPr.color.val",
            "highlight": "rPr.highlight.val",
            "alignment": "pPr.jc.val",
            "spacing-before": "pPr.spacing.before",
            "spacing-after": "pPr.spacing.after",
            "line-spacing": "pPr.spacing.line",
            "indent-firstline": "pPr.ind.firstLine",
            "indent-left": "pPr.ind.left",
            "indent-right": "pPr.ind.right",
            "outline-level": "pPr.outlineLvl.val",   # 原 prop.outlineLvl.val 的简化版
            "page-break-before": "pPr.pageBreakBefore.val",
            "keep-next": "pPr.keepNext.val",
            "keep-lines": "pPr.keepLines.val",
            # 表格不在支持范围内，这里忽略
        }
        if key.startswith("prop."):
            prop_path = key[5:]
            args.extend(["--prop", f"{prop_path}={value}"])
        elif key in prop_map:
            prop_path = prop_map[key]
            str_value = str(value).lower() if isinstance(value, bool) else value
            args.extend(["--prop", f"{prop_path}={str_value}"])
        else:
            # 未知属性，尝试用原键作为 prop 路径（但这可能也无效，记录警告）
            args.extend(["--prop", f"{key}={value}"])
    return args

def execute_operations(doc_path: str, operations: list):
    results = []
    for i, op in enumerate(operations):
        path = op.get("path")
        action = op.get("action", "set")
        props = op.get("properties", {})

        if not path:
            results.append({"index": i, "status": "skipped", "reason": "缺少路径"})
            continue
        if action != "set":
            results.append({"index": i, "status": "skipped", "reason": f"不支持的操作类型: {action}"})
            continue

        # 如果是表格路径（包含 /tbl[ ），直接跳过并告知不支持
        if "/tbl[" in path:
            results.append({
                "index": i,
                "status": "skipped",
                "reason": "表格属性修改暂不支持，已跳过"
            })
            continue

        cmd = ["officecli", "set", doc_path, path] + build_command_args(props)
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            results.append({"index": i, "status": "success"})
        except subprocess.CalledProcessError as e:
            results.append({
                "index": i,
                "status": "error",
                "command": " ".join(cmd),
                "stderr": e.stderr.strip(),
                "stdout": e.stdout.strip()
            })
    return results