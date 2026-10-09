"use strict";

const data = JSON.parse(document.getElementById("course-data").textContent);
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
let toastTimer;

function announce(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 2400);
}

async function copyText(value) {
  if (navigator.clipboard && window.isSecureContext) {
    try { await navigator.clipboard.writeText(value); return true; } catch { /* selection fallback */ }
  }
  const field = document.createElement("textarea");
  field.value = value;
  field.style.position = "fixed";
  field.style.opacity = "0";
  document.body.append(field);
  field.select();
  const copied = document.execCommand("copy");
  field.remove();
  return copied;
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (button) {
    const value = document.getElementById(button.dataset.copy)?.textContent || "";
    const copied = await copyText(value);
    announce(copied ? "요청문을 복사했습니다." : "요청문을 선택해 직접 복사해 주세요.");
    button.focus();
  }
  const closeButton = event.target.closest("[data-close-dialog]");
  if (closeButton) document.getElementById(closeButton.dataset.closeDialog).close();
  const workspaceLink = event.target.closest("[data-workspace-lesson]");
  if (workspaceLink) {
    const mapping = {4:"intro",5:"mail",6:"lesson",7:"poster",8:"storyboard",9:"database",10:"package"};
    const kind = mapping[workspaceLink.dataset.workspaceLesson];
    if (kind) { $("#prompt-type").value = kind; updatePrompt(); }
  }
});

const menuDialog = $("#menu-dialog");
const searchDialog = $("#search-dialog");
$("#open-menu").addEventListener("click", () => menuDialog.showModal());
$("#open-search").addEventListener("click", () => {
  searchDialog.showModal();
  $("#course-search").focus();
});
menuDialog.addEventListener("click", event => {
  if (event.target.closest("a[href^='#']")) menuDialog.close();
});
for (const dialog of [menuDialog, searchDialog]) {
  dialog.addEventListener("click", event => {
    if (event.target === dialog) {
      const r = dialog.getBoundingClientRect();
      if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close();
    }
  });
}
document.addEventListener("keydown", event => {
  const editing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
  if (event.key === "/" && !editing && !menuDialog.open && !searchDialog.open) {
    event.preventDefault(); searchDialog.showModal(); $("#course-search").focus();
  }
});

const normalise = value => value.toLocaleLowerCase("ko").replace(/\s+/g, "");
const searchItems = data.search.map(item => ({...item, titleKey:normalise(item.title), textKey:normalise(item.text)}));
$("#course-search").addEventListener("input", event => {
  const query = event.target.value.trim();
  const results = $("#search-results");
  results.replaceChildren();
  if (!query) { $("#search-status").textContent = "제목과 원고 본문에서 검색합니다."; return; }
  const terms = query.toLowerCase().split(/\s+/).map(normalise).filter(Boolean);
  const matches = searchItems.filter(item => terms.every(term => item.titleKey.includes(term) || item.textKey.includes(term)))
    .map(item => ({...item,score:terms.reduce((score,term) => score + (item.titleKey.includes(term)?20:1),0)}))
    .sort((a,b) => b.score-a.score);
  $("#search-status").textContent = matches.length ? `${matches.length}곳에서 찾았습니다.${matches.length>25?" 앞의 25개 결과를 표시합니다.":""}` : "검색 결과가 없습니다. 단어를 짧게 바꿔 검색해 보세요.";
  for (const item of matches.slice(0,25)) {
    const li = document.createElement("li");
    const a = document.createElement("a"); a.href = "#"+item.id;
    const label = document.createElement("span"); label.textContent = item.lesson ? `${String(item.lesson).padStart(2,"0")}차시 · ${data.lessons[item.lesson-1].title}` : "읽을거리";
    const title = document.createElement("strong"); title.textContent = item.title;
    const snippet = document.createElement("p");
    const lower = item.text.toLocaleLowerCase("ko");
    const position = Math.max(0,lower.indexOf(terms[0]));
    const start = Math.max(0,position-28);
    snippet.textContent = (start?"…":"")+item.text.slice(start,start+115)+(item.text.length>start+115?"…":"");
    a.append(label,title,snippet);
    a.addEventListener("click", () => {
      searchDialog.close();
      if (item.id.startsWith("reading-")) setReadingFilter("all");
    });
    li.append(a); results.append(li);
  }
});

let activeLesson;
const lessonElements = $$("article.lesson");
function updateOutline() {
  const top = window.scrollY + 180;
  let current = null;
  for (const element of lessonElements) {
    if (element.offsetTop <= top && element.offsetTop + element.offsetHeight > top) current = Number(element.dataset.lesson);
  }
  if (current === activeLesson) return;
  activeLesson = current;
  $$("[data-nav-lesson]").forEach(link => {
    const selected = Number(link.dataset.navLesson) === current;
    link.classList.toggle("is-active",selected);
    if (selected) link.setAttribute("aria-current","location"); else link.removeAttribute("aria-current");
  });
  const outline = $("#section-outline"); outline.replaceChildren();
  for (const entry of data.outlines[String(current)] || []) {
    const a = document.createElement("a"); a.href="#"+entry.id; a.textContent=entry.title; outline.append(a);
  }
  $(".page-outline").hidden = !current;
}
let framePending = false;
window.addEventListener("scroll", () => {
  if (!framePending) {
    framePending=true;
    requestAnimationFrame(() => {updateOutline();framePending=false;});
  }
},{passive:true});
window.addEventListener("resize",updateOutline);
updateOutline();

function setReadingFilter(kind) {
  $$("[data-reading-filter]").forEach(button => {
    const selected = button.dataset.readingFilter === kind;
    button.classList.toggle("is-active",selected);
    button.setAttribute("aria-pressed",String(selected));
  });
  $$("[data-reading-type]").forEach(card => {card.hidden=kind!=="all"&&card.dataset.readingType!==kind;});
}
$$("[data-reading-filter]").forEach(button => button.addEventListener("click",()=>setReadingFilter(button.dataset.readingFilter)));
window.addEventListener("hashchange",()=>{
  if(location.hash.startsWith("#reading-")) {
    const item=document.getElementById(location.hash.slice(1));
    if(item?.hidden) {setReadingFilter("all");item.scrollIntoView();}
  }
});

const factForm=$("#fact-form");
const labels={program:"프로그램 이름",grade:"대상 학년",count:"인원",activity:"대표 활동",goal:"학습목표",materials:"준비물·수량",date:"일시",place:"장소",duration:"수업 시간",deadline:"회신 기한",contact:"문의·회신 방법",safety:"안전 약속"};
function factsText() {
  const values=new FormData(factForm);
  return Object.entries(labels).map(([key,label])=>`${label}: ${String(values.get(key)||"").trim() || "[미정]"}`).join("\n");
}
const promptSpecs={
  intro:"아래 기준정보만 사용해서 보호자에게 보낼 강사 자기소개문을 4문장, 존댓말로 써 줘.\n대표 활동과 참여 방법을 읽기 쉬운 표현으로 안내해. 없는 경력·자격·수상·성과는 추가하지 마.",
  mail:"아래 기준정보만 사용해서 학교 늘봄 담당 선생님께 보낼 준비물 협조 요청 메일을 써 줘.\n구성: 제목 1줄 + 본문 6문장 이내.\n본문에는 인사, 활동 목적, 요청 물품과 수량, 사용 일시, 회신 기한과 방법, 감사 인사를 담아. 정중한 존댓말로 써 줘.",
  notice:"아래 기준정보만 사용해서 보호자에게 보낼 가정통신문 문안을 써 줘.\n구성: 제목 / 인사 / 활동 목적 / 일시·장소·대상 / 준비물 / 안전 약속 / 문의.\n일시·장소·준비물은 목록으로, 전체 A4 반 쪽 이내로 써 줘.\n문서번호·결재·학교장 명의·발송 날짜는 만들지 말고 [학교 기재]로 비워 둬.",
  lesson:"너는 초등 늘봄학교 방과후 수업 설계를 돕는 도우미야.\n아래 기준정보로 1차시 수업안을 표로 써 줘.\n표 열: 단계(도입·전개·정리) / 시간 / 학생 활동 / 강사 질문 / 준비물.\n학습목표는 관찰 가능한 학생 행동으로 쓰고 활동과 평가를 연결해.\n비교 실험이면 한 가지 조건만 바꾸고 나머지는 같게 해.\n준비물은 기준정보에 있는 것만 사용해. 안전 주의를 넣고, 실험 결과 수치는 학생이 관찰해 기록하도록 비워 둬. 시간 합계는 기준정보의 수업 시간에 맞춰.",
  worksheet:"아래 기준정보로 대상 학년에 맞는 학생용 학습지 1쪽을 써 줘.\n구성: 제목 / 오늘의 질문 / 예측과 까닭 / 비교 조건 / 관찰 기록 표 / 설명(말·그림 선택) / 자기 점검 / 안전 약속.\n지시문 하나에 행동 하나를 담고, 쓰고 그릴 공간을 넉넉하게 남겨.\n관찰 결과와 수치는 비워 둬. 학생용과 강사용(예상 답·지도 팁)을 구분해서 만들어.",
  rubric:"아래 기준정보의 학습목표에 맞는 3단계 루브릭을 표로 만들어 줘.\n평가 요소 3개는 학습목표와 실제 활동에서 정해.\n수준: 스스로 수행 / 안내 후 수행 / 추가 지원.\n칸마다 강사가 볼 수 있는 학생 행동으로 써. '잘함·우수·노력 요함' 같은 표현은 쓰지 마.\n각 요소 아래에는 추가 지원이 필요한 학생을 위한 도움 방법을 1개씩 제안해.",
  poster:"아래 기준정보의 프로그램을 소개할 포스터 배경 그림을 만들어 줘.\n활동과 준비물이 드러나도록 사물은 아래쪽에 배치하고, 위쪽 1/3은 제목을 넣을 밝은 빈 여백으로 남겨.\n단순하고 밝은 일러스트, 세로 3:4 비율.\n글자·숫자·로고·실존 인물·학생 얼굴은 넣지 마. 날짜와 장소는 그림 안에 넣지 마.\n실험의 결과 수치를 그림으로 지어내지 마. 안내 글자는 내가 편집 도구에서 넣을게.",
  storyboard:"아래 기준정보로 보호자와 학생이 볼 30초 수업 안내 영상의 스토리보드를 표로 짜 줘.\n표 열: 장면 / 화면에 보일 것 / 자막 / 시간(초) / 소리 / 촬영 방식.\n장면은 4개 이하, 시간 합계 30초. 자막은 한 줄 15자 안팎으로 읽을 시간을 확보해.\n실제 활동 결과와 소리는 직접 촬영·녹음으로 표시해. AI로 만들 장면은 AI 클립으로 표시해.\n날짜·장소·준비물은 기준정보와 같게 쓰고, 마지막 장면에 AI 사용 표기를 넣어.",
  database:"아래 기준정보의 방과후 프로그램을 운영할 서류 관리 DB 구조를 제안해 줘.\n필수 속성: 서류명 / 종류 / 마감일 / 상태 / 파일 링크 / 버전 / 메모.\n상태는 시작 전·진행 중·완료로 하고, 완료는 제출·발송까지 끝난 상태로 정의해.\n표·상태별 보드·마감일 캘린더·미완료 보기를 같은 DB에서 구성하는 방법을 설명해.\n실제 기관의 서류나 마감일을 지어내지 말고 예시와 미정을 구분해. 학생 개인정보는 속성이나 예시 기록에 넣지 마.",
  package:"아래 기준정보로 동료 강사에게 보낼 프로그램 꾸러미 안내 글을 써 줘.\n구성: 프로그램 한 줄 소개 / 대상·일시·장소 / 자료를 보는 순서 / 자료마다 사용할 상황 / 검수할 항목.\n수업안·학습지·루브릭·포스터·안내 영상·업무 문서는 실제 만든 자료의 링크를 내가 넣을 수 있게 빈칸으로 남겨.\n아직 만들지 않은 자료를 완성했다고 쓰지 마. 대상·목표·준비물·일시·장소를 교차 검수할 표도 제안해."
};
function updatePrompt() {
  const kind=$("#prompt-type").value;
  $("#generated-prompt").textContent=promptSpecs[kind]+"\n\n[공통 조건]\n기준정보에 없는 날짜·수량·장소·이름·효과는 만들지 마. [미정]인 항목은 [확인 필요]로 표시하고, 작성에 꼭 필요한 정보가 부족하면 먼저 질문해.\n\n[기준정보]\n"+factsText();
}
factForm.addEventListener("input",updatePrompt);
factForm.addEventListener("submit",event=>event.preventDefault());
$("#prompt-type").addEventListener("change",updatePrompt);
$("#load-example").addEventListener("click",()=>{
  const example={program:"늘봄 과학교실",grade:"초등 3~4학년",count:"15명",activity:"종이 다리의 모양에 따른 버티는 힘 비교",goal:"종이 다리의 모양별 관찰 결과를 비교하고 까닭을 설명할 수 있다.",materials:"A4 용지 30장, 100원 동전 60개, 두꺼운 책 8권",date:"2026년 10월 20일(화)",place:"",duration:"40분",deadline:"2026년 10월 13일(화)",contact:"학교 늘봄 담당자에게 메일 회신",safety:"동전을 입에 넣지 않는다. 책을 높이 쌓지 않는다."};
  for(const [key,value] of Object.entries(example))factForm.elements.namedItem(key).value=value;
  updatePrompt();announce("종이 다리 예시를 채웠습니다. 실제 정보로 바꿔 사용하세요.");
});
$("#reset-facts").addEventListener("click",()=>{factForm.reset();updatePrompt();announce("입력을 지웠습니다.");});
function downloadText(filename,text) {
  const blob=new Blob(["\ufeff"+text],{type:"text/plain;charset=utf-8"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$("#download-facts").addEventListener("click",()=>downloadText("기준정보카드.txt",factsText()));
$("#download-prompt").addEventListener("click",()=>downloadText("내프로그램_요청문.txt",$("#generated-prompt").textContent));
updatePrompt();

const changes={
  date:[["가정통신문","일시·장소와 문의 안내"],["포스터","편집 가능한 날짜·장소 글상자"],["안내 영상","안내 장면 자막·내레이션과 MP4 재출력"],["협조 메일","사용 날짜와 회신 기한의 관계"],["서류 DB","관련 마감일과 메모"]],
  materials:[["수업안·학습지","준비물·수량·실험 조건·기록 단위"],["협조 메일","물품명·요청 수량·반납 계획"],["포스터·가정통신문","개인 준비물과 교실 제공 물품"],["안내 영상","재료 장면의 사진·자막·내레이션"],["업무 DB","구입·비치·반납 기록"]],
  grade:[["자기소개·가정통신문","대상 학년·인원과 참여 안내"],["수업안·학습지","낱말 수준·활동 시간·지원 방법"],["루브릭","목표에 맞는 관찰 행동과 추가 지원"],["포스터·영상","대상 학년 안내"],["준비물·출결부","모둠 수·필요 수량·기록 범위"]],
  goal:[["수업안","학생 활동과 강사 질문"],["학습지·확인 문항","예측·관찰·비교·설명의 연결"],["루브릭","평가 요소와 수준별 행동"],["포스터·안내 영상","활동 목적·프로그램 소개 문구"],["기준정보카드","새 목표·대표 활동·필요 재료"]]
};
function updateChanges(){
  const container=$("#change-result");container.replaceChildren();const list=document.createElement("ul");
  for(const [name,position] of changes[$("#change-kind").value]){const li=document.createElement("li");const strong=document.createElement("strong");strong.textContent=name;li.append(strong,document.createTextNode(position));list.append(li);}
  container.append(list);
}
$("#change-kind").addEventListener("change",updateChanges);updateChanges();
