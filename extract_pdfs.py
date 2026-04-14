import json
import os
import re
import glob

chats_dir = '/Users/griff_hq/.gemini/tmp/griff-hq/chats'
files = glob.glob(os.path.join(chats_dir, '*.json'))
latest_file = max(files, key=os.path.getmtime)

with open(latest_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

prompt_text = ""
for msg in reversed(data.get('messages', [])):
    if msg.get('type') == 'user':
        content = msg.get('content', '')
        if isinstance(content, list):
            # sometimes content is a list of parts
            for part in content:
                if isinstance(part, dict) and 'text' in part and '--- Content from referenced files ---' in part['text']:
                    prompt_text = part['text']
                    break
                elif isinstance(part, str) and '--- Content from referenced files ---' in part:
                    prompt_text = part
                    break
            if prompt_text:
                break
        elif isinstance(content, str) and '--- Content from referenced files ---' in content:
            prompt_text = content
            break

if not prompt_text:
    print("Could not find the prompt text in messages.")
    exit(1)

content_start = prompt_text.find('--- Content from referenced files ---')
content_text = prompt_text[content_start:]

parts = content_text.split('==Start of OCR for page 1==')

out_dir = '/Users/griff_hq/Downloads/중2역사'

def clean_ocr(text):
    text = re.sub(r'==Start of OCR for page \d+==\n?', '', text)
    text = re.sub(r'==End of OCR for page \d+==\n?', '', text)
    # remove page numbers like "- 1 -" or "- 2 -"
    text = re.sub(r'(?m)^-\s*\d+\s*-\s*$', '', text)
    return text.strip()

doc_index = 1
for part in parts[1:]:
    part_text = '==Start of OCR for page 1==' + part
    
    match = re.search(r'역사①\s*(\d+)단원', part_text)
    if match:
        unit = match.group(1)
        filename = f'2025년 중2역사 {unit}단원 총정리 필기노트.md'
    else:
        filename = f'extracted_doc_{doc_index}.md'
    
    cleaned_text = clean_ocr(part_text)
    
    filepath = os.path.join(out_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as out_f:
        out_f.write(cleaned_text)
        print(f"Wrote {filepath}")
    
    doc_index += 1
