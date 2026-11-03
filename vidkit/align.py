"""align.py IN.(mp4|wav) OUT.json [--prompt "..."]
Whisper (faster-whisper small) for the words, then pocketsphinx forced alignment
for exact word start/end times. Output: [[start,end,"Word"],...] (original spelling)."""
import sys,json,re,subprocess,os,numpy as np,argparse
ap=argparse.ArgumentParser();ap.add_argument('inp');ap.add_argument('out');ap.add_argument('--prompt',default='Caliversity. Calisthenics. Handstand. WhatsApp.')
ap.add_argument('--model',default=os.environ.get('WHISPER_MODEL','small'))
a=ap.parse_args()
wav='/tmp/_vk_align.wav'
subprocess.run(['ffmpeg','-v','error','-y','-i',a.inp,'-ac','1','-ar','16000',wav],check=True)
import wave
w=wave.open(wav);pcm=np.frombuffer(w.readframes(w.getnframes()),np.int16);audio=(pcm/32768).astype(np.float32)
from faster_whisper import WhisperModel
mp=a.model
for cand in [mp, os.path.join(os.path.dirname(__file__),'..','..','model',mp), os.path.expanduser(f'~/model/{mp}')]:
    if os.path.isdir(cand): mp=cand;break
m=WhisperModel(mp,device='cpu',compute_type='int8',cpu_threads=os.cpu_count())
seg,_=m.transcribe(audio,word_timestamps=True,language='en',initial_prompt=a.prompt)
W=[[x.start,x.end,x.word.strip()] for s in seg for x in s.words]
# group into phrases at pauses >= 0.25s or sentence ends
groups=[];cur=[]
for i,wd in enumerate(W):
    cur.append(wd)
    nxt=W[i+1] if i+1<len(W) else None
    if nxt is None or nxt[0]-wd[1]>=0.25 or re.search(r'[.?!]$',wd[2]): groups.append(cur);cur=[]
NUM={'0':'zero','1':'one','2':'two','3':'three','4':'four','5':'five','6':'six','7':'seven','8':'eight','9':'nine','10':'ten','100':'one hundred'}
def norm(t):
    t=t.lower().replace('-',' ')
    t=re.sub(r"[^a-z0-9' ]",'',t)
    return ' '.join(NUM.get(p,p) for p in t.split())
from pocketsphinx import Decoder
out=[]
for g in groups:
    s=max(0,g[0][0]-0.15); e=min(len(pcm)/16000,g[-1][1]+0.15)
    words=[norm(x[2]) for x in g]
    try:
        d=Decoder(samprate=16000,lm=None,bestpath=False,loglevel='FATAL')
        d.set_align_text(' '.join(x for x in words if x))
        d.start_utt();d.process_raw(pcm[int(s*16000):int(e*16000)].tobytes(),full_utt=True);d.end_utt()
        segs=[x for x in d.seg() if x.word not in('<s>','</s>','<sil>','(NULL)','[NOISE]')]
        tok=[];[tok.extend([(j,p) for p in wd.split()]) for j,wd in enumerate(words)]
        if len(segs)!=len(tok): raise ValueError('count')
        st={};en={}
        for (j,_),sg in zip(tok,segs):
            st.setdefault(j,s+sg.start_frame/100);en[j]=s+(sg.end_frame+1)/100
        for j,x in enumerate(g):
            out.append([round(st.get(j,x[0]),2),round(en.get(j,x[1]),2),x[2]])
    except Exception as ex:
        for x in g: out.append([round(x[0],2),round(x[1],2),x[2]])
        print('align fallback (whisper times) for:',' '.join(x[2] for x in g),ex,file=sys.stderr)
json.dump(out,open(a.out,'w'))
print(' '.join(f'{x[2]}@{x[0]:.2f}' for x in out))
