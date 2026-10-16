#!/usr/bin/env python3
"""Validate the statistical engine extracted from the actual browser HTML.

Run beside the app: python validate_statistics.py --html index.html
Python dependencies: requirements-validation.txt. Also requires Node.js 18+.
No browser, network call or npm package is used by this runner.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

import numpy as np
from scipy.stats import fisher_exact, norm
from statsmodels.stats.proportion import (
    confint_proportions_2indep,
    power_proportions_2indep,
    proportions_ztest,
)


NODE_RUNNER = r"""
const fs=require('fs'),vm=require('vm');
const request=JSON.parse(fs.readFileSync(0,'utf8'));
const ctx={};vm.createContext(ctx);vm.runInContext(request.engine,ctx,{timeout:10000});
const M=ctx.LabMath;
if(!M)throw Error('The supplied script does not expose LabMath.');
const plans=request.plans.map(x=>{const ns=M.plan(...x);return {input:x,n:ns,model:M.model(x[0],x[0]*(1+x[1]),...ns,x[2],x[5]||'two-sided'),previous:ns[0]>2?M.model(x[0],x[0]*(1+x[1]),ns[0]-1,Math.max(2,Math.ceil((ns[0]-1)*x[4]/(1-x[4]))),x[2],x[5]||'two-sided').power:null};});
const simulations=request.simulations.map((s,i)=>{
 const [p0,p1,n0,n1,alpha,R,alternative='two-sided']=s,rng=M.seeded(91200+i);
 const rows=M.simulate(p0,p1,n0,n1,alpha,R,rng,alternative);
 return {input:s,rejections:rows.filter(r=>r.significant).length,sparse:rows.filter(r=>r.sparse).length,theory:M.model(p0,p1,n0,n1,alpha,alternative).power};
});
const moments=request.moments.map(([n,p,R],i)=>{
 const rng=M.seeded(19200+i);let sum=0,sum2=0;
 for(let j=0;j<R;j++){let v=M.binomial(n,p,rng);if(!Number.isInteger(v)||v<0||v>n)throw Error('Invalid binomial count');sum+=v;sum2+=v*v;}
 return {n,p,R,mean:sum/R,variance:(sum2-sum*sum/R)/(R-1)};
});
const invalid=[()=>M.analyse(-1,10,2,10),()=>M.analyse(11,10,2,10),()=>M.analyse(1,1,2,10),()=>M.analyse(1.5,10,2,10),()=>M.model(0,.2,100,100,.05),()=>M.model(.2,1,100,100,.05),()=>M.plan(.2,0,.05,.8,.5)].map(f=>{try{f();return false;}catch{return true;}});
const rr=M.seeded(12345);let revsum=0,revsum2=0,zeros=0;const revenueN=200000;
for(let i=0;i<revenueN;i++){let x=M.revenue(rr);revsum+=x;revsum2+=x*x;if(x===0)zeros++;}
process.stdout.write(JSON.stringify({
 cdf:request.z.map(z=>M.cdf(z)),quantiles:request.probs.map(p=>M.quantile(p)),
 models:request.models.map(x=>M.model(...x)),plans,
 analyses:request.analyses.map(x=>M.analyse(...x)),simulations,moments,invalid,
 revenue:{R:revenueN,mean:revsum/revenueN,zeroRate:zeros/revenueN},
 boundary:[M.binomial(100,0),M.binomial(100,1)]
}));
"""


def reference_model(p0, p1, n0, n1, alpha, alternative="two-sided"):
    pooled = (n0 * p0 + n1 * p1) / (n0 + n1)
    se0 = np.sqrt(pooled * (1 - pooled) * (1 / n0 + 1 / n1))
    se1 = np.sqrt(p0 * (1 - p0) / n0 + p1 * (1 - p1) / n1)
    cutoff = norm.ppf(1 - alpha / (2 if alternative=="two-sided" else 1)) * se0
    power = (norm.cdf((-cutoff - (p1 - p0)) / se1) if alternative!="greater" else 0) + (norm.sf((cutoff - (p1 - p0)) / se1) if alternative!="less" else 0)
    return dict(se0=float(se0), se1=float(se1), cutoff=float(cutoff), power=float(power))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', type=Path, default=Path(__file__).with_name('index.html'))
    parser.add_argument('--report', type=Path, help='Optional JSON report destination')
    args = parser.parse_args()
    if not args.html.is_file():
        parser.error(f'HTML not found: {args.html}. Point --html to the actual application index.html.')
    if not shutil.which('node'):
        parser.error('Node.js 18+ is required to execute the actual JavaScript statistical engine.')
    raw = args.html.read_bytes()
    text = raw.decode('utf-8')
    match = re.search(r'<script\b[^>]*\bid=[\"\x27]lab-statistics[\"\x27][^>]*>(.*?)</script>', text, re.S)
    if not match:
        parser.error('Cannot find the inline script with id="lab-statistics" in the supplied HTML.')
    engine = match.group(1)
    request = dict(
        engine=engine,
        z=np.linspace(-8, 8, 321).tolist(),
        probs=[.0005,.001,.005,.025,.05,.1,.5,.9,.95,.975,.995,.999,.9995],
        models=[
            [.2,.21,25583,25583,.05], [.2,.19,24641,24641,.05],
            [.23,.2484,15000,9000,.01], [.02,.025,10000,5000,.05],
            [.8,.76,3000,9000,.2], [.2,.2,10000,10000,.05],
            [.2,.21,20000,20000,.01], [.2,.21,20000,20000,.05],
            [.2,.21,20000,20000,.05,'greater'], [.2,.19,20000,20000,.05,'less'],
            [.2,.19,20000,10000,.01,'greater'], [.2,.21,10000,20000,.8,'less'],
            [.2,.2,10000,10000,.05,'greater'], [.2,.2,10000,10000,.05,'less'],
        ],
        plans=[
            [.2,.05,.05,.8,.5], [.2,.05,.05,.9,.5], [.2,.025,.05,.8,.5],
            [.2,-.05,.05,.8,.5], [.23,.08,.01,.8,.3725],
            [.2,.05,.05,.8,.5,'greater'], [.2,-.05,.05,.8,.5,'less'], [.23,.08,.01,.8,.3725,'greater'],
        ],
        analyses=[
            [5200,26000,5460,26000,.05], [0,20,0,20,.05],
            [20,20,20,20,.05], [0,12,4,13,.05], [1,100,6,100,.01],
            [150,500,90,400,.05], [1,2,0,2,.05], [0,1000,1,1000,.05],
            [5200,26000,5460,26000,.05,'greater'], [5200,26000,5460,26000,.05,'less'],
            [0,12,4,13,.05,'greater'], [0,12,4,13,.05,'less'],
            [0,20,0,20,.05,'greater'], [20,20,20,20,.05,'less'],
            [150,500,90,400,.8,'less'],
        ],
        simulations=[
            [.2,.2,5000,5000,.05,20000],
            [.2,.21,25583,25583,.05,20000],
            [.2,.19,24641,24641,.05,20000],
            [.2,.2,5000,5000,.05,10000,'greater'], [.2,.2,5000,5000,.05,10000,'less'],
            [.2,.21,20000,20000,.05,10000,'greater'], [.2,.19,20000,20000,.05,10000,'less'],
        ],
        moments=[[10,.2,20000],[1000,.02,20000],[100000,.6,20000]],
    )
    completed = subprocess.run(['node','-e',NODE_RUNNER], input=json.dumps(request), text=True, capture_output=True, timeout=180, check=True)
    data = json.loads(completed.stdout)
    checks = []

    def check(name, condition, detail=None):
        checks.append(dict(name=name, passed=bool(condition), detail=detail))

    cdf_error = float(np.max(np.abs(np.array(data['cdf']) - norm.cdf(request['z']))))
    quant_error = float(np.max(np.abs(np.array(data['quantiles']) - norm.ppf(request['probs']))))
    check('Normal CDF vs SciPy', cdf_error < 1e-7, dict(max_abs_error=cdf_error, tolerance=1e-7))
    check('Normal quantile vs SciPy', quant_error < 1e-4, dict(max_abs_error=quant_error, tolerance=1e-4))
    for i, (x, got) in enumerate(zip(request['models'], data['models'])):
        ref = reference_model(*x)
        errors={key:abs(got[key]-ref[key]) for key in ref}
        p0,p1,n0,n1,alpha=x[:5]
        alternative=x[5] if len(x)>5 else "two-sided"
        sm=float(power_proportions_2indep(diff=p1-p0, prop2=p0, nobs1=n1, ratio=n0/n1, alpha=alpha, alternative={'two-sided':'two-sided','greater':'larger','less':'smaller'}[alternative], return_results=False))
        check(f'Power model {i+1}: SciPy and statsmodels', errors['power']<2e-6 and abs(sm-got['power'])<2e-6 and errors['cutoff']<1e-7 and errors['se0']<1e-12 and errors['se1']<1e-12, dict(input=x,engine=got,scipy=ref,statsmodels_power=sm))
        check(f'Power + beta = 1 ({i+1})', abs(got['power']+got['beta']-1)<1e-12)
    check('Alpha and nominal confidence complement', abs(.05+(1-.05)-1)<1e-12)
    for i, item in enumerate(data['plans']):
        target=item['input'][3]
        check(f'Integer sample-size minimality {i+1}', item['model']['power']>=target and (item['previous'] is None or item['previous']<target), item)
    check('One-sided increase needs fewer users',data['plans'][5]['n'][0]<data['plans'][0]['n'][0])
    check('One-sided decrease needs fewer users',data['plans'][6]['n'][0]<data['plans'][3]['n'][0])
    check('Higher desired power requires more users', data['plans'][1]['n'][0]>data['plans'][0]['n'][0])
    check('Smaller effect magnitude requires more users', data['plans'][2]['n'][0]>data['plans'][0]['n'][0])
    p_low=data['models'][6]['power']
    p_high=data['models'][7]['power']
    check('Lower alpha lowers fixed-n power', p_low<p_high)
    for i,(x,got) in enumerate(zip(request['analyses'],data['analyses'])):
        x0,n0,x1,n1,alpha=x[:5]
        alternative=x[5] if len(x)>5 else "two-sided"
        pooled=(x0+x1)/(n0+n1)
        sparse=min(n0*pooled,n1*pooled,n0*(1-pooled),n1*(1-pooled))<5
        if sparse:
            p=float(fisher_exact([[x1,n1-x1],[x0,n0-x0]],alternative=alternative).pvalue)
        else:
            _,p=proportions_ztest([x1,x0],[n1,n0],value=0,alternative={'two-sided':'two-sided','greater':'larger','less':'smaller'}[alternative])
            p=float(p)
        if alternative=='two-sided':
            ci=np.asarray(confint_proportions_2indep(x1,n1,x0,n0,method='newcomb',compare='diff',alpha=alpha),dtype=float)
        elif alpha<.5:
            central=confint_proportions_2indep(x1,n1,x0,n0,method='newcomb',compare='diff',alpha=2*alpha)
            ci=np.asarray([central[0],1] if alternative=='greater' else [-1,central[1]])
        else:
            # Signed-z extension at unusual nominal confidence <=50%; numerical only.
            z=norm.ppf(1-alpha)
            def directed_wilson(x,n):
                ph=x/n;den=1+z*z/n;mid=(ph+z*z/(2*n))/den;half=z*np.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/den
                return max(0,mid-half),min(1,mid+half)
            l0,u0=directed_wilson(x0,n0);l1,u1=directed_wilson(x1,n1);d=x1/n1-x0/n0
            low=max(-1,d-np.sign(z)*np.hypot(x1/n1-l1,u0-x0/n0));high=min(1,d+np.sign(z)*np.hypot(u1-x1/n1,x0/n0-l0))
            ci=np.asarray([low,1] if alternative=='greater' else [-1,high])
        check(f'Observed test and CI {i+1}', abs(got['p']-p)<2e-6 and np.max(np.abs(np.array(got['ci'])-ci))<2e-6 and got['sparse']==sparse and got['significant']==(got['p']<alpha), dict(input=x,engine_p=got['p'],reference_p=p,engine_ci=got['ci'],reference_ci=ci.tolist(),method='Fisher' if sparse else 'pooled z'))
        if x0==0:
            check(f'Zero baseline relative change is undefined ({i+1})',got['relative'] is None)
    for i,item in enumerate(data['simulations']):
        p0,p1,n0,n1,alpha,R=item['input'][:6]
        alternative=item['input'][6] if len(item['input'])>6 else 'two-sided'
        theta=reference_model(p0,p1,n0,n1,alpha,alternative)['power'] if p0!=p1 else alpha
        observed=item['rejections']/R
        # Five Monte Carlo SEs plus a small absolute allowance for planning approximation.
        tolerance=5*np.sqrt(theta*(1-theta)/R)+.003
        check(f'Long-run simulated rejection rate {i+1}',abs(observed-theta)<tolerance,dict(input=item['input'],observed=observed,reference=theta,tolerance=float(tolerance),sparse_tables=item['sparse']))
    for i,item in enumerate(data['moments']):
        n,p,R=item['n'],item['p'],item['R'];mean=n*p;variance=n*p*(1-p)
        check(f'Binomial generator mean/variance {i+1}',abs(item['mean']-mean)<5*np.sqrt(variance/R) and abs(item['variance']/variance-1)<.08,dict(**item,reference_mean=mean,reference_variance=variance))
    check('Invalid inputs rejected by engine',all(data['invalid']))
    check('Binomial boundaries 0 and 1',data['boundary']==[0,100])
    mu=.19*np.exp(3.4+.65**2/2)+.01*np.exp(6+.65**2/2)
    second=.19*np.exp(2*3.4+2*.65**2)+.01*np.exp(2*6+2*.65**2)
    check('Synthetic revenue mean and zero mass',abs(data['revenue']['mean']-mu)<5*np.sqrt((second-mu**2)/data['revenue']['R']) and abs(data['revenue']['zeroRate']-.8)<.01,dict(**data['revenue'],reference_mean=float(mu)))
    report=dict(
        run_at_utc=datetime.now(timezone.utc).isoformat(),
        html_sha256=hashlib.sha256(raw).hexdigest(),
        engine_sha256=hashlib.sha256(engine.encode()).hexdigest(),
        environment=dict(python=platform.python_version(),node=subprocess.check_output(['node','--version'],text=True).strip(),numpy=np.__version__,scipy=importlib.metadata.version('scipy'),statsmodels=importlib.metadata.version('statsmodels')),
        passed=sum(c['passed'] for c in checks),total=len(checks),checks=checks,
        limitations=['No real-browser rendering or accessibility checks','Finite selected cases, not exhaustive validation','Simulation tolerance includes Monte Carlo and planning approximation','No production experiment validity audit'],
    )
    if args.report:
        args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    for c in checks:
        print(('PASS' if c['passed'] else 'FAIL')+' '+c['name'])
    print(f"\n{report['passed']}/{report['total']} checks passed")
    print('HTML SHA-256:',report['html_sha256'])
    if report['passed']!=report['total']:
        print('A failed check is not a reason to silently loosen tolerances. Investigate the changed input, numerical approximation or algorithm.',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
