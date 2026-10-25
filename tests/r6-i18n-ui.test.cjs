const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const nodes = new Map();
function node(selector) {
 if (!nodes.has(selector)) nodes.set(selector, {textContent:'',innerHTML:'',hidden:false,value:'',dataset:{},attributes:{},classList:{add(){},remove(){},contains(){return false}},setAttribute(k,v){this.attributes[k]=v},getAttribute(k){return this.attributes[k]},closest(){return node('footer')},querySelector(s){return node(s)},querySelectorAll(){return []},focus(){},select(){},setCustomValidity(){},reportValidity(){}});
 return nodes.get(selector);
}
const posts=[]; const stored=new Map([['r6-pinned-person','Player Alpha']]); const alerts=[];
const document={querySelector:node,querySelectorAll(){return []},addEventListener(){},documentElement:{lang:'zh-CN'},title:''};
const storage={getItem:k=>stored.get(k)||null,setItem:(k,v)=>stored.set(k,v),removeItem:k=>stored.delete(k)};
const ctx=vm.createContext({document,navigator:{language:'zh-CN',languages:['zh-CN'],userAgent:'test',platform:'Linux'},localStorage:storage,window:{localStorage:storage,addEventListener(){},matchMedia(){return {matches:false}}},fetch:async(url,opts)=>{if(opts?.method==='POST')posts.push(JSON.parse(opts.body));return {ok:true,json:async()=>({people:[{name:'Player Alpha',status:'yes',time:'any'},{name:'Player Beta',status:'no',time:'21:15'},{name:'Player Gamma',status:'maybe',time:'09:00'}]})}},setTimeout(){},alert:m=>alerts.push(m),confirm:()=>false,prompt:()=>null,Intl,Date});
const run=code=>vm.runInContext(code,ctx);
for(const file of ['i18n.js','app.js']) run(fs.readFileSync(path.join(__dirname,'../web',file),'utf8'));
(async()=>{
 await new Promise(resolve=>setImmediate(resolve));
 const before=run('JSON.stringify(people)');
 assert.equal(run('typeof setLanguage'),'function','app must expose a language switch that rerenders the UI');
 run("setLanguage('en')");
 assert.equal(document.documentElement.lang,'en');
 assert.match(document.title,/Playing tonight/);
 assert.equal(stored.get('r6-language'),'en');
 assert.equal(stored.get('r6-pinned-person'),'Player Alpha');
 assert.equal(run('JSON.stringify(people)'),before);
 assert.equal(posts.length,0,'language switching must never write shared data');
 const cards=node('#cards').innerHTML;
 for(const copy of ['Ready whenever','Any time','Not playing tonight','Not decided yet','Coming','Not coming','Undecided','Edit Player Alpha','Unpin Player Alpha','Choose arrival time for Player Alpha']) assert.ok(cards.includes(copy),copy);
 assert.ok(!/[\u3400-\u9fff]/u.test(cards),'English cards contain no untranslated UI');
 run('openTimePicker(0, null)');
 for(const copy of ['Any time','Ready whenever','Evening','Other hours']) assert.ok(node('#time-picker-options').innerHTML.includes(copy),copy);
 run("timePickerHour='23';renderTimePicker()");
 assert.ok(node('#time-picker-step').textContent.includes('23'));
 assert.equal((node('#time-picker-options').innerHTML.match(/data-time-minute=/g)||[]).length,1);
 for(const platform of ['ios','android','other']) {run(`showInstallGuide('${platform}')`);for(const id of ['#install-copy','#install-steps','#install-tip'])assert.ok(!/[\u3400-\u9fff]/u.test(node(id).textContent+node(id).innerHTML),id+platform);}
 run("setLanguage('zh-CN')");
 assert.equal(document.documentElement.lang,'zh-CN');
 assert.ok(node('#cards').innerHTML.includes('随时待命'));
 assert.equal(posts.length,0);
 run("showToast('消息已发送');setLanguage('en')");
 assert.equal(node('#toast').textContent,'Message sent','active toast retains its meaning when switching language');
 node('#send-note').disabled=true;
 run("setLanguage('zh-CN');setLanguage('en')");
 assert.equal(node('#send-note').textContent,'Sending…','language changes must preserve in-flight message state');
 node('#send-note').disabled=false;
 for(const lang of ['en','zh-CN']) {
  run(`setLanguage('${lang}')`);
  for(const code of ['invalid_payload','empty_message','message_too_long','request_too_large','unsupported_control_character','notification_failed','unknown']) {
   ctx.fetch=async()=>({ok:false,status:502,json:async()=>({error:code})});
   node('#note-text').value='Synthetic test message';
   await node('#note-form').onsubmit({preventDefault(){}});
   assert.ok(alerts.at(-1));
   assert.equal(/[\u3400-\u9fff]/u.test(alerts.at(-1)),lang==='zh-CN',code);
  }
  ctx.fetch=async()=>{throw Error('untranslated browser exception')};
  await node('#note-form').onsubmit({preventDefault(){}});
  assert.ok(!alerts.at(-1).includes('untranslated'));
 }
 console.log('PASS: bilingual cards, accessible controls, picker, install guides, every message error and pending state; locale switch preserves roster/pin and never POSTs');
})().catch(e=>{console.error(e);process.exitCode=1});
