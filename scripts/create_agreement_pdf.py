"""
Скрипт для создания PDF файла с пользовательским соглашением из MD файла
"""
import os
import sys
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
except ImportError:
    print("Установите reportlab: pip install reportlab")
    sys.exit(1)


def create_agreement_pdf(md_file_path: str, output_path: str = None):
    """Создает PDF файл с пользовательским соглашением из MD файла"""
    
    if output_path is None:
        output_path = md_file_path.replace('.md', '.pdf')
    
    # Читаем MD файл
    md_path = Path(md_file_path)
    if not md_path.exists():
        print(f"Файл не найден: {md_file_path}")
        return False
    
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Создаем PDF документ
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    
    # Стили
    styles = getSampleStyleSheet()
    
    # Кастомные стили
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor='black',
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor='black',
        spaceAfter=6,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor='black',
        spaceAfter=6,
        alignment=TA_JUSTIFY,
        fontName='Helvetica'
    )
    
    # Разбираем содержимое на параграфы
    story = []
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        
        if not line:
            story.append(Spacer(1, 6))
            continue
        
        # Заголовок документа
        if line.startswith('ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ'):
            story.append(Paragraph(line, title_style))
            continue
        
        # Заголовки разделов (номера разделов)
        if line and (line[0].isdigit() or line.startswith('•')):
            if line[0].isdigit() and '.' in line[:5]:
                # Это заголовок раздела (например, "1. ОПРЕДЕЛЕНИЯ И ТЕРМИНЫ")
                story.append(Paragraph(line, heading_style))
            else:
                # Это пункт списка или обычный текст
                story.append(Paragraph(line, normal_style))
        else:
            # Обычный текст
            story.append(Paragraph(line, normal_style))
    
    # Генерируем PDF
    try:
        doc.build(story)
        print(f"PDF файл успешно создан: {output_path}")
        return True
    except Exception as e:
        print(f"Ошибка при создании PDF: {e}")
        return False


if __name__ == "__main__":
    # Определяем путь к файлу соглашения
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    md_file = project_root / "docs" / "BEST_PR_System_Agreement.md"
    pdf_file = project_root / "docs" / "BEST_PR_System_Agreement.pdf"
    
    if md_file.exists():
        create_agreement_pdf(str(md_file), str(pdf_file))
    else:
        print(f"Файл соглашения не найден: {md_file}")
