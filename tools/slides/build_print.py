# -*- coding: utf-8 -*-
"""Собирает из слайдов колоды один print.html (для PDF и проверки).

    python3 tools/slides/build_print.py slides/FlexTail <папка_вывода>

Слайды лежат в <колода>/project/slides/<id>.html, порядок — в <колода>/project/deck.json.
Специальные теги артефакта (<x-shape>, <x-icon>) заменяются обычной разметкой, <aside> (заметки докладчика) убирается."""
import html
import json
import os
import re
import sys

ARROW = '<div style="clip-path:polygon(0 0,100%% 0,50%% 100%%);%s"></div>'
CHECK = ('<svg viewBox="0 0 24 24" style="%s" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" '
         'stroke-linejoin="round"><path d="M4 12.5l5 5L20 6.5"/></svg>')


def main(deck_dir, out_dir):
    root = os.path.join(deck_dir, 'project')
    with open(os.path.join(root, 'deck.json'), encoding='utf-8') as f:
        deck = json.load(f)
    pages = []
    for sid in deck['order']:
        with open(os.path.join(root, 'slides', sid + '.html'), encoding='utf-8') as f:
            s = f.read()
        s = re.sub(r'<x-shape kind="arrow-down" style="([^"]*)"></x-shape>', lambda m: ARROW % m.group(1), s)
        s = re.sub(r'<x-icon name="Check" style="([^"]*)"></x-icon>', lambda m: CHECK % m.group(1), s)
        s = re.sub(r'<aside>.*?</aside>', '', s, flags=re.S)
        assert '<x-' not in s, 'неизвестный тег <x-…> в слайде ' + sid
        pages.append(s)
    page = ('<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>%s</title>\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">\n'
            '<style>\n@page{size:1920px 1080px;margin:0}\nhtml,body{margin:0;padding:0}\n'
            'section{position:relative;width:1920px;height:1080px;box-sizing:border-box;overflow:hidden;'
            'page-break-after:always;break-after:page}\nsection:last-of-type{page-break-after:auto;break-after:auto}\n'
            'h1,h2,h3,p,ul,ol{margin:0}\n</style></head><body>%s</body></html>') % (
        html.escape(deck['title']), '\n'.join(pages))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'print.html'), 'w', encoding='utf-8') as f:
        f.write(page)
    print(len(pages), 'слайдов ->', os.path.join(out_dir, 'print.html'))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
