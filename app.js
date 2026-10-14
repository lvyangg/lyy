/* =========================================================
   聊天参谋 · 网页版
   两条输入通道：粘贴文字 / 上传截图（视觉模型识别）
   三种输出档位：提示（只给方向）/ 参考 / 整句
   所有数据只存在本机浏览器里
   ========================================================= */

const PROVIDERS = {
  deepseek: {
    label: 'DeepSeek（便宜，但看不了图）',
    base: 'https://api.deepseek.com/v1',
    text: 'deepseek-chat',
    vision: '',
    note: 'DeepSeek 目前只有纯文字模型，截图那条路走不通，选它就只能粘贴文字。'
  },
  dashscope: {
    label: '通义千问（能看图）',
    base: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    text: 'qwen-plus',
    vision: 'qwen-vl-max',
    note: '阿里云百炼，文字和看图一个 key 全搞定。'
  },
  zhipu: {
    label: '智谱 GLM（能看图）',
    base: 'https://open.bigmodel.cn/api/paas/v4',
    text: 'glm-4-flash',
    vision: 'glm-4v-flash',
    note: '看图模型有免费额度，想省钱的可以先试这家。'
  },
  moonshot: {
    label: 'Kimi（能看图）',
    base: 'https://api.moonshot.cn/v1',
    text: 'moonshot-v1-8k',
    vision: 'moonshot-v1-8k-vision-preview',
    note: '长文本强，看图也可以。'
  },
  ark: {
    label: '火山方舟（能看图）',
    base: 'https://ark.cn-beijing.volces.com/api/v3',
    text: '',
    vision: '',
    note: '模型名要填你在方舟上创建的接入点 ID，不是模型名字。'
  },
  custom: {
    label: '自定义（任何兼容 OpenAI 格式的）',
    base: '',
    text: '',
    vision: '',
    note: '只要接口格式兼容 OpenAI，都能填。'
  }
};

const TPL = {
  friend: '好朋友，关系特别铁，什么都能聊，平时互相打趣',
  colleague: '同事，工作上有来往，关系还行但不算熟，说话要留分寸',
  like: '我喜欢的人，还在暧昧阶段，想往前走一点但又不想显得急',
  family: '家里人，是长辈，平时比较关心我'
};

const ACTIONS = {
  reply:    { label: '怎么回',   title: '接话建议' },
  topic:    { label: '聊什么',   title: '话题方向' },
  polish:   { label: '润色这句', title: '润色结果' },
  icebreak: { label: '冷场急救', title: '破冰招数' },
  meet:     { label: '约见面',   title: '约见面的话' },
  wrap:     { label: '好好收尾', title: '收尾的话' }
};

const MODE_TEXT = {
  hint: '提示档：只给方向和抓手，一个成品句都不给——话由你自己说。',
  ref:  '参考档：给你一句示范，你用自己习惯的说法改一遍再发。',
  full: '整句档：直接给你能发出去的话，想省事时用。'
};

const VISION_PROMPT = `这是微信聊天界面的截图。请把里面的对话按时间顺序转录成文字。
要求：
1. 每行一条消息，格式为「对方：内容」或「我：内容」；气泡靠左的算对方，靠右的算我
2. 只输出对话本身，不要解释、不要评论、不要标题
3. 看不清的字用 □ 代替，不要猜
4. 图片、语音、视频、红包、转账这类非文字消息，用【图片】【语音】这样标注
5. 时间单独一行，写成「时间：xxx」`;

const LS_KEY = 'chat_helper_v1';
const $  = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));

/* ---------------- 状态 ---------------- */

let S = {
  profiles: [{ who: '', rel: '', shared: '', goal: '', avoid: '' }],
  cur: 0,
  settings: {
    provider: 'deepseek', key: '', base: '', text: '',
    visionOn: false, vBase: '', vModel: '', vKey: '',
    proxy: '', tempClear: true
  },
  mode: 'hint',
  theme: 'light',        // light / dark / auto
  size: 'm',             // s / m / l
  draft: { chat: '', draft: '', temp: '' },
  history: []
};

let imgs = [];
let busy = false;
let lastRun = null;

function load() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return;
    const j = JSON.parse(raw);
    if (j && typeof j === 'object') {
      S.profiles = Array.isArray(j.profiles) && j.profiles.length
        ? j.profiles : S.profiles;
      S.cur = Number.isInteger(j.cur) ? j.cur : 0;
      S.mode = j.mode || S.mode;
      if (j.theme) S.theme = j.theme;
      if (j.size) S.size = j.size;
      if (j.draft && typeof j.draft === 'object') S.draft = Object.assign(S.draft, j.draft);
      S.history = Array.isArray(j.history) ? j.history : [];
      S.settings = Object.assign({}, S.settings, j.settings || {});
    }
  } catch (e) { }
  if (S.cur < 0 || S.cur >= S.profiles.length) S.cur = 0;
}

function save() {
  try { localStorage.setItem(LS_KEY, JSON.stringify(S)); } catch (e) { }
}

const P = () => S.profiles[S.cur] || S.profiles[0];
const prov = () => PROVIDERS[S.settings.provider] || PROVIDERS.custom;
const baseUrl = () => (S.settings.base || prov().base || '').replace(/\/+$/, '');
const textModel = () => S.settings.text || prov().text || '';
const visionModel = () => S.settings.vModel || prov().vision || '';
const visionBase = () => (S.settings.vBase || baseUrl()).replace(/\/+$/, '');
const visionKey = () => S.settings.vKey || S.settings.key;
const apiKey = () => S.settings.key;

/* ---------------- 小工具 ---------------- */

function toast(msg, kind) {
  const d = document.createElement('div');
  d.className = 'toast' + (kind ? ' ' + kind : '');
  d.textContent = msg;
  $('#toasts').appendChild(d);
  const life = kind === 'err' ? 4200 : 2000;
  setTimeout(() => {
    d.style.transition = '.25s';
    d.style.opacity = '0';
    d.style.transform = 'translateY(8px)';
    setTimeout(() => d.remove(), 260);
  }, life);
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    buzz();
    toast('已复制', 'ok');
  } catch (e) {
    const t = document.createElement('textarea');
    t.value = text;
    t.style.position = 'fixed';
    t.style.opacity = '0';
    document.body.appendChild(t);
    t.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (_) { }
    t.remove();
    if (ok) buzz();
    toast(ok ? '已复制' : '复制失败，长按文字手动复制', ok ? 'ok' : 'err');
  }
}

// 手机上的轻微震动反馈
function buzz() {
  try { if (navigator.vibrate) navigator.vibrate(12); } catch (e) { }
}

/* ---------------- 主题与字号 ---------------- */

const THEME_ORDER = ['light', 'dark', 'auto'];
const THEME_NAME = { light: '明亮', dark: '深色', auto: '跟随系统' };
const SIZE_ORDER = ['s', 'm', 'l'];
const SIZE_NAME = { s: '小', m: '标准', l: '大' };

function systemDark() {
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function applyTheme() {
  const resolved = S.theme === 'auto' ? (systemDark() ? 'dark' : 'light') : S.theme;
  document.documentElement.dataset.theme = resolved;
  const meta = document.querySelector('meta[name=theme-color]');
  if (meta) meta.setAttribute('content', resolved === 'dark' ? '#0a0b11' : '#f5f7fc');
}

function applySize() {
  document.documentElement.dataset.size = S.size || 'm';
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]
  ));
}

function initials(s) {
  const t = String(s || '').trim();
  return t ? t.slice(0, 1) : '·';
}

function hhmm(ts) {
  const d = new Date(ts);
  const p = n => String(n).padStart(2, '0');
  return (d.getMonth() + 1) + '/' + d.getDate() + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
}

/* ---------------- 提示词 ---------------- */

function sysPrompt() {
  const p = P();
  const temp = $('#temp').value.trim();
  const who = p.who || '对方';
  let r = '你是我本人的私人聊天参谋，帮我给「' + who + '」回消息。';
  r += '\n【关系定位】' + (p.rel || '（未填，按普通朋友处理）');
  if (p.shared) r += '\n【我们的共同爱好 / 常聊的事】' + p.shared;
  if (p.goal)   r += '\n【我长期想达到的效果】' + p.goal;
  if (p.avoid)  r += '\n【绝对不能碰的话题】' + p.avoid;
  if (temp)     r += '\n【这次聊天的临时目的（仅此一次）】' + temp;
  r += '\n【口吻铁律】\n' +
    '- 好朋友 / 哥们 / 闺蜜 / 老同学：彻底放松，短句、可以互怼、可以开玩笑、可以约事情，' +
    '绝对不要客套，不要出现「您」「感谢」「麻烦您」这种词\n' +
    '- 同事 / 客户 / 不太熟：得体但不生硬，别热络过头，别碰私人话题，别用网络梗\n' +
    '- 喜欢的人 / 暧昧对象：克制，不油腻，不夸张赞美，不连环追问，留一点余地\n' +
    '- 家人长辈：耐心、具体、有回应，不敷衍\n' +
    '以【关系定位】为准；没填就按普通朋友处理。';
  r += '\n【形式铁律】像真人随手打字：短、口语、不写小作文、不用书面词、不堆 emoji、不列点、不解释。';
  r += '\n【最重要的一条】这是辅助我聊天，不是替我聊天。别替我做决定，别说教，' +
       '别长篇分析人际关系，只在我卡住的地方递一个抓手。';
  r += '\n只输出要求的内容，不要问我「需不需要…」。';
  return r;
}

function buildPrompt(act) {
  const p = P();
  const who = p.who || '对方';
  const chat = $('#chat').value.trim();
  const draft = $('#draft').value.trim();
  const m = S.mode;

  if (act === 'polish') {
    if (!draft) return null;
    const u = '下面这句是我已经打好、准备发给' + who + '的话，请帮我改得更好：\n--------\n' +
      draft + '\n--------\n' +
      '请给 3 个版本，只输出 3 行，一行一个，意思保持不变，只调语气和措辞；' +
      '必须保留我原本的口吻，不要改成另一个人说的话；不要解释。';
    return [{ role: 'system', content: sysPrompt() }, { role: 'user', content: u }];
  }

  if (!chat) return null;
  const head = '下面是我和' + who + '最近的对话（可能来自截图识别，会有错字，自行忽略）：\n--------\n' +
    chat + '\n--------\n';
  let u = '';

  if (act === 'reply') {
    const spec = m === 'hint'
      ? '不要给我写好的句子，我要自己组织语言。请给我 3 个接话方向。\n' +
        '格式固定：方向名（4 字以内）｜我该抓住什么、往哪儿接（给我看的提示，不是发给他的话，25 字内）\n' +
        '只输出 3 行。'
      : m === 'full'
        ? '请给出 3 条我可以直接发出去的话，只输出 3 行，每行一条，不超过 30 字，' +
          '三条风格各不相同（顺接 / 带点情绪 / 往前一步）。'
        : '请给出 3 条参考说法（我会用自己的话再改），只输出 3 行，每行一条，不超过 30 字，' +
          '三条风格各不相同（顺接 / 带点情绪 / 往前一步）。';
    u = head + spec +
      '\n另外：一次只问一个问题，不要连着追问；对方在表达情绪时先接情绪，别急着给建议；' +
      '出现我们的共同爱好就优先往那上面接。';
  } else if (act === 'topic') {
    u = head + '请给我 3 个还能自然聊下去的话题方向。\n' +
      '1. 只输出 3 行，格式固定：话题方向｜一句可以直接发出去的开场话\n' +
      '2. 必须紧贴对方刚聊到的内容往外延展，不要凭空找话题\n' +
      '3. 优先从我们的共同爱好里找角度\n' +
      '4. 不要查户口式提问\n' +
      '5. 开场话不超过 25 字';
  } else if (act === 'icebreak') {
    u = head + '现在聊得有点冷了，给我 3 个能让气氛重新活过来的招。\n' +
      '1. 只输出 3 行，格式：招数名｜具体怎么做（30 字内，说清我要发什么）\n' +
      '2. 要轻，别用力过猛，别突然热情，不要说"你怎么不理我"这类话\n' +
      '3. 优先用我们共同爱好的梗，或者抛一个对方一定会接的具体问题';
  } else if (act === 'meet') {
    u = head + '我想约' + who + '见面。请给我 3 个邀约的说法，只输出 3 行。\n' +
      '1. 一行一句，不超过 30 字\n' +
      '2. 自然、给台阶、不施压，最好带一个具体的由头或场所\n' +
      '3. 不要写"你有空吗"这种把决定权全推给对方的空话';
  } else if (act === 'wrap') {
    u = head + '我想自然地结束这次聊天。请给我 3 个收尾的话，只输出 3 行。\n' +
      '1. 一行一句，不超过 25 字\n' +
      '2. 体面、留个好印象、给下次留个话头，不要显得敷衍或者想跑\n' +
      '3. 不要用"我去洗澡了"这种一眼假的借口';
  }
  return [{ role: 'system', content: sysPrompt() }, { role: 'user', content: u }];
}

/* ---------------- 网络 ---------------- */

function friendlyError(code, body) {
  const t = String(body || '').slice(0, 200);
  if (code === 401 || code === 403) return 'Key 不对或没有权限（' + code + '）。去设置里检查 API Key。';
  if (code === 402) return '账户余额不够了（402）。';
  if (code === 404) return '接口地址或模型名不对（404）。检查「接口地址」和模型名。';
  if (code === 429) return '被限流了（429），缓一会儿再点。';
  if (code >= 500) return '对方服务器出问题了（' + code + '），等会儿再试。';
  return '请求失败（' + code + '）：' + t;
}

async function post(path, payload, opts) {
  opts = opts || {};
  const proxy = (S.settings.proxy || '').trim().replace(/\/+$/, '');
  let url, headers, body;
  if (proxy) {
    url = proxy + '/api/chat';
    headers = { 'Content-Type': 'application/json' };
    body = JSON.stringify({
      target: (opts.base || baseUrl()) + path,
      apiKey: opts.key || apiKey(),
      payload: payload
    });
  } else {
    url = (opts.base || baseUrl()) + path;
    headers = { 'Content-Type': 'application/json' };
    const k = opts.key || apiKey();
    if (k) headers['Authorization'] = 'Bearer ' + k;
    body = JSON.stringify(payload);
  }
  const res = await fetch(url, { method: 'POST', headers: headers, body: body });
  if (!res.ok) {
    let t = '';
    try { t = await res.text(); } catch (e) { }
    throw new Error(friendlyError(res.status, t));
  }
  return res;
}

function netError() {
  return new Error('连不上接口。可能是网络问题，也可能是浏览器跨域被拦——' +
    '用附带的 server.js 起个本地代理，再把代理地址填进设置。');
}

async function callChat(messages, onDelta) {
  const payload = { model: textModel(), messages: messages, temperature: 1.0, stream: true };
  let res;
  try { res = await post('/chat/completions', payload); }
  catch (e) { if (e instanceof TypeError) throw netError(); throw e; }

  if (!res.body || !res.body.getReader) {
    const j = await res.json();
    const t = (j.choices && j.choices[0] && j.choices[0].message &&
      j.choices[0].message.content) || '';
    onDelta && onDelta(t);
    return t;
  }

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '', full = '';
  while (true) {
    const r = await reader.read();
    if (r.done) break;
    buf += dec.decode(r.value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (!line.startsWith('data:')) continue;
      const d = line.slice(5).trim();
      if (d === '[DONE]') return full;
      try {
        const j = JSON.parse(d);
        const delta = j.choices && j.choices[0] && j.choices[0].delta &&
          j.choices[0].delta.content;
        if (delta) { full += delta; onDelta && onDelta(full); }
      } catch (e) { }
    }
  }
  return full;
}

async function callVision(list) {
  if (!visionModel()) throw new Error('还没填看图模型。去设置里打开「截图输入」并填上模型名。');
  const content = [{ type: 'text', text: VISION_PROMPT }];
  list.forEach(d => content.push({ type: 'image_url', image_url: { url: d } }));
  const payload = {
    model: visionModel(),
    messages: [{ role: 'user', content: content }],
    temperature: 0.1,
    stream: false
  };
  let res;
  try { res = await post('/chat/completions', payload, { base: visionBase(), key: visionKey() }); }
  catch (e) { if (e instanceof TypeError) throw netError(); throw e; }
  const j = await res.json();
  return (j.choices && j.choices[0] && j.choices[0].message &&
    j.choices[0].message.content) || '';
}

/* ---------------- 图片 ---------------- */

function compress(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => {
      const img = new Image();
      img.onload = () => {
        const MAX = 1600;
        let w = img.width, h = img.height;
        if (Math.max(w, h) > MAX) {
          const k = MAX / Math.max(w, h);
          w = Math.round(w * k);
          h = Math.round(h * k);
        }
        const c = document.createElement('canvas');
        c.width = w;
        c.height = h;
        const ctx = c.getContext('2d');
        ctx.fillStyle = '#fff';
        ctx.fillRect(0, 0, w, h);
        ctx.drawImage(img, 0, 0, w, h);
        resolve(c.toDataURL('image/jpeg', 0.85));
      };
      img.onerror = () => reject(new Error('这张图读不出来'));
      img.src = fr.result;
    };
    fr.onerror = () => reject(new Error('文件读取失败'));
    fr.readAsDataURL(file);
  });
}

async function addFiles(files) {
  const list = Array.from(files).filter(f => /^image\//.test(f.type));
  if (!list.length) { toast('只支持图片文件', 'err'); return; }
  for (const f of list) {
    if (imgs.length >= 3) { toast('最多 3 张，够覆盖跨屏记录了'); break; }
    try { imgs.push(await compress(f)); }
    catch (e) { toast(e.message, 'err'); }
  }
  renderThumbs();
}

function renderThumbs() {
  const box = $('#thumbs');
  box.innerHTML = imgs.map((src, i) =>
    '<div class="thumb"><img src="' + src + '" alt=""><div class="x" data-i="' + i + '">✕</div></div>'
  ).join('');
  $('#btnOcr').disabled = imgs.length === 0;
  $$('#thumbs .x').forEach(el => {
    el.onclick = () => { imgs.splice(Number(el.dataset.i), 1); renderThumbs(); };
  });
}

/* ---------------- 渲染 ---------------- */

function renderProfiles() {
  const bar = $('#profBar');
  bar.innerHTML = S.profiles.map((p, i) => {
    const on = i === S.cur ? ' on' : '';
    const rel = (p.rel || '').trim();
    return '<div class="prof' + on + '" data-i="' + i + '">' +
      '<span class="av">' + esc(initials(p.who)) + '</span>' +
      '<span>' + esc(p.who || '未命名') + '</span>' +
      '<span class="tag">' + esc(rel ? rel.slice(0, 8) : '没写定位') + '</span>' +
      '</div>';
  }).join('') +
    '<div class="prof add" id="profEdit">✎ 定位</div>' +
    '<div class="prof add" id="profAdd">＋ 新对象</div>';

  $$('#profBar .prof[data-i]').forEach(el => {
    el.onclick = () => { S.cur = Number(el.dataset.i); save(); renderProfiles(); };
    el.ondblclick = () => {
      S.cur = Number(el.dataset.i); save(); renderProfiles(); fillProfile(); openSheet('#sheetProfile');
    };
  });
  $('#profEdit').onclick = () => { fillProfile(); openSheet('#sheetProfile'); };
  $('#profAdd').onclick = () => {
    S.profiles.push({ who: '', rel: '', shared: '', goal: '', avoid: '' });
    S.cur = S.profiles.length - 1;
    save(); renderProfiles(); fillProfile(); openSheet('#sheetProfile');
    toast('新建了一套空档案，先把称呼和定位填上');
  };
}

function renderHistory() {
  const card = $('#histCard');
  const box = $('#histList');
  if (!S.history.length) { card.style.display = 'none'; return; }
  card.style.display = 'block';
  box.innerHTML = S.history.map((h, hi) => {
    const items = h.items.map((t, ii) =>
      '<div class="li" data-h="' + hi + '" data-i="' + ii + '">' + esc(t) + '</div>').join('');
    const modeName = h.mode === 'hint' ? '提示' : h.mode === 'ref' ? '参考' : '整句';
    const actName = (ACTIONS[h.act] && ACTIONS[h.act].label) || h.act;
    return '<div class="hist">' +
      '<div class="hd"><span class="who">' + esc(h.who) + ' · ' + esc(actName) + '</span>' +
      '<span class="badge">' + modeName + '</span>' +
      '<span class="tm">' + hhmm(h.t) + '</span></div>' +
      '<div class="bd">' + items + '</div></div>';
  }).join('');
  $$('#histList .hist .hd').forEach(el => {
    el.onclick = () => el.parentElement.classList.toggle('open');
  });
  $$('#histList .li').forEach(el => {
    el.onclick = () => {
      const h = S.history[Number(el.dataset.h)];
      if (h) copy(h.items[Number(el.dataset.i)]);
    };
  });
}

function renderResults(items, act) {
  const box = $('#results');
  box.innerHTML = items.map((t, i) => {
    const cut = t.indexOf('｜');
    const body = (S.mode === 'hint' && cut > 0)
      ? '<b>' + esc(t.slice(0, cut)) + '</b>　' + esc(t.slice(cut + 1))
      : esc(t);
    return '<div class="res" data-i="' + i + '" role="button" tabindex="0" aria-label="复制这条建议">' +
      '<div class="idx">' + (i + 1) + '</div>' +
      '<div class="tx">' + body + '</div>' +
      '<button class="btn btn-sm cp" aria-hidden="true" tabindex="-1">' +
      '<svg class="i"><use href="#i-copy"/></svg></button></div>';
  }).join('');
  $$('#results .res').forEach(el => {
    const text = items[Number(el.dataset.i)];
    el.onclick = () => copy(text);
    el.onkeydown = ev => {
      if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); copy(text); }
    };
  });
  $('#resTitle').textContent = ACTIONS[act].title;
  $('#resultWrap').style.display = 'block';
  $('#resActions').style.display = 'flex';
  $('#resMeta').textContent = ACTIONS[act].label + ' · ' +
    (S.mode === 'hint' ? '提示档' : S.mode === 'ref' ? '参考档' : '整句档') +
    ' · ' + items.join('').length + ' 字';
}

/* ---------------- 抽屉 ---------------- */

let openedSheet = null;

function openSheet(sel) {
  closeSheet();
  openedSheet = sel;
  $(sel).classList.add('open');
  $('#scrim').classList.add('on');
}

function closeSheet() {
  if (openedSheet) $(openedSheet).classList.remove('open');
  openedSheet = null;
  $('#scrim').classList.remove('on');
}

/* ---------------- 生成 ---------------- */

function parseItems(text) {
  if (!text) return [];
  return text.split(/\r?\n/)
    .map(l => l.replace(/^\s*(?:[-*•]|\d+\s*[.、)）])\s*/, '').trim())
    .filter(l => l && !/^(以下是|好的[，,]|当然[，,]?$|上面就是)/.test(l))
    .slice(0, 3);
}

function pushHistory(act, items) {
  S.history.unshift({
    t: Date.now(),
    act: act,
    mode: S.mode,
    who: P().who || '未命名',
    items: items
  });
  S.history = S.history.slice(0, 20);
  save();
  renderHistory();
}

async function run(act) {
  if (busy) { toast('正在生成，稍等'); return; }

  const msgs = buildPrompt(act);
  if (!msgs) {
    if (act === 'polish') {
      toast('先在「我要说的话」里写一句', 'err');
      $('#draft').focus();
    } else {
      toast('先把聊天内容填进来：粘贴文字，或者切到截图让它读', 'err');
    }
    return;
  }
  if (!apiKey()) { toast('先填 API Key', 'err'); fillSettings(); openSheet('#sheetSettings'); return; }
  if (!textModel()) { toast('先填文字模型名', 'err'); fillSettings(); openSheet('#sheetSettings'); return; }

  busy = true;
  $$('.act').forEach(b => { b.disabled = true; });
  $('#resTitle').textContent = ACTIONS[act].title;
  $('#resultWrap').style.display = 'block';
  $('#resActions').style.display = 'none';
  $('#results').innerHTML = '<div class="skel"><i></i><i></i><i></i></div>';
  let streamEl = null;
  $('#resultWrap').scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  try {
    const full = await callChat(msgs, txt => {
      if (!streamEl) {
        $('#results').innerHTML = '<div class="streaming" id="stream"></div>';
        streamEl = $('#stream');
      }
      streamEl.innerHTML = esc(txt) + '<span class="cursor"></span>';
    });
    const items = parseItems(full);
    if (!items.length) {
      $('#results').innerHTML = '<div class="empty"><span class="ei">' +
        '<svg class="i"><use href="#i-spark"/></svg></span>没拿到有效结果，再点一次试试</div>';
      return;
    }
    renderResults(items, act);
    lastRun = { act: act, items: items };
    if (S.settings.tempClear) $('#temp').value = '';
    pushHistory(act, items);
  } catch (e) {
    $('#results').innerHTML = '<div class="empty" style="color:var(--err)">' +
      esc(e && e.message ? e.message : '出错了') + '</div>';
  } finally {
    busy = false;
    $$('.act').forEach(b => { b.disabled = false; });
  }
}

/* ---------------- 界面切换 ---------------- */

function switchSrc(which) {
  $$('#segSrc button').forEach(b => b.classList.toggle('on', b.dataset.src === which));
  $('#paneText').style.display = which === 'text' ? 'block' : 'none';
  $('#paneShot').style.display = which === 'shot' ? 'block' : 'none';
  $('#srcBadge').textContent = which === 'text' ? '文字' : '截图';
  $('#srcBadge').className = 'badge' + (which === 'shot' ? ' ok' : '');
  moveGlider('#segSrc');
}

function switchMode(m) {
  S.mode = m;
  save();
  $$('#segMode button').forEach(b => b.classList.toggle('on', b.dataset.mode === m));
  $('#modeBadge').textContent = m === 'hint' ? '提示' : m === 'ref' ? '参考' : '整句';
  $('#modeHint').textContent = MODE_TEXT[m];
  moveGlider('#segMode');
}

// 分段控件里那个会滑动的指示器
function moveGlider(sel) {
  const seg = $(sel);
  if (!seg) return;
  const on = seg.querySelector('button.on');
  const gl = seg.querySelector('.glider');
  if (!on || !gl || !on.offsetWidth) return;
  gl.style.width = on.offsetWidth + 'px';
  gl.style.transform = 'translateX(' + (on.offsetLeft - 4) + 'px)';
}

function refreshBanner() {
  const b = $('#banner');
  if (!b) return;
  b.style.display = apiKey() ? 'none' : 'flex';
}

function relayout() {
  moveGlider('#segSrc');
  moveGlider('#segMode');
  moveGlider('#segTempClear');
}

function fillProfile() {
  const p = P();
  $('#pfTitle').textContent = '对象定位 · ' + (p.who || '未命名');
  $('#pfWho').value = p.who || '';
  $('#pfRel').value = p.rel || '';
  $('#pfShared').value = p.shared || '';
  $('#pfGoal').value = p.goal || '';
  $('#pfAvoid').value = p.avoid || '';
}

function fillSettings() {
  const s = S.settings;
  const p = PROVIDERS[s.provider] || PROVIDERS.custom;
  $('#stProvider').value = s.provider;
  $('#providerHint').textContent = p.note || '';
  $('#stKey').value = s.key || '';
  $('#stBase').value = s.base || p.base || '';
  $('#stText').value = s.text || p.text || '';
  $('#stVBase').value = s.vBase || '';
  $('#stVModel').value = s.vModel || p.vision || '';
  $('#stVKey').value = s.vKey || '';
  $('#stProxy').value = s.proxy || '';
  $('#swVision').classList.toggle('on', !!s.visionOn);
  $('#visionBox').style.display = s.visionOn ? 'block' : 'none';
  $$('#segTempClear button').forEach(b => {
    b.classList.toggle('on', (b.dataset.v === '1') === !!s.tempClear);
  });
  // 抽屉刚打开时按钮还没排好版，稍等一下再摆指示器
  setTimeout(() => {
    moveGlider('#segSrc');
    moveGlider('#segMode');
    moveGlider('#segTempClear');
  }, 60);
}

/* ---------------- 草稿自动保存 ---------------- */

function restoreDraft() {
  const d = S.draft || {};
  if (d.chat) {
    $('#chat').value = d.chat;
    $('#cnt').textContent = d.chat.length + ' 字';
  }
  if (d.draft) $('#draft').value = d.draft;
  if (d.temp) $('#temp').value = d.temp;
}

let draftTimer = null;
function saveDraftSoon() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    S.draft = { chat: $('#chat').value, draft: $('#draft').value, temp: $('#temp').value };
    save();
  }, 400);
}

/* ---------------- 整理格式 ---------------- */

function tidyChat(raw) {
  const lines = String(raw || '').split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  const out = [];
  for (const l of lines) {
    if (/^(\d{1,4}[-/年]\d{1,2}[-/月]\d{1,2}(\s+\d{1,2}:\d{2})?|\d{1,2}:\d{2})$/.test(l)) {
      out.push('时间：' + l);
      continue;
    }
    const m = l.match(/^(\[[^\]]{1,16}\]|[^：:]{1,12})[：:]\s*(.+)$/);
    if (m) {
      out.push(m[1].trim() + '：' + m[2].trim());
    } else if (out.length && !/^时间：/.test(out[out.length - 1])) {
      out[out.length - 1] += ' ' + l;      // 换行续写，接到上一条
    } else {
      out.push(l);                          // 判断不出说话人，原样保留，不硬贴标签
    }
  }
  return out.join('\n');
}

/* ---------------- 事件绑定 ---------------- */

function bind() {
  $('#btnTheme').onclick = () => {
    const i = THEME_ORDER.indexOf(S.theme);
    S.theme = THEME_ORDER[(i + 1) % THEME_ORDER.length];
    save();
    applyTheme();
    toast('外观：' + THEME_NAME[S.theme]);
  };
  $('#btnSize').onclick = () => {
    const i = SIZE_ORDER.indexOf(S.size);
    S.size = SIZE_ORDER[(i + 1) % SIZE_ORDER.length];
    save();
    applySize();
    relayout();
    toast('字号：' + SIZE_NAME[S.size]);
  };
  $('#btnSettings').onclick = () => { fillSettings(); openSheet('#sheetSettings'); };
  $('#btnSetup').onclick = () => { fillSettings(); openSheet('#sheetSettings'); };
  $$('[data-close]').forEach(el => { el.onclick = closeSheet; });
  $('#scrim').onclick = closeSheet;

  $$('#segSrc button').forEach(b => { b.onclick = () => switchSrc(b.dataset.src); });
  $$('#segMode button').forEach(b => { b.onclick = () => switchMode(b.dataset.mode); });

  $('#chat').oninput = () => {
    $('#cnt').textContent = $('#chat').value.length + ' 字';
    saveDraftSoon();
  };
  $('#draft').oninput = saveDraftSoon;
  $('#temp').oninput = saveDraftSoon;
  $('#btnTidy').onclick = () => {
    const raw = $('#chat').value;
    if (!raw.trim()) { toast('先粘贴一段聊天记录'); return; }
    const tidied = tidyChat(raw);
    if (tidied === raw.trim()) { toast('已经是整齐的了'); return; }
    $('#chat').value = tidied;
    $('#cnt').textContent = tidied.length + ' 字';
    saveDraftSoon();
    toast('已整理成一行一条','ok');
  };
  $('#btnClear').onclick = () => {
    $('#chat').value = '';
    $('#cnt').textContent = '0 字';
  };
  $('#btnDemo').onclick = () => {
    $('#chat').value = '对方：今天加班到九点，累死了\n我：又是你那个项目？\n' +
      '对方：这次是临时改需求，烦\n对方：而且明天还要早起开会';
    $('#cnt').textContent = $('#chat').value.length + ' 字';
    saveDraftSoon();
  };
  $('#btnPaste').onclick = async () => {
    try {
      const t = await navigator.clipboard.readText();
      if (!t) { toast('剪贴板是空的'); return; }
      $('#chat').value = $('#chat').value ? $('#chat').value + '\n' + t : t;
      $('#cnt').textContent = $('#chat').value.length + ' 字';
      switchSrc('text');
      toast('已读入剪贴板内容', 'ok');
    } catch (e) {
      toast('浏览器不让读剪贴板，手动长按粘贴吧', 'err');
    }
  };

  const drop = $('#drop');
  drop.onclick = () => $('#file').click();
  $('#file').onchange = e => { addFiles(e.target.files); e.target.value = ''; };
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => {
    e.preventDefault();
    drop.classList.add('over');
  }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => {
    e.preventDefault();
    drop.classList.remove('over');
  }));
  drop.addEventListener('drop', e => {
    if (e.dataTransfer && e.dataTransfer.files) addFiles(e.dataTransfer.files);
  });
  window.addEventListener('paste', e => {
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    const files = [];
    for (const it of items) {
      if (it.kind === 'file' && /^image\//.test(it.type)) files.push(it.getAsFile());
    }
    if (files.length) { switchSrc('shot'); addFiles(files); }
  });

  $('#btnOcr').onclick = async () => {
    if (!imgs.length) { toast('先选截图', 'err'); return; }
    if (!visionModel()) {
      toast('先去设置里打开「截图输入」并填看图模型', 'err');
      fillSettings();
      openSheet('#sheetSettings');
      return;
    }
    const b = $('#btnOcr');
    b.disabled = true;
    b.innerHTML = '<span class="spin"></span> 识别中…';
    try {
      const txt = await callVision(imgs);
      $('#ocrOut').value = txt.trim();
      toast('识别完成，核对一下错字再用', 'ok');
    } catch (e) {
      toast(e.message, 'err');
    } finally {
      b.disabled = false;
      b.textContent = '识别成文字';
    }
  };
  $('#btnUseOcr').onclick = () => {
    const t = $('#ocrOut').value.trim();
    if (!t) { toast('还没有识别结果', 'err'); return; }
    $('#chat').value = t;
    $('#cnt').textContent = t.length + ' 字';
    switchSrc('text');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    toast('已设为对话内容，可以点动作按钮了', 'ok');
  };

  $$('.act').forEach(b => { b.onclick = () => run(b.dataset.act); });
  $('#btnAgain').onclick = () => { if (lastRun) run(lastRun.act); };
  $('#btnCopyAll').onclick = () => {
    if (lastRun) copy(lastRun.items.join('\n'));
  };
  $('#btnClearHist').onclick = () => {
    S.history = [];
    save();
    renderHistory();
    toast('历史已清空', 'ok');
  };

  $('#pfSave').onclick = () => {
    const p = P();
    p.who = $('#pfWho').value.trim();
    p.rel = $('#pfRel').value.trim();
    p.shared = $('#pfShared').value.trim();
    p.goal = $('#pfGoal').value.trim();
    p.avoid = $('#pfAvoid').value.trim();
    save();
    renderProfiles();
    closeSheet();
    toast('定位已保存 · ' + (p.who || '未命名'), 'ok');
  };
  $('#pfNew').onclick = () => {
    S.profiles.push({ who: '', rel: '', shared: '', goal: '', avoid: '' });
    S.cur = S.profiles.length - 1;
    save(); renderProfiles(); fillProfile();
    toast('新建了一套空档案');
  };
  $('#pfDel').onclick = () => {
    if (S.profiles.length <= 1) { toast('至少要留一个对象', 'err'); return; }
    const n = P().who || '未命名';
    S.profiles.splice(S.cur, 1);
    if (S.cur >= S.profiles.length) S.cur = S.profiles.length - 1;
    save(); renderProfiles(); fillProfile();
    toast('已删除：' + n);
  };
  $$('[data-tpl]').forEach(b => {
    b.onclick = () => {
      const cur = $('#pfRel').value.trim();
      const t = TPL[b.dataset.tpl];
      $('#pfRel').value = cur ? cur + '；' + t : t;
      toast('已套用模板，接着改');
    };
  });

  const sel = $('#stProvider');
  sel.innerHTML = Object.keys(PROVIDERS).map(k =>
    '<option value="' + k + '">' + esc(PROVIDERS[k].label) + '</option>').join('');
  sel.onchange = () => {
    S.settings.provider = sel.value;
    const p = PROVIDERS[sel.value];
    $('#stBase').value = p.base;
    $('#stText').value = p.text;
    $('#stVBase').value = '';
    $('#stVModel').value = p.vision;
    $('#providerHint').textContent = p.note || '';
    if (!p.vision) toast('这家看不了图，只能走粘贴文字', 'err');
  };
  $('#swVision').onclick = () => {
    S.settings.visionOn = !S.settings.visionOn;
    $('#swVision').classList.toggle('on', S.settings.visionOn);
    $('#visionBox').style.display = S.settings.visionOn ? 'block' : 'none';
  };
  $('#stSave').onclick = () => {
    S.settings.key = $('#stKey').value.trim();
    S.settings.base = $('#stBase').value.trim();
    S.settings.text = $('#stText').value.trim();
    S.settings.vBase = $('#stVBase').value.trim();
    S.settings.vModel = $('#stVModel').value.trim();
    S.settings.vKey = $('#stVKey').value.trim();
    S.settings.proxy = $('#stProxy').value.trim();
    save();
    closeSheet();
    refreshBanner();
    toast('设置已保存', 'ok');
  };
  $('#stTest').onclick = async () => {
    const b = $('#stTest');
    b.disabled = true;
    b.innerHTML = '<span class="spin"></span> 测试中…';
    try {
      await callChat([{ role: 'user', content: '只回复两个字：可以' }], () => { });
      toast('通了，可以用了', 'ok');
    } catch (e) {
      toast(e.message, 'err');
    } finally {
      b.disabled = false;
      b.textContent = '测试连接';
    }
  };
  $$('#segTempClear button').forEach(b => {
    b.onclick = () => {
      S.settings.tempClear = b.dataset.v === '1';
      $$('#segTempClear button').forEach(x => x.classList.toggle('on', x === b));
      moveGlider('#segTempClear');
      save();
    };
  });

  // 键盘快捷键（电脑上用）
  window.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeSheet(); return; }
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      run(lastRun ? lastRun.act : 'reply');
      return;
    }
    const tag = (e.target && e.target.tagName ? e.target.tagName : '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    if (e.key === '1' || e.key === '2' || e.key === '3') {
      if (!lastRun) return;
      const t = lastRun.items[Number(e.key) - 1];
      if (t) copy(t);
    }
  });
}

/* ---------------- 启动 ---------------- */

(function init() {
  load();
  applyTheme();
  applySize();
  renderProfiles();
  renderHistory();
  renderThumbs();
  bind();
  switchMode(S.mode || 'hint');
  switchSrc('text');
  refreshBanner();
  restoreDraft();

  window.addEventListener('load', relayout);
  window.addEventListener('resize', relayout);
  setTimeout(relayout, 120);

  // 跟随系统时，系统切换深浅色要跟着变
  if (window.matchMedia) {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => { if (S.theme === 'auto') applyTheme(); };
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else if (mq.addListener) mq.addListener(onChange);
  }

  // 在线地址（https）下注册离线缓存，手机可以"添加到主屏幕"当 App 用
  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
    navigator.serviceWorker.register('sw.js').catch(() => { });
  }
})();
