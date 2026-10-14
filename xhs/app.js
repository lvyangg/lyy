/* =========================================================
   小红书图文流水线 · 网页版
   把选题变成可直接使用的 content.json（本地脚本直接吃这份文件）

   这一版新增的舒适感：
   - 生成结果可以直接改，改了再导出，不用重来
   - 标题/正文字数实时校验（对上小红书的上限）
   - 换一版：同选题再写一次
   - 历史记录：最近 5 份文案，随时翻回来
   - 草稿自动保存：选题写到一半关掉也不丢
   - 外观三选（明亮/深色/跟随系统），跟主站共用一份设置
   ========================================================= */

const PROVIDERS = {
  deepseek:  { label: 'DeepSeek', base: 'https://api.deepseek.com/v1', text: 'deepseek-chat' },
  dashscope: { label: '通义千问', base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', text: 'qwen-plus' },
  zhipu:     { label: '智谱 GLM', base: 'https://open.bigmodel.cn/api/paas/v4', text: 'glm-4-flash' },
  moonshot:  { label: 'Kimi', base: 'https://api.moonshot.cn/v1', text: 'moonshot-v1-8k' },
  ark:       { label: '火山方舟', base: 'https://ark.cn-beijing.volces.com/api/v3', text: '' },
  custom:    { label: '自定义', base: '', text: '' }
};

const LS_MAIN = 'chat_helper_v1';     // 与主站共用：API 设置 + 外观
const LS_TOOL = 'xhs_tool_v1';        // 本页自己的：草稿 + 历史
const HISTORY_MAX = 5;

const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));

let S = { settings: {}, theme: 'light', size: 'm' };
let TOOL = { draft: {}, history: [] };
let lastJson = null;
let busy = false;

/* ---------------- 设置读写 ---------------- */

function loadAll() {
  try {
    const a = JSON.parse(localStorage.getItem(LS_MAIN) || '{}') || {};
    S.settings = a.settings || {};
    S.theme = a.theme || 'light';
    S.size = a.size || 'm';
  } catch (e) { }
  try {
    const b = JSON.parse(localStorage.getItem(LS_TOOL) || '{}') || {};
    TOOL.draft = b.draft || {};
    TOOL.history = Array.isArray(b.history) ? b.history : [];
  } catch (e) { }
}

function mergeMain(patch) {
  try {
    const j = JSON.parse(localStorage.getItem(LS_MAIN) || '{}') || {};
    if (patch.settings) j.settings = Object.assign({}, j.settings, patch.settings);
    if (patch.theme) j.theme = patch.theme;
    if (patch.size) j.size = patch.size;
    localStorage.setItem(LS_MAIN, JSON.stringify(j));
  } catch (e) { }
}

function saveTool() {
  try { localStorage.setItem(LS_TOOL, JSON.stringify(TOOL)); } catch (e) { }
}

const prov = () => PROVIDERS[S.settings.provider] || PROVIDERS.custom;
const baseUrl = () => (S.settings.base || prov().base || '').replace(/\/+$/, '');
const textModel = () => S.settings.text || prov().text || '';
const apiKey = () => S.settings.key || '';

/* ---------------- 小工具 ---------------- */

function toast(msg, kind) {
  const d = document.createElement('div');
  d.className = 'toast' + (kind ? ' ' + kind : '');
  d.textContent = msg;
  $('#toasts').appendChild(d);
  setTimeout(() => {
    d.style.transition = '.25s'; d.style.opacity = '0'; d.style.transform = 'translateY(8px)';
    setTimeout(() => d.remove(), 260);
  }, kind === 'err' ? 4200 : 2000);
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); buzz(); toast('已复制', 'ok'); }
  catch (e) {
    const t = document.createElement('textarea');
    t.value = text; t.style.position = 'fixed'; t.style.opacity = '0';
    document.body.appendChild(t); t.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (_) { }
    t.remove();
    if (ok) buzz();
    toast(ok ? '已复制' : '复制失败，手动选中复制', ok ? 'ok' : 'err');
  }
}

function buzz() { try { if (navigator.vibrate) navigator.vibrate(12); } catch (e) { } }

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]
  ));
}

function stamp(ts) {
  const d = new Date(ts);
  const p = n => String(n).padStart(2, '0');
  return (d.getMonth() + 1) + '/' + d.getDate() + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
}

/* ---------------- 外观 ---------------- */

const THEME_NAME = { light: '明亮', dark: '深色', auto: '跟随系统' };
const SIZE_NAME = { s: '小', m: '标准', l: '大' };
const systemDark = () => window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;

function applyTheme() {
  const resolved = S.theme === 'auto' ? (systemDark() ? 'dark' : 'light') : S.theme;
  document.documentElement.dataset.theme = resolved;
  const meta = document.querySelector('meta[name=theme-color]');
  if (meta) meta.setAttribute('content', resolved === 'dark' ? '#0a0b11' : '#f8faff');
  $$('#segTheme button').forEach(b => b.classList.toggle('on', b.dataset.v === S.theme));
}

function applySize() {
  document.documentElement.dataset.size = S.size || 'm';
  $$('#segSize button').forEach(b => b.classList.toggle('on', b.dataset.v === S.size));
}

/* ---------------- 抽屉 ---------------- */

let opened = null;
function openSheet(sel) { $(sel).classList.add('open'); $('#scrim').classList.add('on'); opened = sel; }
function closeSheet() { if (opened) $(opened).classList.remove('open'); $('#scrim').classList.remove('on'); opened = null; }

function fillCfg() {
  const s = S.settings;
  $('#cfgProvider').value = s.provider || 'deepseek';
  $('#cfgKey').value = s.key || '';
  $('#cfgBase').value = s.base || prov().base || '';
  $('#cfgModel').value = s.text || prov().text || '';
  applyTheme(); applySize();
}

function refreshBadge() {
  const b = $('#badgeModel');
  const banner = $('#banner');
  const ok = !!(apiKey() && textModel());
  b.textContent = ok ? textModel() : '未配置';
  b.className = 'badge' + (ok ? ' ok' : '');
  if (banner) banner.style.display = ok ? 'none' : 'flex';
}

/* ---------------- 提示词 ---------------- */

const SCHEMA = `{
  "note": {
    "title": "标题，20 字以内",
    "alt_titles": ["备选标题一", "备选标题二"],
    "body": "正文，200-400 字，口语化、短段落、多换行，段之间用 \\n\\n 分隔",
    "tags": ["#标签1", "#标签2", "#标签3", "#标签4", "#标签5"]
  },
  "pages": [
    {"kind":"cover","eyebrow":"栏目，6 字内","title1":"封面第 1 行","title2":"封面第 2 行","title3":"封面第 3 行","sub":"副标题，20 字内","footer":"页脚，12 字内"},
    {"kind":"pain","eyebrow":"小标题，6 字内","title":"痛点第 1 行","title2":"痛点第 2 行","items":[["原因一，8 字内","解释，25 字内"],["原因二","解释"],["原因三","解释"]]},
    {"kind":"method","num":"一","eyebrow":"小标题","title":"方法名，6 字内","body":"说明，80-120 字","quote":"一句可以直接说出口的话，25 字内"},
    {"kind":"method","num":"二","eyebrow":"小标题","title":"方法名","body":"说明，80-120 字","quote":"一句话"},
    {"kind":"method","num":"三","eyebrow":"小标题","title":"方法名","body":"说明，80-120 字","quote":"一句话"},
    {"kind":"end","eyebrow":"小标题","title":"结尾第 1 行","title2":"结尾第 2 行","steps":[["第一步，6 字内","说明，25 字内"],["第二步","说明"]],"ask":"引导互动的一句话，20 字内"}
  ]
}`;

function buildMessages(topic, audience, tone, seed) {
  const sys = '你是小红书图文内容的作者。你写的笔记要像真人分享：一篇只讲一件事、口语化、短段落、' +
    '不用书面词、不做清单式榜单、不用绝对化用词、不承诺收入、不导流。';
  const user =
    '选题：' + topic + '\n' +
    (audience ? '写给谁看：' + audience + '\n' : '') +
    (tone ? '语气要求：' + tone + '\n' : '') +
    (seed ? '这是同一选题的第 ' + seed + ' 版，请换一个切入角度，不要和上一版重复。\n' : '') +
    '\n请按下面的结构输出，**只输出 JSON，不要代码块标记，不要任何解释**：\n' + SCHEMA +
    '\n\n硬性要求：\n' +
    '1. pages 必须正好 6 个，kind 顺序固定为 cover、pain、method、method、method、end\n' +
    '2. 所有字段都要有内容，不要留空，不要出现「示例」两个字\n' +
    '3. 封面三行字连起来要是一句完整的话，每行不超过 6 个字\n' +
    '4. 正文里的换行用 \\n，标签 5-6 个';
  return [
    { role: 'system', content: sys },
    { role: 'user', content: user }
  ];
}

/* ---------------- 调模型 ---------------- */

function friendly(code, body) {
  const t = String(body || '').slice(0, 160);
  if (code === 401 || code === 403) return 'Key 不对或没权限（' + code + '），点右上角齿轮检查一下。';
  if (code === 402) return '账户余额不足（402）。';
  if (code === 404) return '接口地址或模型名不对（404）。';
  if (code === 429) return '被限流了（429），缓一会儿再点。';
  if (code >= 500) return '对方服务器出问题了（' + code + '）。';
  return '请求失败（' + code + '）：' + t;
}

async function ask(messages) {
  const proxy = (S.settings.proxy || '').trim().replace(/\/+$/, '');
  const payload = { model: textModel(), messages: messages, temperature: 0.9, stream: false };
  let url, headers, body;
  if (proxy) {
    url = proxy + '/api/chat';
    headers = { 'Content-Type': 'application/json' };
    body = JSON.stringify({ target: baseUrl() + '/chat/completions', apiKey: apiKey(), payload: payload });
  } else {
    url = baseUrl() + '/chat/completions';
    headers = { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + apiKey() };
    body = JSON.stringify(payload);
  }
  let res;
  try { res = await fetch(url, { method: 'POST', headers: headers, body: body }); }
  catch (e) { throw new Error('连不上接口：检查网络，或换一家服务商试试。'); }
  if (!res.ok) {
    let t = '';
    try { t = await res.text(); } catch (e) { }
    throw new Error(friendly(res.status, t));
  }
  const j = await res.json();
  return (j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content) || '';
}

function parseJson(text) {
  let t = String(text || '').trim();
  t = t.replace(/^```(?:json)?/i, '').replace(/```$/, '').trim();
  const a = t.indexOf('{');
  const b = t.lastIndexOf('}');
  if (a > 0 || b < t.length - 1) t = t.slice(a, b + 1);
  const j = JSON.parse(t);
  if (!j.note || !Array.isArray(j.pages) || j.pages.length < 2) throw new Error('返回的内容不完整，点「换一版」再试一次。');
  return j;
}

/* ---------------- 路径读写（让结果可编辑） ---------------- */

function seg(p) { return /^\d+$/.test(p) ? Number(p) : p; }

function setPath(obj, path, val) {
  const parts = path.split('.');
  let o = obj;
  for (let i = 0; i < parts.length - 1; i++) o = o[seg(parts[i])];
  o[seg(parts[parts.length - 1])] = val;
}

function getPath(obj, path) {
  return path.split('.').reduce((o, k) => (o == null ? o : o[seg(k)]), obj);
}

const LAYOUT = {
  cover: [['title1', '第 1 行', 6], ['title2', '第 2 行', 6], ['title3', '第 3 行', 6],
          ['sub', '副标题', 24], ['footer', '页脚', 14]],
  pain:  [['title', '第 1 行', 10], ['title2', '第 2 行', 10],
          ['items', '三个原因（每行写：原因：解释）', 0, 'pa']],
  method: [['title', '方法名', 8], ['body', '这一页的说明', 130, 'ta'], ['quote', '那句可以说出口的话', 28]],
  end:   [['title', '第 1 行', 10], ['title2', '第 2 行', 10],
          ['steps', '两步（每行写：动作：说明）', 0, 'pa'], ['ask', '结尾引导', 22]]
};
const KIND_NAME = { cover: '封面', pain: '痛点页', method: '方法页', end: '结尾页' };

function pairsToText(arr) {
  return (arr || []).map(it => (it[0] || '') + '：' + (it[1] || '')).join('\n');
}

function textToPairs(txt) {
  return String(txt || '').split(/\r?\n/).map(l => l.trim()).filter(Boolean).map(l => {
    const m = l.match(/^([^：:]{1,20})[：:]\s*(.*)$/);
    return m ? [m[1].trim(), m[2].trim()] : [l, ''];
  });
}

/* ---------------- 渲染 ---------------- */

function counter(el, val, min, max) {
  const n = (val || '').length;
  const c = el.parentElement.querySelector('.cnt');
  if (!c) return;
  c.textContent = n + ' 字';
  if (max && n > max) { c.className = 'cnt bad'; }
  else if (min && n < min) { c.className = 'cnt'; }
  else { c.className = 'cnt ok'; }
}

function fieldHtml(path, label, value, hint, kind) {
  // 说明类和多行列表（每行一条）都用 textarea，单行 input 会把换行吃掉
  const isTa = kind === 'ta' || kind === 'pa';
  const v = esc(value == null ? '' : value);
  const attrs = 'data-p="' + path + '"' + (kind ? ' data-k="' + kind + '"' : '');
  const input = isTa
    ? '<textarea ' + attrs + '>' + v + '</textarea>'
    : '<input type="text" ' + attrs + ' value="' + v + '">';
  return '<div class="ed"><label>' + esc(label) + (hint && hint[0] ? '<span class="cnt">0 字</span>' : '') + '</label>' + input + '</div>';
}

function render(j) {
  lastJson = j;
  const n = j.note || {};
  let html = '';

  html += '<div class="sect">笔记正文<span class="ln"></span><span class="badge">发出去的就是这段</span></div>';
  html += '<div class="grp">';
  html += fieldHtml('note.title', '标题（小红书上限 20 字）', n.title, [1]);
  html += '<div class="ed"><label>备选标题<span class="cnt">0 字</span></label>' +
          '<input type="text" data-pl="note.alt_titles" value="' + esc((n.alt_titles || []).join(' / ')) + '">' +
          '<div class="hintbox">用 / 分隔多个备选</div></div>';
  html += fieldHtml('note.body', '正文', n.body, [1], 'ta');
  html += '<div class="ed"><label>标签<span class="cnt">0 个</span></label>' +
          '<input type="text" data-pl="note.tags" value="' + esc((n.tags || []).join(' ')) + '">' +
          '<div class="hintbox">空格分隔，5-6 个最好</div></div>';
  html += '</div>';

  html += '<div class="sect">六张卡片上印的字<span class="ln"></span><span class="badge">点标题可跳过</span></div>';
  (j.pages || []).forEach((p, i) => {
    html += '<div class="grp"><div class="hd"><span class="no">' + (i + 1) + '</span><span class="nm">' +
      esc(KIND_NAME[p.kind] || p.kind) + '</span>' +
      '<button class="btn btn-sm cp" data-copy="' + i + '">复制这页</button></div>';
    html += fieldHtml('pages.' + i + '.eyebrow', '小标题', p.eyebrow || '', null);
    (LAYOUT[p.kind] || []).forEach(([k, label, max, kind]) => {
      const raw = k === 'items' || k === 'steps' ? pairsToText(p[k]) : p[k];
      html += fieldHtml('pages.' + i + '.' + k, label, raw, [1], kind);
    });
    html += '</div>';
  });

  $('#outBody').innerHTML = html;
  $('#outCard').style.display = 'block';

  // 字数实时校验
  $$('#outBody [data-p]').forEach(el => {
    const path = el.dataset.p;
    const upd = () => {
      const max = path === 'note.title' ? 20 : 0;
      const min = path === 'note.body' ? 180 : 0;
      const bmax = path === 'note.body' ? 600 : max;
      counter(el, el.value, min, bmax);
    };
    el.addEventListener('input', upd);
    upd();
  });
  const tagEl = $('#outBody [data-pl="note.tags"]');
  if (tagEl) {
    const updTags = () => {
      const c = tagEl.parentElement.querySelector('.cnt');
      const list = tagEl.value.split(/[\s,，、]+/).filter(Boolean);
      c.textContent = list.length + ' 个';
      c.className = 'cnt' + (list.length >= 5 && list.length <= 6 ? ' ok' : '');
    };
    tagEl.addEventListener('input', updTags);
    updTags();
  }
  $$('#outBody [data-copy]').forEach(b => {
    b.onclick = () => copy(pagesText(j.pages[Number(b.dataset.copy)]));
  });

  $('#outMeta').textContent = (n.title || '').length + ' 字标题 · ' + (n.body || '').length + ' 字正文';
}

function pagesText(p) {
  if (!p) return '';
  if (p.kind === 'cover') return [p.eyebrow, [p.title1, p.title2, p.title3].filter(Boolean).join(''), p.sub, p.footer].filter(Boolean).join('\n');
  if (p.kind === 'pain') return [p.eyebrow, p.title + ' ' + (p.title2 || ''), pairsToText(p.items)].filter(Boolean).join('\n');
  if (p.kind === 'method') return [p.eyebrow, (p.num || '') + ' · ' + p.title, p.body, '「' + (p.quote || '') + '」'].filter(Boolean).join('\n');
  if (p.kind === 'end') return [p.eyebrow, p.title + ' ' + (p.title2 || ''), pairsToText(p.steps), p.ask].filter(Boolean).join('\n');
  return '';
}

/* ---------------- 收集编辑 + 导出 ---------------- */

function collect() {
  if (!lastJson) return null;
  $$('#outBody [data-p]').forEach(el => {
    const path = el.dataset.p;
    if (el.dataset.k === 'pa') setPath(lastJson, path, textToPairs(el.value));
    else setPath(lastJson, path, el.value.trim());
  });
  $$('#outBody [data-pl]').forEach(el => {
    const list = el.value.split(/[\s,，、/]+/).filter(Boolean);
    setPath(lastJson, el.dataset.pl, list);
  });
  return lastJson;
}

function fullJson() {
  const j = collect();
  return JSON.stringify(Object.assign({ style: 'hand' }, j), null, 2);
}

function download() {
  const blob = new Blob([fullJson()], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'content.json';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  toast('已下载 content.json，放进 xhs-auto/ 就能用', 'ok');
}

/* ---------------- 历史 ---------------- */

function pushHistory(j, topic) {
  TOOL.history.unshift({ t: Date.now(), topic: topic, data: JSON.parse(JSON.stringify(j)) });
  TOOL.history = TOOL.history.slice(0, HISTORY_MAX);
  saveTool();
  renderHistory();
}

function renderHistory() {
  const box = $('#histList');
  const card = $('#histCard');
  if (!box) return;
  if (!TOOL.history.length) { card.style.display = 'none'; return; }
  card.style.display = 'block';
  box.innerHTML = TOOL.history.map((h, i) =>
    '<div class="histline" data-i="' + i + '"><span class="tt">' +
    esc((h.data.note && h.data.note.title) || h.topic || '未命名') + '</span>' +
    '<span class="tm">' + stamp(h.t) + '</span></div>').join('');
  $$('#histList .histline').forEach(el => {
    el.onclick = () => {
      const h = TOOL.history[Number(el.dataset.i)];
      lastJson = JSON.parse(JSON.stringify(h.data));
      render(lastJson);
      $('#topic').value = h.topic || $('#topic').value;
      saveDraftSoon();
      toast('已载回来，可以接着改', 'ok');
    };
  });
}

/* ---------------- 草稿 ---------------- */

let draftTimer = null;
function saveDraftSoon() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    TOOL.draft = { topic: $('#topic').value, audience: $('#audience').value, tone: $('#tone').value };
    saveTool();
  }, 400);
}

function restoreDraft() {
  const d = TOOL.draft || {};
  if (d.topic) $('#topic').value = d.topic;
  if (d.audience) $('#audience').value = d.audience;
  if (d.tone) $('#tone').value = d.tone;
}

/* ---------------- 生成 ---------------- */

let version = 0;
let lastTopic = '';

async function generate(again) {
  if (busy) { toast('正在写，稍等'); return; }
  const topic = ($('#topic').value || '').trim();
  if (!topic) { toast('先写一个选题', 'err'); $('#topic').focus(); return; }
  if (!apiKey() || !textModel()) {
    toast('先点右上角齿轮填一个模型 Key', 'err');
    fillCfg(); openSheet('#sheetCfg');
    return;
  }
  if (again && topic !== lastTopic) version = 0;
  version = again ? version + 1 : 0;
  lastTopic = topic;

  busy = true;
  const b = $('#btnGen');
  b.disabled = true;
  b.innerHTML = '<span class="spin"></span> 正在写…';
  $('#genStatus').textContent = again ? '换个角度重写…' : '通常 5-15 秒';
  try {
    const txt = await ask(buildMessages(topic, $('#audience').value.trim(), $('#tone').value.trim(), version));
    const j = parseJson(txt);
    render(j);
    pushHistory(j, topic);
    $('#genStatus').textContent = '';
    toast('写好了，往下看，可以直接改', 'ok');
  } catch (e) {
    $('#genStatus').textContent = '';
    toast(e.message || '出错了', 'err');
  } finally {
    busy = false;
    b.disabled = false;
    b.innerHTML = '<svg class="i"><use href="#i-magic"/></svg>生成图文文案';
  }
}

/* ---------------- 绑定 ---------------- */

function bind() {
  $('#btnTheme').onclick = () => {
    const order = ['light', 'dark', 'auto'];
    S.theme = order[(order.indexOf(S.theme) + 1) % order.length];
    applyTheme(); mergeMain({ theme: S.theme });
    toast('外观：' + THEME_NAME[S.theme]);
  };
  $('#btnSize').onclick = () => {
    const order = ['s', 'm', 'l'];
    S.size = order[(order.indexOf(S.size) + 1) % order.length];
    applySize(); mergeMain({ size: S.size });
    toast('字号：' + SIZE_NAME[S.size]);
  };
  $('#btnCfg').onclick = () => { fillCfg(); openSheet('#sheetCfg'); };
  $$('[data-close]').forEach(el => { el.onclick = closeSheet; });
  $('#scrim').onclick = closeSheet;
  const goCfg = () => { fillCfg(); openSheet('#sheetCfg'); };
  if ($('#btnSetup')) $('#btnSetup').onclick = goCfg;

  const sel = $('#cfgProvider');
  sel.innerHTML = Object.keys(PROVIDERS).map(k =>
    '<option value="' + k + '">' + esc(PROVIDERS[k].label) + '</option>').join('');
  sel.onchange = () => {
    const p = PROVIDERS[sel.value];
    S.settings.provider = sel.value;
    $('#cfgBase').value = p.base;
    $('#cfgModel').value = p.text;
  };
  $('#cfgSave').onclick = () => {
    S.settings.provider = $('#cfgProvider').value;
    S.settings.key = $('#cfgKey').value.trim();
    S.settings.base = $('#cfgBase').value.trim();
    S.settings.text = $('#cfgModel').value.trim();
    mergeMain({ settings: S.settings });
    refreshBadge();
    closeSheet();
    toast('设置已保存', 'ok');
  };
  $$('#segTheme button').forEach(b => {
    b.onclick = () => { S.theme = b.dataset.v; applyTheme(); mergeMain({ theme: S.theme }); };
  });
  $$('#segSize button').forEach(b => {
    b.onclick = () => { S.size = b.dataset.v; applySize(); mergeMain({ size: S.size }); };
  });

  $('#btnGen').onclick = () => generate(false);
  $('#btnAgain2').onclick = () => generate(true);
  $('#btnSample').onclick = () => {
    $('#topic').value = '把 AI 当实习生带了一个月，我踩了 3 个坑';
    $('#audience').value = '刚工作一两年的年轻人';
    $('#tone').value = '像朋友分享，不端着';
    saveDraftSoon();
  };
  ['topic', 'audience', 'tone'].forEach(id => { $('#' + id).oninput = saveDraftSoon; });
  $('#topic').onkeydown = e => { if (e.key === 'Enter') generate(false); };

  $('#jumpTool').onclick = () => {
    $('#tool').scrollIntoView({ behavior: 'smooth', block: 'start' });
    setTimeout(() => $('#topic').focus(), 400);
  };
  $('#btnDl').onclick = () => { if (lastJson && collect()) download(); };
  $('#btnCopyJson').onclick = () => { if (lastJson && collect()) copy(fullJson()); };
  $('#btnCopyBody').onclick = () => {
    if (!lastJson) return;
    const n = collect().note || {};
    copy((n.body || '') + '\n\n' + (n.tags || []).join(' '));
  };
  $('#btnClearHist').onclick = () => {
    TOOL.history = []; saveTool(); renderHistory();
    toast('历史已清空', 'ok');
  };

  window.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeSheet(); return; }
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); generate(false); }
  });
  if (window.matchMedia) {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const on = () => { if (S.theme === 'auto') applyTheme(); };
    if (mq.addEventListener) mq.addEventListener('change', on);
    else if (mq.addListener) mq.addListener(on);
  }
}

/* ---------------- 启动 ---------------- */

(function init() {
  loadAll();
  applyTheme();
  applySize();
  bind();
  refreshBadge();
  restoreDraft();
  renderHistory();
})();
