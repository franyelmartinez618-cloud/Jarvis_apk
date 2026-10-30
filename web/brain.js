(() => {
"use strict";
const STOP = new Set("a al algo ante como con de del desde donde durante e el ella en entre es esa ese esto fue ha hacia hay la las le les lo los más me mi muy ni no nos o otra para pero por porque que se sin sobre su también te tiene tu un una unos y ya".split(/\s+/));
const fold = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const tokens = s => fold(s).match(/[a-z0-9]{2,}/g) || [];
let ready=false, entries=[], lexicon=new Set(), model=null, evaluation=null, modelStatus="loading";
async function load() {
  if (ready) return;
  const paths=["./knowledge.json","./brain.json","./evaluation.json"];
  const results=await Promise.allSettled(paths.map(path=>fetch(path,{cache:"no-store"}).then(r=>r.ok?r.json():Promise.reject(Error(path+" HTTP "+r.status)))));
  if(results[0].status==="fulfilled"){entries=results[0].value.entries||[];lexicon=new Set(results[0].value.lexicon||[]);}
  if(results[1].status==="fulfilled"){
    model=results[1].value;model._weights={};
    for(const [name,values] of Object.entries(model.weights||{}))model._weights[name]=Float32Array.from(values);
  }
  if(results[2].status==="fulfilled")evaluation=results[2].value;
  modelStatus=model&&model.format==="jarvis-from-zero-v1"?(evaluation&&evaluation.pass===true?"approved":"not-approved"):"not-available";
  ready=true;
}
function search(query){
  const terms=[...new Set(tokens(query).filter(x=>!STOP.has(x)))];
  return entries.map(entry=>{
    const text=fold(entry.title+" "+entry.text);let score=0;
    for(const term of terms){
      if(text.includes(term))score+=fold(entry.title).includes(term)?1.5:1;
      else if(term.length>5&&text.includes(term.slice(0,-1)))score+=.2;
    }
    const phrase=fold(query).trim();if(phrase.length>5&&text.includes(phrase))score+=1;
    return {entry,score:score/Math.max(1,terms.length)};
  }).sort((a,b)=>b.score-a.score).slice(0,4);
}
function knowledgeAnswer(query){
  const ranked=search(query);
  if(!ranked.length||ranked[0].score<.34)return "Todavía no encuentro información fiable sobre ese tema en mi biblioteca local. Puedo aprenderlo al ampliar mis fuentes; no voy a inventar una respuesta.";
  return ranked.filter(x=>x.score>=Math.max(.34,ranked[0].score*.55)).slice(0,2)
    .map(x=>x.entry.text+"\n\nFuente: "+x.entry.source+(x.entry.url?"\n"+x.entry.url:"")).join("\n\n");
}
function matmul(input,length,inDim,outDim,weight,bias){
  const output=new Float32Array(length*outDim);
  for(let p=0;p<length;p++)for(let o=0;o<outDim;o++){
    let sum=bias?bias[o]:0,offset=o*inDim;
    for(let i=0;i<inDim;i++)sum+=weight[offset+i]*input[p*inDim+i];
    output[p*outDim+o]=sum;
  }
  return output;
}
function layerNorm(input,length,dim,weight,bias){
  const output=new Float32Array(input.length);
  for(let p=0;p<length;p++){
    const offset=p*dim;let mean=0;
    for(let i=0;i<dim;i++)mean+=input[offset+i];
    mean/=dim;let variance=0;
    for(let i=0;i<dim;i++){const delta=input[offset+i]-mean;variance+=delta*delta;}
    const inv=1/Math.sqrt(variance/dim+1e-5);
    for(let i=0;i<dim;i++)output[offset+i]=(input[offset+i]-mean)*inv*weight[i]+bias[i];
  }
  return output;
}
function forward(ids){
  const c=model.config,dim=c.dim,length=ids.length,w=model._weights,embedding=w["token.weight"],position=w["position.weight"];
  let state=new Float32Array(length*dim);
  for(let p=0;p<length;p++){
    const id=Math.max(0,Math.min(c.vocab-1,ids[p]));
    for(let d=0;d<dim;d++)state[p*dim+d]=embedding[id*dim+d]+position[p*dim+d];
  }
  for(let layer=0;layer<c.layers;layer++){
    const prefix="blocks."+layer+".";
    const norm1=layerNorm(state,length,dim,w[prefix+"ln1.weight"],w[prefix+"ln1.bias"]);
    const qkv=matmul(norm1,length,dim,dim*3,w[prefix+"attn.qkv.weight"],w[prefix+"attn.qkv.bias"]);
    const attended=new Float32Array(length*dim),heads=c.heads,headDim=dim/heads,scale=1/Math.sqrt(headDim);
    for(let p=0;p<length;p++)for(let h=0;h<heads;h++){
      const start=h*headDim,scores=new Float32Array(p+1);let max=-Infinity;
      for(let prior=0;prior<=p;prior++){
        let dot=0;for(let d=0;d<headDim;d++)dot+=qkv[p*dim*3+start+d]*qkv[prior*dim*3+dim+start+d];
        scores[prior]=dot*scale;if(scores[prior]>max)max=scores[prior];
      }
      let total=0;for(let prior=0;prior<=p;prior++){scores[prior]=Math.exp(scores[prior]-max);total+=scores[prior];}
      for(let prior=0;prior<=p;prior++){const factor=scores[prior]/total;for(let d=0;d<headDim;d++)attended[p*dim+start+d]+=factor*qkv[prior*dim*3+dim*2+start+d];}
    }
    const projected=matmul(attended,length,dim,dim,w[prefix+"attn.proj.weight"],w[prefix+"attn.proj.bias"]);
    for(let i=0;i<state.length;i++)state[i]+=projected[i];
    const norm2=layerNorm(state,length,dim,w[prefix+"ln2.weight"],w[prefix+"ln2.bias"]);
    const hidden=matmul(norm2,length,dim,dim*4,w[prefix+"fc1.weight"],w[prefix+"fc1.bias"]);
    for(let i=0;i<hidden.length;i++){const x=hidden[i];hidden[i]=.5*x*(1+Math.tanh(.7978845608*(x+.044715*x*x*x)));}
    const feed=matmul(hidden,length,dim*4,dim,w[prefix+"fc2.weight"],w[prefix+"fc2.bias"]);
    for(let i=0;i<state.length;i++)state[i]+=feed[i];
  }
  const final=layerNorm(state,length,dim,w["norm.weight"],w["norm.bias"]),offset=(length-1)*dim,logits=new Float32Array(c.vocab);
  for(let token=0;token<c.vocab;token++){let sum=0;for(let d=0;d<dim;d++)sum+=final[offset+d]*embedding[token*dim+d];logits[token]=sum;}
  return logits;
}
function generate(query){
  if(modelStatus!=="approved"||!model)return "";
  const map=new Map(model.vocab.map((v,i)=>[v,i]));
  const prompt="JARVIS\nPregunta: "+String(query).slice(0,240)+"\nRespuesta:";
  let ids=[...prompt].map(char=>map.get(char)??0);
  for(let step=0;step<140;step++){
    const logits=forward(ids.slice(-model.config.context));
    const top=Array.from(logits,(v,i)=>({id:i,value:v/.7})).sort((a,b)=>b.value-a.value).slice(0,10);
    const maximum=top[0].value;let total=0;
    for(const item of top){item.prob=Math.exp(item.value-maximum);total+=item.prob;}
    let random=Math.random()*total,chosen=top[top.length-1].id;
    for(const item of top){random-=item.prob;if(random<=0){chosen=item.id;break;}}
    if(chosen===2)break;ids.push(chosen);
  }
  return ids.slice([...prompt].length).map(id=>model.vocab[id]||"").join("").trim();
}
function isReadable(answer){
  const words=String(answer).split(/\s+/).filter(w=>w.length>1);
  if(words.length<8)return false;
  const letters=(answer.match(/[a-záéíóúñü]/gi)||[]).length;
  const vowels=(answer.match(/[aeiouáéíóú]/gi)||[]).length;
  if(!letters||vowels/letters<.27||vowels/letters>.58)return false;
  const known=words.filter(w=>lexicon.has(fold(w).replace(/[^a-záéíóúñü]/g,""))).length;
  return known/words.length>.28;
}
function status(){return{ready,passages:entries.length,model:modelStatus,externalModel:false,architecture:model?model.config:null};}
window.JarvisBrain={
  load,
  answer:async query=>{await load();if(modelStatus==="approved"){const output=generate(query);if(isReadable(output))return output;}return knowledgeAnswer(query);},
  search:async query=>{await load();return search(query);},
  status
};
load().catch(error=>{console.error("JARVIS knowledge initialization",error);ready=true;modelStatus="load-error";});
})();
