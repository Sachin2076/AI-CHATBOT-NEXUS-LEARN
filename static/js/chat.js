/* ── chat.js — Nexus Learn Chat with Session History ── */

const msgsEl   = document.getElementById('msgs');
const emptyEl  = document.getElementById('chat-empty');
const inputEl  = document.getElementById('chat-input');
const sendBtn  = document.getElementById('send-btn');
const statusEl = document.getElementById('llm-status');
const dotEl    = document.getElementById('status-dot');
const titleEl  = document.getElementById('chat-title');
const sessionListEl = document.getElementById('session-list');

let currentSessionId = null;
let pendingPlan = null;
let allSessions = [];

/* ══════════════════════════════════════
   HELPERS
══════════════════════════════════════ */
function fmtTime(iso){
  const d = iso ? new Date(iso) : new Date();
  return d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
}
function fmtDate(iso){
  if(!iso) return '';
  const d = new Date(iso);
  const today = new Date();
  if(d.toDateString()===today.toDateString()) return 'Today';
  const yest = new Date();
  yest.setDate(yest.getDate()-1);
  if(d.toDateString()===yest.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([],{month:'short',day:'numeric'});
}
function escH(s){
  return String(s)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}
function fmtMD(text){
  let h = text;
  // Convert HTML tags to readable text before stripping
  h = h.replace(/<strong>(.*?)<\/strong>/gi,'**$1**');
  h = h.replace(/<em>(.*?)<\/em>/gi,'_$1_');
  h = h.replace(/<br\s*\/?>/gi,'\n');
  h = h.replace(/<li>(.*?)<\/li>/gi,'• $1\n');
  h = h.replace(/<\/p>/gi,'\n');
  h = h.replace(/<\/div>/gi,'\n');
  h = h.replace(/<\/h[1-6]>/gi,'\n');
  // Strip all remaining HTML tags
  h = h.replace(/<[^>]+>/g,'');
  // Decode HTML entities
  h = h.replace(/&lt;/g,'<')
       .replace(/&gt;/g,'>')
       .replace(/&amp;/g,'&')
       .replace(/&quot;/g,'"')
       .replace(/&#039;/g,"'");
  // Apply markdown formatting
  h = h.replace(/```(\w*)\n?([\s\S]*?)```/g,
    (_,lang,code)=>`<pre><code>${escH(code.trim())}</code></pre>`);
  h = h.replace(/`([^`\n]+)`/g,(_,c)=>`<code>${escH(c)}</code>`);
  h = h.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>');
  h = h.replace(/\n/g,'<br>');
  return h;
}
function hideEmpty(){ if(emptyEl) emptyEl.style.display='none'; }
function scrollBot(){ msgsEl.scrollTop=msgsEl.scrollHeight; }

/* ══════════════════════════════════════
   SESSION SIDEBAR
══════════════════════════════════════ */
async function loadSessions(){
  try{
    const r = await fetch('/api/chat/sessions');
    if(r.status===401){ location.href='/login'; return; }
    const d = await r.json();
    allSessions = d.sessions || [];
    renderSessionList();
  } catch(e){
    console.error('Failed to load sessions:',e);
  }
}

function renderSessionList(){
  if(allSessions.length===0){
    sessionListEl.innerHTML='<div class="hs-empty">No chats yet.<br>Click New to start.</div>';
    return;
  }
  sessionListEl.innerHTML='';
  allSessions.forEach(s=>{
    const item = document.createElement('div');
    item.className = 'session-item' + (s._id===currentSessionId?' active':'');
    item.dataset.id = s._id;
    item.innerHTML=`
      <div class="session-title" title="${escH(s.title)}">${escH(s.title)}</div>
      <div class="session-date">${fmtDate(s.created_at)}</div>
      <button class="session-del" onclick="deleteSession(event,'${s._id}')" title="Delete">🗑</button>`;
    item.addEventListener('click',()=>openSession(s._id,s.title));
    sessionListEl.appendChild(item);
  });
}

async function openSession(sessionId, title){
  currentSessionId = sessionId;
  pendingPlan = null;
  document.querySelectorAll('.session-item').forEach(el=>{
    el.classList.toggle('active', el.dataset.id===sessionId);
  });
  if(titleEl) titleEl.textContent = title || 'AI Learning Assistant';
  msgsEl.querySelectorAll('.mrow').forEach(r=>r.remove());
  if(emptyEl) emptyEl.style.display='none';
  try{
    const r = await fetch(`/api/chat/history?session_id=${sessionId}`);
    if(!r.ok) return;
    const d = await r.json();
    if(d.messages && d.messages.length>0){
      d.messages.forEach(m=>appendBubble(m.role,m.content,m.timestamp,false));
    } else {
      if(emptyEl) emptyEl.style.display='';
    }
  } catch(e){
    console.error('Failed to load messages:',e);
  }
}

async function deleteSession(e, sessionId){
  e.stopPropagation();
  if(!confirm('Delete this chat?')) return;
  try{
    await fetch(`/api/chat/sessions/${sessionId}`,{method:'DELETE'});
    if(currentSessionId===sessionId){
      currentSessionId = null;
      pendingPlan = null;
      msgsEl.querySelectorAll('.mrow').forEach(r=>r.remove());
      if(emptyEl) emptyEl.style.display='';
      if(titleEl) titleEl.textContent='AI Learning Assistant — Nexus';
    }
    allSessions = allSessions.filter(s=>s._id!==sessionId);
    renderSessionList();
  } catch(e){
    console.error('Delete session failed:',e);
  }
}

/* ══════════════════════════════════════
   NEW CHAT
══════════════════════════════════════ */
function newChat(){
  currentSessionId = null;
  pendingPlan = null;
  msgsEl.querySelectorAll('.mrow').forEach(r=>r.remove());
  if(emptyEl) emptyEl.style.display='';
  if(titleEl) titleEl.textContent='AI Learning Assistant — Nexus';
  document.querySelectorAll('.session-item').forEach(el=>el.classList.remove('active'));
  inputEl.focus();
}

/* ══════════════════════════════════════
   CHAT BUBBLES
══════════════════════════════════════ */
function appendBubble(role, content, iso, animate=true){
  hideEmpty();
  const row = document.createElement('div');
  row.className = `mrow ${role==='user'?'user':'bot'}`;
  if(!animate) row.style.animation='none';
  row.innerHTML=`
    <div class="mav ${role==='user'?'usr':'bot'}">${role==='user'?'👤':'🤖'}</div>
    <div class="mcontent">
      <div class="mbubble">${fmtMD(content)}</div>
      <div class="mtime">${fmtTime(iso)}</div>
    </div>`;
  msgsEl.appendChild(row);
  scrollBot();
}

function showTyping(){
  const row = document.createElement('div');
  row.className = 'mrow bot typing';
  row.id = 'typing';
  row.innerHTML=`
    <div class="mav bot">🤖</div>
    <div class="mcontent">
      <div class="mbubble">
        <div class="tdot"></div>
        <div class="tdot"></div>
        <div class="tdot"></div>
      </div>
    </div>`;
  msgsEl.appendChild(row);
  scrollBot();
}

function hideTyping(){
  const r = document.getElementById('typing');
  if(r) r.remove();
}

/* ══════════════════════════════════════
   WEEKLY PLAN
══════════════════════════════════════ */
function appendPlanOffer(){
  hideEmpty();
  const row = document.createElement('div');
  row.className = 'mrow bot';
  row.id = 'plan-offer-row';
  row.innerHTML=`
    <div class="mav bot">🤖</div>
    <div class="mcontent">
      <div class="mbubble">
        📅 Would you like me to save this plan to your <strong>Weekly Planner</strong>?
        <div style="display:flex;gap:8px;margin-top:10px">
          <button onclick="confirmSavePlan()" class="btn btn-primary btn-sm">✅ Yes, save it!</button>
          <button onclick="declineSavePlan()" class="btn btn-outline btn-sm">No thanks</button>
        </div>
      </div>
      <div class="mtime">${fmtTime()}</div>
    </div>`;
  msgsEl.appendChild(row);
  scrollBot();
}

async function confirmSavePlan(){
  const offerRow = document.getElementById('plan-offer-row');
  if(offerRow) offerRow.remove();
  if(!pendingPlan){
    appendBubble('bot','⚠️ No plan found to save.',new Date().toISOString());
    return;
  }
  const lines = pendingPlan.split('\n').filter(l=>l.trim());
  let saved = 0;
  for(const line of lines){
    const match = line.match(/^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday):\s*(.+)$/i);
    if(match){
      try{
        await fetch('/api/planner',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({day:match[1], task_text:match[2].trim()})
        });
        saved++;
      } catch(e){
        console.error('Failed to save task:',e);
      }
    }
  }
  pendingPlan = null;
  appendBubble('bot',
    `✅ Done! I've saved **${saved} tasks** to your Weekly Planner. Click **Planner** in the top menu to view them!`,
    new Date().toISOString()
  );
}

function declineSavePlan(){
  const offerRow = document.getElementById('plan-offer-row');
  if(offerRow) offerRow.remove();
  pendingPlan = null;
  appendBubble('bot',
    "No problem! The plan is here in the chat whenever you need it. 😊",
    new Date().toISOString()
  );
}

function processBotReply(rawText){
  // Check for full learning package
  if(rawText.includes('LEARNING_PACKAGE_START')){
    parseLearningPackage(rawText);
    return;
  }
  // Check for simple weekly plan
  const planMatch = rawText.match(/WEEKLY_PLAN_START([\s\S]*?)WEEKLY_PLAN_END/);
  if(planMatch){
    pendingPlan = planMatch[1].trim();
    let displayText = rawText
      .replace(/WEEKLY_PLAN_START[\s\S]*?WEEKLY_PLAN_END/,'')
      .replace(/PLAN_OFFER:.*$/m,'')
      .trim();
    appendBubble('bot', displayText, new Date().toISOString());
    setTimeout(()=>appendPlanOffer(), 400);
    return;
  }
  if(rawText.includes('PLAN_CONFIRMED') && pendingPlan){
    confirmSavePlan();
    return;
  }
  appendBubble('bot', rawText, new Date().toISOString());
}

function parseLearningPackage(rawText){
  // Extract topic from plan
  const planMatch  = rawText.match(/PLAN_START([\s\S]*?)PLAN_END/);
  const mcqMatch   = rawText.match(/MCQ_START([\s\S]*?)MCQ_END/);
  const codeMatch  = rawText.match(/CODING_START([\s\S]*?)CODING_END/);
  const motivMatch = rawText.match(/MOTIVATION_START([\s\S]*?)MOTIVATION_END/);

  // Get topic
  let topic = 'Programming';
  if(motivMatch){
    const topicLine = motivMatch[1].match(/TOPIC:\s*(.+)/);
    if(topicLine) topic = topicLine[1].trim();
  }

  // Parse plan
  let planDays = {};
  if(planMatch){
    const lines = planMatch[1].trim().split('\n');
    lines.forEach(line=>{
      const m = line.match(/^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday):\s*(.+)$/i);
      if(m) planDays[m[1]] = m[2].trim();
    });
  }

  // Parse MCQ
  let mcqData = [];
  if(mcqMatch){
    const text = mcqMatch[1];
    const dayBlocks = text.split(/DAY:\d+/).filter(b=>b.trim());
    const dayNums   = [...text.matchAll(/DAY:(\d+)/g)].map(m=>parseInt(m[1]));
    dayBlocks.forEach((block, idx)=>{
      const dayNum = dayNums[idx] || (idx+1);
      const qBlocks = block.trim().split(/(?=Q:)/);
      qBlocks.forEach(qb=>{
        if(!qb.trim()) return;
        const qLine = qb.match(/Q:\s*(.+)/);
        const aLine = qb.match(/A\)\s*(.+)/);
        const bLine = qb.match(/B\)\s*(.+)/);
        const cLine = qb.match(/C\)\s*(.+)/);
        const dLine = qb.match(/D\)\s*(.+)/);
        const ansLine = qb.match(/ANS:\s*([ABCD])/);
        if(qLine && ansLine){
          mcqData.push({
            day:      dayNum,
            question: qLine[1].trim(),
            options:  {
              A: aLine ? aLine[1].trim() : '',
              B: bLine ? bLine[1].trim() : '',
              C: cLine ? cLine[1].trim() : '',
              D: dLine ? dLine[1].trim() : '',
            },
            answer: ansLine[1].trim(),
          });
        }
      });
    });
  }

  // Parse coding tasks
  let codingData = [];
  if(codeMatch){
    const text = codeMatch[1];
    const dayNums = [...text.matchAll(/DAY:(\d+)/g)].map(m=>parseInt(m[1]));
    const blocks  = text.split(/DAY:\d+/).filter(b=>b.trim());
    blocks.forEach((block, idx)=>{
      const taskLine = block.match(/TASK:\s*(.+)/);
      const hintLine = block.match(/HINT:\s*(.+)/);
      if(taskLine){
        codingData.push({
          day:  dayNums[idx] || (idx+1),
          task: taskLine[1].trim(),
          hint: hintLine ? hintLine[1].trim() : '',
        });
      }
    });
  }

  // Parse motivation
  let motivData = { topic, story:'', daily_tip:'' };
  if(motivMatch){
    const storyLine = motivMatch[1].match(/STORY:\s*([\s\S]*?)(?=DAILY_TIP:|$)/);
    const tipLine   = motivMatch[1].match(/DAILY_TIP:\s*(.+)/);
    if(storyLine) motivData.story     = storyLine[1].trim();
    if(tipLine)   motivData.daily_tip = tipLine[1].trim();
  }

  // Store pending package
  window.pendingPackage = { topic, planDays, mcqData, codingData, motivData };

  // Show preview in chat
  showPackagePreview(topic, planDays, mcqData, codingData);
}

function showPackagePreview(topic, planDays, mcqData, codingData){
  hideEmpty();
  const days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const planHtml = days.map(d=>
    planDays[d] ? `<div style="padding:4px 0;border-bottom:1px solid var(--bdr);font-size:13px"><span style="color:var(--amber);font-family:var(--fM);font-size:11px">${d}</span><br>${escH(planDays[d])}</div>` : ''
  ).join('');

  const row = document.createElement('div');
  row.className = 'mrow bot';
  row.id = 'package-preview-row';
  row.innerHTML=`
    <div class="mav bot">🤖</div>
    <div class="mcontent" style="max-width:85%">
      <div class="mbubble">
        <div style="margin-bottom:12px">
          🎯 I've prepared a complete <strong>${escH(topic)}</strong> learning package for you!
        </div>

        <div style="background:var(--bg-r);border:1px solid var(--bdr);border-radius:8px;padding:12px;margin-bottom:10px">
          <div style="font-family:var(--fM);font-size:11px;color:var(--amber);margin-bottom:8px;letter-spacing:.08em">📅 WEEKLY PLAN</div>
          ${planHtml}
        </div>

        <div style="background:var(--bg-r);border:1px solid var(--bdr);border-radius:8px;padding:12px;margin-bottom:10px">
          <div style="font-family:var(--fM);font-size:11px;color:var(--amber);margin-bottom:4px;letter-spacing:.08em">📝 PRACTICE</div>
          <div style="font-size:13px;color:var(--tx-s)">${mcqData.length} MCQ questions across 7 days + coding tasks</div>
        </div>

        <div style="background:var(--bg-r);border:1px solid var(--bdr);border-radius:8px;padding:12px;margin-bottom:14px">
          <div style="font-family:var(--fM);font-size:11px;color:var(--amber);margin-bottom:4px;letter-spacing:.08em">🔥 MOTIVATION</div>
          <div style="font-size:13px;color:var(--tx-s)">Personalised success story + daily tip for ${escH(topic)}</div>
        </div>

        <div style="font-size:13px;color:var(--tx-s);margin-bottom:12px">
          Confirm to save everything to your Planner, Practice page, and Motivation page automatically.
        </div>

        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button onclick="confirmPackage()" class="btn btn-primary btn-sm">✅ Save everything!</button>
          <button onclick="declinePackage()" class="btn btn-outline btn-sm">No thanks</button>
        </div>
      </div>
      <div class="mtime">${fmtTime()}</div>
    </div>`;
  msgsEl.appendChild(row);
  scrollBot();
}

async function confirmPackage(){
  const pkg = window.pendingPackage;
  if(!pkg) return;

  const previewRow = document.getElementById('package-preview-row');
  if(previewRow) previewRow.remove();

  // Show saving indicator
  appendBubble('bot', '⏳ Saving your learning package…', new Date().toISOString());

  let saved = 0;

  // 1. Save planner tasks
  const days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  for(const day of days){
    if(pkg.planDays[day]){
      try{
        await fetch('/api/planner',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
         body:JSON.stringify({day, task_text: pkg.planDays[day], source:'learning', plan_name: pkg.topic + ' Learning'})
        });
        saved++;
      } catch(e){ console.error('Planner save failed:',e); }
    }
  }

  // 2. Save practice set
  let practiceSetId = null;
  try{
    const r = await fetch('/api/practice',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        topic:  pkg.topic,
        mcq:    pkg.mcqData,
        coding: pkg.codingData,
      })
    });
    const d = await r.json();
    if(d.practice_set) practiceSetId = d.practice_set._id;
  } catch(e){ console.error('Practice save failed:',e); }

  // 3. Save motivation
  try{
    await fetch('/api/motivation',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(pkg.motivData)
    });
  } catch(e){ console.error('Motivation save failed:',e); }

  window.pendingPackage = null;

  // Show success
  msgsEl.querySelectorAll('.mrow').forEach((r,i,arr)=>{ if(i===arr.length-1) r.remove(); });

  appendBubble('bot',
    `✅ **Everything saved!** Here's what was added:\n\n📅 **Weekly Planner** — 7 days of ${pkg.topic} tasks\n📝 **Practice Page** — ${pkg.mcqData.length} MCQ questions + coding tasks\n🔥 **Motivation Page** — Your ${pkg.topic} success story\n\nHead to the **Practice** page to start Day 1 quiz, or check your **Planner** to see your schedule!`,
    new Date().toISOString()
  );
}

function declinePackage(){
  const previewRow = document.getElementById('package-preview-row');
  if(previewRow) previewRow.remove();
  window.pendingPackage = null;
  appendBubble('bot',
    "No problem! Just ask whenever you're ready to start learning. 😊",
    new Date().toISOString()
  );
}

/* ══════════════════════════════════════
   SEND MESSAGE
══════════════════════════════════════ */
async function sendMsg(){
  const text = inputEl.value.trim();
  if(!text || sendBtn.disabled) return;
  appendBubble('user', text, new Date().toISOString());
  inputEl.value='';
  resizeInput();
  inputEl.disabled = true;
  sendBtn.disabled = true;
  showTyping();
  try{
    const body = {message: text};
    if(currentSessionId) body.session_id = currentSessionId;
    const r = await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)
    });
    hideTyping();
    if(r.status===401){ location.href='/login'; return; }
    const d = await r.json();
    if(r.ok && d.reply){
      if(!currentSessionId && d.session_id){
        currentSessionId = d.session_id;
        await loadSessions();
        document.querySelectorAll('.session-item').forEach(el=>{
          el.classList.toggle('active', el.dataset.id===currentSessionId);
        });
      }
      processBotReply(d.reply);
    } else {
      appendBubble('bot','⚠️ '+(d.error||'Something went wrong.'),new Date().toISOString());
    }
  } catch(e){
    hideTyping();
    appendBubble('bot','⚠️ Network error — please check your connection.',new Date().toISOString());
  } finally{
    inputEl.disabled = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

/* ══════════════════════════════════════
   OTHER ACTIONS
══════════════════════════════════════ */
function suggest(el){
  inputEl.value = el.textContent;
  sendMsg();
}

async function clearChat(){
  if(!confirm('Clear messages in this chat?')) return;
  const url = currentSessionId
    ? `/api/chat/history?session_id=${currentSessionId}`
    : '/api/chat/history';
  await fetch(url,{method:'DELETE'});
  msgsEl.querySelectorAll('.mrow').forEach(r=>r.remove());
  if(emptyEl) emptyEl.style.display='';
  pendingPlan = null;
}

async function checkStatus(){
  try{
    const r = await fetch('/api/status');
    if(!r.ok){
      dotEl.className='sdot error';
      statusEl.textContent='Status check failed';
      return;
    }
    const d = await r.json();
    console.log('Status:', d);
    if(d.ollama && d.ollama.ok && d.ollama.model_loaded){
      dotEl.className='sdot online';
      statusEl.textContent='Connected · ' + d.ollama.model;
    } else if(d.ollama && d.ollama.ok){
      dotEl.className='sdot error';
      statusEl.textContent='Model not found — run: ollama pull mistral';
    } else {
      dotEl.className='sdot error';
      statusEl.textContent='Ollama not running — run: ollama serve';
    }
  } catch(e){
    console.error('Status error:',e);
    dotEl.className='sdot error';
    statusEl.textContent='Cannot reach server';
  }
}

async function logout(){
  await fetch('/api/logout',{method:'POST'});
  location.href='/';
}

function resizeInput(){
  inputEl.style.height='auto';
  inputEl.style.height=Math.min(inputEl.scrollHeight,120)+'px';
}

inputEl.addEventListener('input',resizeInput);
inputEl.addEventListener('keydown',e=>{
  if(e.key==='Enter' && !e.shiftKey){
    e.preventDefault();
    sendMsg();
  }
});

/* ══════════════════════════════════════
   INIT
══════════════════════════════════════ */
loadSessions();
checkStatus();
inputEl.focus();