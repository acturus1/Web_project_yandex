import markdown

def convert_md_to_html(path_to_md: str):
    """Конвертирует Markdown файл в HTML используя библиотеку markdown"""
    try:
        with open(path_to_md, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        html_content = markdown.markdown(md_content)
        
        path_to_html = path_to_md[:-3] + ".html"
        with open(path_to_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return True
    except Exception as e:
        print(f"Ошибка конвертации: {str(e)}")
        return False
