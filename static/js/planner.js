/* ── planner.js — Nexus Learn Weekly Planner ── */

const DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
let tasks = {}; // { Monday: [{_id,task_text,created_at}], … }

/* ── Init ── */
async function init(){
  DAYS.forEach(d=>{ tasks[d]=[]; });
  await loadTasks();
  // default select today
  const today = new Date().toLocaleDateString('en-GB',{weekday:'long'});
  const sel = document.getElementById('task-day');
  if(sel){const o=[...sel.options].find(o=>o.value===today); if(o)sel.value=today;}
  document.getElementById('task-input').addEventListener('keydown',e=>{
    if(e.key==='Enter'){e.preventDefault();addTask();}
  });
}

async function loadTasks(){
  try{
    const r=await fetch('/api/planner');
    if(r.status===401){location.href='/login';return;}
    if(!r.ok) throw new Error('Failed to load');
    const d=await r.json();
    DAYS.forEach(day=>{ tasks[day]=[]; });
    (d.tasks||[]).forEach(t=>{ if(tasks[t.day]) tasks[t.day].push(t); });
  }catch(e){
    console.error('Planner load error:',e);
  }
  showGrid();
}

function showGrid(){
  const grid=document.getElementById('week-grid');
  const loading=document.getElementById('loading-tasks');
  if(loading) loading.style.display='none';
  grid.style.display='';
  grid.innerHTML='';
  DAYS.forEach(day=>{
    const col=document.createElement('div');
    col.className='dcol'; col.id='col-'+day;
    col.innerHTML=`<div class="dhdr"><span class="dname">${day}</span><span class="dcnt" id="cnt-${day}">0</span></div><div class="dtasks" id="dt-${day}"></div>`;
    grid.appendChild(col);
    renderDay(day);
  });
}

function renderDay(day){
  const c=document.getElementById('dt-'+day);
  const cnt=document.getElementById('cnt-'+day);
  if(!c) return;
  const list=tasks[day]||[];
  c.innerHTML='';
  cnt.textContent=list.length;
  if(list.length===0){c.innerHTML='<div class="dempty">No tasks yet</div>';return;}
  list.forEach(task=>{
    const id=task._id||task.id||'';
    const item=document.createElement('div');
    item.className='ti';
    item.innerHTML=`
      <input type="checkbox" class="tcb" onchange="toggleDone(this,'${esc(id)}','${esc(day)}')">
      <span class="ttxt" id="tx-${esc(id)}">${escH(task.task_text)}</span>
      <button class="tdel" onclick="deleteTask('${esc(id)}','${esc(day)}')" title="Remove">✕</button>`;
    c.appendChild(item);
  });
}

async function addTask(){
  const day=document.getElementById('task-day').value;
  const inp=document.getElementById('task-input');
  const text=inp.value.trim();
  if(!text){inp.focus();return;}
  const btn=document.getElementById('add-btn');
  btn.disabled=true; btn.textContent='…';
  try{
    const r=await fetch('/api/planner',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({day,task_text:text})
    });
    if(r.status===401){location.href='/login';return;}
    const d=await r.json();
    if(r.ok&&d.task){ tasks[day].push(d.task); renderDay(day); inp.value=''; inp.focus(); }
    else{ alert(d.error||'Failed to add task.'); }
  }catch(e){ alert('Network error.'); }
  finally{ btn.disabled=false; btn.textContent='+ Add Task'; }
}

async function deleteTask(id,day){
  try{
    const r=await fetch('/api/planner',{
      method:'DELETE',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({task_id:id})
    });
    if(r.ok){ tasks[day]=tasks[day].filter(t=>(t._id||t.id)!==id); renderDay(day); }
  }catch(e){console.error('Delete failed:',e);}
}

function toggleDone(cb,id,day){
  const el=document.getElementById('tx-'+id);
  if(el) el.classList.toggle('done',cb.checked);
}

async function logout(){ await fetch('/api/logout',{method:'POST'}); location.href='/'; }

function escH(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function esc(s){ return String(s||'').replace(/'/g,"\\'"); }

document.addEventListener('DOMContentLoaded', init);
