// app.js — Debate MVP using Chrome’s Web Speech API only.

const connectBtn = document.getElementById("connectBtn");
const startBtn   = document.getElementById("startBtn");
const muteBtn    = document.getElementById("muteBtn");
const statusEl   = document.getElementById("status");
const youEl      = document.getElementById("youStream");
const agentAEl   = document.getElementById("agentAStream");
const agentBEl   = document.getElementById("agentBStream");
const topicInput = document.getElementById("topic");

let rec = null;
let isMicOn = false;
let currentSpeaker = "A";

function speak(text, who, onEnd) {
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate=1.0; u.pitch=1.0;
    u.onend=()=>{ if(onEnd) onEnd(); };
    u.onerror=(e)=>console.error("TTS error:",e);
    if(who==="A") agentAEl.textContent=text;
    if(who==="B") agentBEl.textContent=text;
    window.speechSynthesis.speak(u);
  } catch(e){ console.error("speak failed", e); }
}

function startSTT(){
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!Rec){ alert("SpeechRecognition not supported. Use Chrome/Edge."); return; }
  rec=new Rec();
  rec.continuous=true; rec.interimResults=true; rec.lang="en-US";
  rec.onresult=(e)=>{
    let interim="", final="";
    for(let i=e.resultIndex;i<e.results.length;i++){
      const res=e.results[i];
      if(res.isFinal) final+=res[0].transcript;
      else interim+=res[0].transcript;
    }
    if(interim) youEl.textContent=interim;
    if(final){
      youEl.textContent=final;
      window.speechSynthesis.cancel();
      currentSpeaker="You";
      handleUserSpeech(final.trim());
    }
  };
  rec.onerror=e=>console.error("STT error:",e);
  rec.onend=()=>{ if(isMicOn) try{ rec.start(); }catch(_){} };
  try{ rec.start(); isMicOn=true; }catch(e){ console.error("STT start fail",e); }
}
function stopSTT(){ try{rec?.stop();}catch(_){} isMicOn=false; }

function handleUserSpeech(text){
  if(currentSpeaker==="You"){ currentSpeaker="A"; fakeAgentRespond("A", text); }
}
function fakeAgentRespond(who,input){
  let reply=who==="A"
    ? "I disagree with '"+input+"'"
    : "But consider the opposite of '"+input+"'";
  speak(reply, who, ()=>{
    if(who==="A"){ currentSpeaker="B"; fakeAgentRespond("B", reply); }
    else currentSpeaker="A";
  });
}

connectBtn.onclick=()=>{
  connectBtn.disabled=true; startSTT();
  muteBtn.disabled=false; startBtn.disabled=false;
  setStatus("mic active, STT running");
};
muteBtn.onclick=()=>{
  if(isMicOn){ stopSTT(); muteBtn.textContent="Unmute mic"; }
  else{ startSTT(); muteBtn.textContent="Mute mic"; }
};
startBtn.onclick=()=>{
  const topic=topicInput.value.trim()||"Should AI have legal personhood?";
  currentSpeaker="A"; fakeAgentRespond("A", topic);
};
function setStatus(s){ statusEl.textContent=s; }
