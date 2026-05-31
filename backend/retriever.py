# retriever.py
import os

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates.txt")

def load_templates():
    """解析 templates.txt，返回模板列表"""
    templates = []
    if not os.path.exists(TEMPLATES_PATH):
        return templates

    with open(TEMPLATES_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('# 模板类型：'):
            if current:
                templates.append(current)
            current = {
                'name': stripped.split('：', 1)[1].strip(),
                'keywords': [],
                'content': ''
            }
        elif stripped.startswith('# 关键词：'):
            if current is not None:
                keywords_str = stripped.split('：', 1)[1].strip()
                # 兼容中英文逗号
                current['keywords'] = [
                    kw.strip() for kw in keywords_str.replace('，', ',').split(',') if kw.strip()
                ]
        elif current is not None:
            current['content'] += line 

    if current:
        templates.append(current)
    return templates

def match_template(user_message: str):
    """
    根据用户消息中的关键词匹配模板。
    如果未匹配到特定模板（模糊指令），则返回第一个模板（通用模板）作为兜底。
    """
    templates = load_templates()
    if not templates:
        return None
        
    best_template = None
    best_score = 0
    user_lower = user_message.lower()

    for tpl in templates:
        score = 0
        for kw in tpl['keywords']:
            if kw in user_lower:
                score += 1
        if score > best_score:
            best_score = score
            best_template = tpl

    # 如果匹配到了特定模板，返回它
    if best_template and best_score > 0:
        return best_template['content']
    
    # 否则（模糊指令），返回第一个模板（通用模板）
    return templates[0]['content']