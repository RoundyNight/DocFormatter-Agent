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
                current['keywords'] = [
                    kw.strip() for kw in keywords_str.replace('，', ',').split(',')
                ]
        elif current is not None:
            current['content'] += line  # 保留原始换行和缩进

    if current:
        templates.append(current)
    return templates


def match_template(user_message: str):
    """
    根据用户消息中的关键词匹配模板
    返回最匹配模板的 content（字符串），如果没有匹配则返回 None
    """
    templates = load_templates()
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

    return best_template['content'] if best_template else None