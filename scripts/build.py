"""Build the accessible course reader from the supplied PPT content.

No third-party packages, build service or browser network calls are required.
"""
from pathlib import Path
from html import escape
import json
import re

ROOT = Path(__file__).resolve().parents[1]
COURSE = json.loads((ROOT / 'content/course.json').read_text())
DECKS = json.loads((ROOT / 'content/ppt-content.json').read_text())
READINGS = json.loads((ROOT / 'content/readings.json').read_text()) if (ROOT / 'content/readings.json').exists() else []
SEARCH = []
OUTLINES = {}
COUNTS = {'topics': 0, 'tables': 0, 'prompts': 0}

URL = re.compile(r'(?<![\w@])(?:https?://)?(?:[a-zA-Z0-9-]+\.)+(?:com|org|edu|gov|net|new|so|google)(?:/[^\s<>]*)?')


def clean(t):
    t = t.strip().replace('\\n', '\n')
    t = re.sub(r'^[📁📂📄📊📋📝🖼📕🔗⭐🏫📚☎♪✦]+\s*', '', t)
    return t


def inline(t):
    """Link explicit service/source addresses, without linking email addresses."""
    t = clean(t)
    out = []
    start = 0
    for m in URL.finditer(t):
        raw = m.group().rstrip('.,，。)）]')
        end = m.start() + len(raw)
        out.append(escape(t[start:m.start()]))
        url = raw if raw.startswith(('https://', 'http://')) else 'https://' + raw
        out.append(f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(raw)}</a>')
        start = end
    out.append(escape(t[start:]))
    result = ''.join(out).replace('\n', '<br>')
    if t.startswith('='):
        result = '<code>' + result + '</code>'
    return result


def paragraphs(texts, small=False):
    out, lis, checklist = [], [], []

    def flush():
        if lis:
            out.append('<ul>' + ''.join(f'<li>{inline(x)}</li>' for x in lis) + '</ul>')
            lis.clear()
        if checklist:
            out.append('<ul class="checklist">' + ''.join(f'<li>{inline(x)}</li>' for x in checklist) + '</ul>')
            checklist.clear()

    for raw in texts:
        t = clean(raw)
        if not t or t in ['└', 'vs', 'O', 'X', '直接 해보기', '직접 해보기']:
            continue
        if t.startswith(('•', '→ ', '- ')):
            if checklist:
                flush()
            lis.append(re.sub(r'^(?:•|→|-)[\s]*', '', t))
        elif t.startswith(('☐', '☑', '✓ ')):
            if lis:
                flush()
            checklist.append(re.sub(r'^[☐☑✓]\s*', '', t))
        elif re.fullmatch(r'\d{1,2}', t):
            continue
        else:
            flush()
            cls = ' class="secondary"' if small else ''
            out.append(f'<p{cls}>{inline(t)}</p>')
    flush()
    return ''.join(out)


def table_html(rows, title):
    COUNTS['tables'] += 1
    out = [f'<div class="table-scroll" tabindex="0" role="region" aria-label="{escape(title, quote=True)} 표"><table><caption class="sr-only">{escape(title)}</caption>']
    for i, row in enumerate(rows):
        out.append('<thead><tr>' if i == 0 else '<tr>')
        for j, cell in enumerate(row):
            tag = 'th' if i == 0 else 'td'
            scope = ' scope="col"' if i == 0 else ''
            out.append(f'<{tag}{scope}>' + '<br>'.join(inline(t) for t in cell if t.strip()) + f'</{tag}>')
        out.append('</tr></thead><tbody>' if i == 0 else '</tr>')
    out.append('</tbody></table></div>')
    return ''.join(out)


def shape_text(n):
    return '\n'.join(n.get('text', [])).strip()


def plain(n):
    if n['type'] == 'table':
        return ' '.join(' '.join(c) for r in n['rows'] for c in r)
    return shape_text(n)


def row_groups(nodes):
    groups = []
    for n in sorted(nodes, key=lambda n: (n['y'], n['x'])):
        found = next((g for g in groups if abs(g[0]['y'] - n['y']) < 80000), None)
        if found is None:
            groups.append([n])
        else:
            found.append(n)
    return [sorted(g, key=lambda n: n['x']) for g in groups]


def basic_group(nodes):
    """Recover headings and paragraphs inside each column of the PPT."""
    out = []
    for n in sorted(nodes, key=lambda n: (n['y'], n['x'])):
        if n['type'] == 'table':
            out.append(table_html(n['rows'], '자료'))
        else:
            ts = n['text']
            t = shape_text(n)
            if not t or re.fullmatch(r'\d{1,2}', t):
                continue
            if n['h'] < 690000 and len(t) < 65 and not t.startswith(('•', '☐', '→', '✓')):
                out.append('<h5>' + inline(t) + '</h5>')
            else:
                out.append(paragraphs(ts))
    return ''.join(out)


def generic(nodes, title):
    if not nodes:
        return ''
    tables = [n for n in nodes if n['type'] == 'table']
    if tables:
        return ''.join(table_html(n['rows'], title) if n['type'] == 'table' else paragraphs(n['text']) for n in sorted(nodes, key=lambda n: (n['y'], n['x'])))
    groups = row_groups(nodes)
    # Definition rows and relationship diagrams are already aligned in the source.
    if len(groups) >= 2 and all(len(g) == 2 for g in groups) and all(g[0]['w'] < 3800000 and g[1]['x'] - g[0]['x'] > 1800000 for g in groups):
        return '<dl class="definitions">' + ''.join('<div><dt>' + inline(shape_text(g[0])) + '</dt><dd>' + paragraphs(g[1]['text']) + '</dd></div>' for g in groups) + '</dl>'
    # Preserve native table-like drawings as tables instead of flattened strings.
    repeated = [g for g in groups if len(g) >= 4]
    if len(repeated) >= 3 and len(set(len(g) for g in repeated)) == 1:
        xs = [[n['x'] for n in g] for g in repeated]
        if all(all(abs(a-b) < 100000 for a, b in zip(xs[0], row)) for row in xs[1:]):
            prefix = [n for n in nodes if not any(n in g for g in repeated)]
            return table_html([[n['text'] for n in g] for g in repeated], title) + basic_group(prefix)
    # Two- or three-column concept comparisons.
    top = min(n['y'] for n in nodes)
    headings = [n for n in nodes if n['y'] <= top + 350000 and n['type'] == 'text' and n['w'] < 5800000 and not re.fullmatch(r'\d{1,2}', shape_text(n))]
    anchors = []
    for n in sorted(headings, key=lambda n: n['x']):
        if not anchors or n['x'] - anchors[-1] > 2300000:
            anchors.append(n['x'])
    if len(anchors) in [2, 3] and all(n['w'] < 5800000 for n in nodes):
        cols = [[] for _ in anchors]
        for n in nodes:
            i = min(range(len(anchors)), key=lambda i: abs(anchors[i]-n['x']))
            cols[i].append(n)
        return '<div class="concept-grid">' + ''.join('<div>' + basic_group(col) + '</div>' for col in cols if col) + '</div>'
    return basic_group(nodes)


def procedure(nodes, exercise=False):
    nums = [n for n in nodes if n['type'] == 'text' and re.fullmatch(r'[1-9]', shape_text(n)) and n['x'] < 1300000]
    if len(nums) < 2:
        return None
    nums.sort(key=lambda n: n['y'])
    content = [n for n in nodes if n not in nums]
    side = [n for n in content if exercise and n['x'] >= 7350000]
    mains = [n for n in content if n not in side]
    rows = [[] for _ in nums]
    for n in mains:
        nearest = min(range(len(nums)), key=lambda i: abs((nums[i]['y'] + nums[i]['h']/2) - (n['y'] + n['h']/2)))
        rows[nearest].append(n)
    out = '<ol class="steps">'
    for row in rows:
        row.sort(key=lambda n: n['x'])
        out += '<li>' + ''.join(paragraphs(n['text'], small=(i > 0)) if n['type']=='text' else table_html(n['rows'], '실습') for i, n in enumerate(row)) + '</li>'
    out += '</ol>'
    if side:
        out += '<div class="exercise-notes">' + basic_group(side) + '</div>'
    return out


def prompt(nodes, sid):
    labels = [n for n in nodes if n['type'] == 'text' and '복사해서 바꿔 쓰는 요청문' in shape_text(n)]
    if not labels:
        return None
    left = [n for n in nodes if n['type']=='text' and n['x'] < 8000000 and n not in labels]
    if not left:
        return None
    value = '\n'.join(shape_text(n) for n in sorted(left,key=lambda n:n['y']))
    COUNTS['prompts'] += 1
    right = [n for n in nodes if n not in left and n not in labels]
    return f'<div class="prompt"><div class="prompt-head"><span>요청문 예시</span><button type="button" class="copy-button" data-copy="prompt-{sid}" aria-label="요청문 복사">복사</button></div><pre id="prompt-{sid}">{escape(value)}</pre></div>' + ('<div class="prompt-tip">' + basic_group(right) + '</div>' if right else '')


def sources(nodes):
    out = ['<ul class="source-list">']
    for g in row_groups([n for n in nodes if n['type']=='text' and not shape_text(n).startswith('확인일')]):
        if len(g)==2:
            label, address = shape_text(g[0]), shape_text(g[1])
            if URL.fullmatch(address):
                url=address if address.startswith('http') else 'https://'+address
                out.append(f'<li><a href="{escape(url,quote=True)}" target="_blank" rel="noopener noreferrer">{escape(label)}<span>{escape(address.split("/")[0])}</span></a></li>')
                continue
        out.append('<li>'+''.join(paragraphs(n['text']) for n in g)+'</li>')
    out.append('</ul>')
    return ''.join(out)


OVERRIDES = {
    (4,50): '<dl class="definitions"><div><dt>서비스 이름</dt><dd>Gemini는 우리가 사용하는 앱·웹 서비스 이름입니다.</dd></div><div><dt>모델 이름</dt><dd>서비스 안에서 답을 만드는 엔진입니다. Google은 2026년 9월 30일 Gemini 4 Argon을 발표했습니다. 발표문에서는 신뢰할 수 있는 보안 분야 사용자부터 검증하고 일반 공개를 준비한다고 설명합니다. 새 모델의 발표가 내 계정의 사용 가능을 뜻하지는 않습니다.</dd></div><div><dt>이름이 바뀌는 서비스</dt><dd>2026년 7월 NotebookLM이 Gemini Notebook으로 이름을 바꿨습니다. 06차시에서 원자료 기반 질문에 사용합니다.</dd></div></dl><p><a href="https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-argon/" target="_blank" rel="noopener noreferrer">발표 원문에서 제공 계획 확인하기</a></p>',
    (2,7): '<dl class="definitions"><div><dt>편지쓰기</dt><dd>새 메일을 작성합니다.</dd></div><div><dt>받은편지함</dt><dd>받은 메일을 읽고 처리합니다. 기본·프로모션·소셜 탭도 살펴봅니다.</dd></div><div><dt>임시보관함</dt><dd>작성 중인 메일을 다시 엽니다.</dd></div><div><dt>검색·라벨</dt><dd>사람·제목·첨부로 검색하고 라벨별로 메일을 모아 봅니다.</dd></div></dl>',
    (2,28): '<dl class="definitions"><div><dt>새로 만들기</dt><dd>폴더·파일 업로드·새 Google 문서를 만듭니다.</dd></div><div><dt>내 드라이브</dt><dd>내가 만든 자료와 올린 자료를 정리합니다.</dd></div><div><dt>공유 문서함</dt><dd>다른 사람이 내 계정에 공유한 자료를 확인합니다.</dd></div><div><dt>최근·중요 문서함</dt><dd>최근 열었거나 별표한 파일을 모아 봅니다.</dd></div><div><dt>휴지통</dt><dd>지운 파일을 확인하고 복원합니다. 자동 삭제 기한을 확인합니다.</dd></div></dl>',
    (2,39): '<dl class="definitions"><div><dt>뷰어</dt><dd>자료를 열어 봅니다.</dd></div><div><dt>댓글 작성자</dt><dd>자료를 보고 의견을 남깁니다.</dd></div><div><dt>편집자</dt><dd>내용을 수정합니다. 재공유 허용 여부도 설정을 확인합니다.</dd></div><div><dt>제한됨</dt><dd>접근 권한을 준 사람만 열 수 있습니다.</dd></div><div><dt>링크가 있는 모든 사용자</dt><dd>링크를 받은 사람이 열 수 있습니다. 학생 정보나 내부 자료에는 사용하지 않습니다.</dd></div></dl>',
    (9,34): '<p><code>=COUNTIF(범위, "출석")</code>은 범위 안에서 출석이라고 입력한 칸을 셉니다.</p><dl class="definitions"><div><dt>학생별 출석 수</dt><dd><code>=COUNTIF(B2:D2,"출석")</code><p>한 학생의 날짜별 기록을 가로로 셉니다.</p></dd></div><div><dt>날짜별 출석 인원</dt><dd><code>=COUNTIF(B2:B4,"출석")</code><p>한 날짜의 학생 기록을 세로로 셉니다.</p></dd></div><div><dt>검산</dt><dd>출석·결석·지각·조퇴·미기록의 합계가 전체 칸 수와 같은지 대조합니다.</dd></div></dl>',
    (3,9): None,
}


def topic(slide, lid):
    nodes=slide['nodes']; num=slide['number']; sid=f'{lid:02}-{num:02}'
    title_node=next((n for n in nodes if n['type']=='text' and 850000<=n['y']<=950000),None)
    if not title_node:
        return None
    category_node=next((n for n in nodes if n['type']=='text' and 500000<n['y']<650000),None)
    category=shape_text(category_node) if category_node else ''
    title=shape_text(title_node).replace('\n',' ')
    if category in ['오늘의 수업','정리'] or (lid==1 and num in [2,6]) or (lid==10 and num==52):
        return None
    body=[n for n in nodes if n['y']>1600000]
    # Footer callouts are taken out of the drawing order and placed after the body.
    callouts=[n for n in body if n['type']=='text' and n['w']>9000000 and n['y']>=5600000]
    body=[n for n in body if n not in callouts]
    fulltext=' '.join(plain(n) for n in body+callouts)
    SEARCH.append({'title':title,'lesson':lid,'id':'topic-'+sid,'text':fulltext})
    COUNTS['topics']+=1
    if category=='참고':
        rendered=sources(body)
    elif (lid,num) in OVERRIDES and OVERRIDES[(lid,num)] is not None:
        rendered=OVERRIDES[(lid,num)]
        SEARCH[-1]['text']=re.sub(r'<[^>]+>', ' ', rendered)
    elif category=='1분 점검':
        questions=[n for n in body if n['type']=='text' and not re.fullmatch(r'[1-9]|O|X',shape_text(n))]
        answer=[n for n in callouts+questions if shape_text(n).startswith('정답')]
        questions=[n for n in questions if n not in answer]
        rendered='<ol class="questions">'+''.join('<li>'+paragraphs(n['text'])+'</li>' for n in questions)+'</ol>'
        rendered+='<details class="answers"><summary>정답과 해설</summary>'+''.join(paragraphs(n['text']) for n in answer)+'</details>'
        callouts=[n for n in callouts if n not in answer]
    else:
        rendered=prompt(body,sid)
        if rendered is None:
            rendered=procedure(body,exercise=(category=='실습'))
        if rendered is None:
            rendered=generic(body,title)
    if callouts:
        rendered+=''.join('<p class="key-note">'+inline(shape_text(n))+'</p>' for n in callouts)
    label='직접 해보기' if category=='실습' else ('생각해 보기' if category=='생각 열기' else '')
    klass='topic exercise' if category=='실습' else 'topic'
    return f'<section class="{klass}" id="topic-{sid}" data-title="{escape(title,quote=True)}">'+(f'<span class="topic-label">{label}</span>' if label else '')+f'<h4>{escape(title)}</h4>'+rendered+'</section>'


def lesson_html(meta,deck):
    lid=meta['id']; OUTLINES[str(lid)]=[]
    out=[f'<article id="lesson-{lid:02}" class="lesson" aria-labelledby="lesson-title-{lid:02}" data-lesson="{lid}">']
    out.append(f'<header class="lesson-header"><div class="lesson-index">{lid:02}</div><div><p class="eyebrow">{meta["day"]}일차 · {lid:02}차시</p><h2 id="lesson-title-{lid:02}">{escape(meta["title"])}</h2><p class="lesson-lead">{escape(meta["intro"])}</p></div></header>')
    out.append('<div class="lesson-brief"><div><h3>배울 내용</h3><ul>'+''.join('<li>'+escape(g)+'</li>' for g in meta['goals'])+'</ul></div><div><h3>이번 차시 결과물</h3><p>'+escape(meta['output'])+'</p><a class="text-link" href="#practice" data-workspace-lesson="'+str(lid)+'">내 프로그램으로 실습하기</a></div></div>')
    opened=False; section_index=0
    for slide in deck['slides']:
        nodes=slide['nodes']
        divider=next((n for n in nodes if n['type']=='text' and n['y']==3291840),None)
        is_divider=divider is not None and any(n['type']=='text' and re.fullmatch(r'\d{2}',shape_text(n)) and n['y']==1810512 for n in nodes)
        if is_divider:
            if opened:out.append('</div>')
            section_index+=1;title=shape_text(divider)
            # Reader titles name the subject directly.
            aliases={'업무 메일과 공문 초안':'업무 메일과 가정통신문','AI 영상 도구 알아보기':'AI 영상과 Google Vids'}
            title=aliases.get(title,title)
            aid=f'chapter-{lid:02}-{section_index:02}'
            OUTLINES[str(lid)].append({'id':aid,'title':title})
            out.append(f'<div class="chapter-section" id="{aid}"><div class="section-heading"><span>{section_index:02}</span><h3>{escape(title)}</h3></div>')
            bridge=meta.get('sections',{}).get(title)
            if bridge:out.append('<p class="section-lead">'+escape(bridge)+'</p>')
            opened=True
            continue
        if slide['number']==1 or slide['number']==deck['slide_count']:continue
        rendered=topic(slide,lid)
        if rendered:out.append(rendered)
    if opened:out.append('</div>')
    selected=[r for r in READINGS if lid in r['lessons']]
    if selected:
        out.append('<aside class="related-reading"><h3>함께 읽기</h3>'+''.join(f'<a href="#reading-{r["id"]}"><span>{escape(r["type"])} · {escape(r["publisher"])}</span>{escape(r["title"])}</a>' for r in selected[:3])+'</aside>')
    out.append(f'<div class="lesson-finish"><span>{escape(meta["output"])}</span><a href="'+(f'#lesson-{lid+1:02}' if lid<10 else '#practice')+'">'+('다음 차시 읽기' if lid<10 else '내 결과물 점검하기')+'</a></div></article>')
    return ''.join(out)


def nav_html():
    out=['<a class="overview-link" href="#manuscript">연수 시작</a>']
    for day,label in [(1,'업무 기반과 AI 시작'),(2,'수업자료와 통합 프로젝트')]:
        out.append(f'<p class="nav-group">{day}일차 <span>{label}</span></p><ol class="lesson-nav">')
        for m in COURSE['lessons']:
            if m['day']==day:out.append(f'<li><a href="#lesson-{m["id"]:02}" data-nav-lesson="{m["id"]}"><span>{m["id"]:02}</span><span>{escape(m["short"])}</span></a></li>')
        out.append('</ol>')
    out.append('<div class="sidebar-links"><a href="#practice">실습 도구</a><a href="#readings">읽을거리와 최신 동향</a><a href="#tools">도구 바로가기</a></div>')
    return ''.join(out)


def readings_html():
    out=['<section id="readings" class="extra-section"><div class="extra-heading"><p class="eyebrow">함께 읽기</p><h2>읽을거리와 최신 동향</h2><p>차시에서 다룬 개념을 실제 서비스 변화와 교육 활동에 연결해 봅니다.</p><p class="secondary">자료 확인: 2026.10.09 · 새 기능의 제공 계정·국가·언어·한도는 공식 안내를 확인합니다.</p></div><div class="reading-filters" role="group" aria-label="읽을거리 종류"><button class="filter-button is-active" data-reading-filter="all" aria-pressed="true">전체</button><button class="filter-button" data-reading-filter="최신 동향" aria-pressed="false">최신 동향</button><button class="filter-button" data-reading-filter="기사" aria-pressed="false">관련 기사</button><button class="filter-button" data-reading-filter="수업 원자료" aria-pressed="false">수업 원자료</button><button class="filter-button" data-reading-filter="도움말" aria-pressed="false">공식 도움말</button></div><div class="reading-list">']
    for r in READINGS:
        out.append(f'<article class="reading-card" id="reading-{r["id"]}" data-reading-type="{escape(r["type"],quote=True)}"><div class="reading-meta"><span>{escape(r["type"])}</span><span>{escape(r["publisher"])}</span><time>{escape(r["date"])}</time></div><h3>{escape(r["title"])}</h3><p>{escape(r["summary"])}</p><div class="reading-question"><span>생각해 볼 질문</span><p>{escape(r["question"])}</p></div><div class="reading-bottom"><div>'+''.join(f'<a href="#lesson-{lid:02}">{lid:02}차시</a>' for lid in r['lessons'])+f'</div><a href="{escape(r["url"],quote=True)}" target="_blank" rel="noopener noreferrer">원문 읽기</a></div></article>')
        SEARCH.append({'title':r['title'],'lesson':None,'id':'reading-'+r['id'],'text':r['summary']+' '+r['question']})
    out.append('</div></section>')
    return ''.join(out)


def main():
    chapters=''.join(lesson_html(meta,deck) for meta,deck in zip(COURSE['lessons'],DECKS))
    template=(ROOT/'scripts/template.html').read_text()
    reading_content = readings_html()
    inline_data=json.dumps({'search':SEARCH,'outlines':OUTLINES,'lessons':[{'id':m['id'],'title':m['title']} for m in COURSE['lessons']]},ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    html=template.replace('{{NAV}}',nav_html()).replace('{{LESSONS}}',chapters).replace('{{READINGS}}',reading_content).replace('{{DATA}}',inline_data)
    (ROOT/'index.html').write_text(html)
    print(json.dumps({**COUNTS,'lessons':len(DECKS),'source_slides':sum(d['slide_count'] for d in DECKS),'readings':len(READINGS),'bytes':len(html.encode())},ensure_ascii=False))


if __name__=='__main__':
    main()
