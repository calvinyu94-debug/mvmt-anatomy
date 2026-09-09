// Pull the MVMT structure table (id, name, latin, region, system, layer) out of mvmt-program's
// index.html, where it lives as the ANATOMY array, into a JSON file for tools/bp3d_export.py.
//   node tools/mvmt_structures.mjs <path to mvmt-program/index.html> <out.json>
import fs from 'node:fs';
const [src,out]=process.argv.slice(2);
if(!src||!out)throw new Error('usage: mvmt_structures.mjs <mvmt-program/index.html> <out.json>');
const s=fs.readFileSync(src,'utf8');
const start=s.indexOf('const ANATOMY = [');if(start<0)throw new Error('ANATOMY not found');
// walk to the matching close bracket, skipping strings and comments
let i=start+'const ANATOMY = '.length,depth=0,inStr=null,esc=false,end=-1;
for(;i<s.length;i++){const c=s[i];
 if(inStr){if(esc){esc=false;continue;}if(c==='\\'){esc=true;continue;}if(c===inStr)inStr=null;continue;}
 if(c==='"'||c==="'"||c==='`'){inStr=c;continue;}
 if(c==='/'&&s[i+1]==='*'){i=s.indexOf('*/',i)+1;continue;}
 if(c==='/'&&s[i+1]==='/'){i=s.indexOf('\n',i);continue;}
 if(c==='['||c==='{')depth++;else if(c===']'||c==='}'){depth--;if(depth===0){end=i+1;break;}}}
const arr=(0,eval)(s.slice(start+'const ANATOMY = '.length,end));
const rows=arr.map(x=>({id:x.id,name:x.name,latin:x.latin,region:x.region,alsoRegion:x.alsoRegion,system:x.system,layer:x.layer,kind:x.kind}));
fs.writeFileSync(out,JSON.stringify(rows));
console.log(`${rows.length} structures -> ${out}`);
