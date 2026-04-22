#!/usr/bin/env python3
"""story.md 파일에 [이미지 필요] 마커를 삽입하는 스크립트.

1. ★ 빨간 용어(dc2626)의 첫 등장 위치에 [이미지 필요: ★{용어}]
2. 핵심 서사 키워드(도약, 빌런, 귀환 등) 위치에 [삽화 필요: {설명}]
"""
import re
import sys
from pathlib import Path

def extract_red_terms(line: str) -> list[str]:
    """한 줄에서 ★빨간 볼드 용어를 추출"""
    pattern = r'<span style="color:#dc2626;font-weight:bold">(★[^<]+)</span>'
    return re.findall(pattern, line)

def process_file(filepath: Path):
    lines = filepath.read_text(encoding='utf-8').splitlines()
    seen_terms = set()
    result = []

    for i, line in enumerate(lines):
        result.append(line)

        # ★ 용어 첫 등장에 마커 삽입
        terms = extract_red_terms(line)
        for term in terms:
            if term not in seen_terms:
                seen_terms.add(term)
                # 용어에서 ★ 제거한 이름
                clean = term.replace('★', '').strip()
                result.append('')
                result.append(f'[이미지 필요: {clean}]')

    filepath.write_text('\n'.join(result), encoding='utf-8')
    return len(seen_terms)

# 서사 장면 마커 삽입 (수동 정의)
NARRATIVE_MARKERS = {
    '1편-고대문명': [
        ('눈을 떴을 때', '[삽화 필요: 하나의 첫 시간 도약]'),
        ('별 가루 같은 빛', None),  # skip, too many
    ],
    '6편-마지막여행': [
        ('이거 진짜 무겁네', '[삽화 필요: 나루의 마지막 농담]'),
        ('똑딱, 한다', '[삽화 필요: 에필로그 — 가방 속 똑딱 소리]'),
    ],
}

def main():
    base = Path('/Users/griff_hq/Downloads/중2역사/소설')
    volumes = sorted(base.glob('*편-*/story.md'))

    total = 0
    for vol in volumes:
        count = process_file(vol)
        print(f'{vol.parent.name}: ★ 마커 {count}개 삽입')
        total += count

    print(f'\n총 {total}개 ★ 이미지 마커 삽입 완료')

if __name__ == '__main__':
    main()
