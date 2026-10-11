/* Mobile-first controller for the EXISTING four-tab historical SPA.
   No canonical facts, citations, personnel or geographic data are authored here.
   A phone displays one task at a time instead of shrinking desktop columns. */
(() => {
  'use strict';
  const panel=document.getElementById('panel-timeline');
  const slider=document.getElementById('atlas-year-range');
  const dashboard=document.getElementById('atlas-year-dashboard');
  const workspace=panel?.querySelector('.atlas-timeline-workspace');
  const globalSheet=document.getElementById('atlas-global-sheet');
  if(!panel||!slider||!dashboard||!workspace||!globalSheet)return;

  const breakpoint=window.matchMedia('(max-width:900px)');
  // Keep original, descriptive accessible names. Only abbreviate the VISIBLE
  // labels in the bottom navigation, where 320px cannot fit long words.
  const shortNames={timeline:'Год',people:'Люди',poster:'Плакат',research:'Источники'};
  document.querySelectorAll('.mode-tab[data-view]').forEach(tab=>{
    const num=tab.querySelector('.num');
    const full=tab.textContent.replace(/^\s*\d{1,2}\s*/,'').trim();
    const large=document.createElement('span');
    large.className='atlas-desktop-tab-label';large.textContent=full;
    const small=document.createElement('span');
    small.className='atlas-mobile-tab-label';
    small.textContent=shortNames[tab.dataset.view]||full;
    tab.setAttribute('aria-label',full);
    tab.replaceChildren(...(num?[num]:[]),large,small);
  });
  const modeMap=new Map([
    ['summary','Сводка'],
    ['timeline','Шкала']
  ]);
  let mode='summary';
  const controls=document.createElement('nav');
  controls.id='atlas-mobile-actions';
  controls.className='atlas-mobile-actions';
  controls.setAttribute('aria-label','Действия с выбранным годом');

  function makeButton(label,choice,callback) {
    const b=document.createElement('button');
    b.type='button';
    b.className='atlas-mobile-action';
    b.dataset.mobileAction=choice;
    b.textContent=label;
    b.setAttribute('aria-label',label);
    b.addEventListener('click',callback);
    controls.append(b);
    return b;
  }
  const summaryBtn=makeButton('Сводка','summary',()=>setMode('summary'));
  const timelineBtn=makeButton('Шкала','timeline',()=>setMode('timeline'));
  const overviewBtn=makeButton('Века','overview',()=>{
    window.dispatchEvent(new CustomEvent('atlas:mobile-open-overview'));
  });
  const compareBtn=makeButton('Сравнить','compare',()=>{
    window.dispatchEvent(new CustomEvent('atlas:mobile-open-compare'));
  });
  summaryBtn.setAttribute('aria-controls','atlas-year-dashboard');
  timelineBtn.setAttribute('aria-controls','time-canvas');
  overviewBtn.setAttribute('aria-controls','atlas-global-sheet');
  compareBtn.setAttribute('aria-controls','atlas-global-sheet');
  panel.append(controls);

  // Preserve the original historical disclaimer, but reveal it on demand
  // rather than consuming several lines of the first phone screen.
  const originalCaveat=dashboard.querySelector('.atlas-year-dashboard-caveat');
  const sliderRange=dashboard.querySelector('.atlas-year-dashboard-range');
  if(originalCaveat && sliderRange){
    const more=document.createElement('details');
    more.className='atlas-mobile-method';
    const summary=document.createElement('summary');
    summary.textContent='Как понимать эти сведения?';
    const explanation=document.createElement('p');
    explanation.textContent=originalCaveat.textContent;
    more.append(summary,explanation);
    sliderRange.after(more);
  }

  // The universal sheet was mounted inside the desktop chart workspace.
  // That workspace is hidden in summary mode, so move ONLY the presentation
  // panel to its independent parent on mobile, then restore on desktop.
  function synchronizeLayout(){
    const mobile=breakpoint.matches;
    document.documentElement.classList.toggle('atlas-mobile',mobile);
    if(mobile && globalSheet.parentElement!==panel)
      panel.appendChild(globalSheet);
    if(!mobile && globalSheet.parentElement!==workspace)
      workspace.appendChild(globalSheet);
    panel.dataset.mobileMode=mode;
    refreshControls();
  }
  function refreshControls(){
    for(const b of controls.querySelectorAll('button')){
      if(modeMap.has(b.dataset.mobileAction))
        b.setAttribute('aria-pressed',String(b.dataset.mobileAction===mode));
    }
  }
  function chooseContextEra(){
    const y=Number(slider.value);
    const available=[
      [1417,1546,'muscovy'],[1547,1616,'tsardom'],
      [1617,1681,'romanov'],[1682,1741,'dual'],
      [1742,1816,'eighteenth'],[1817,1893,'imperial'],
      [1894,1925,'transition'],[1926,1952,'early'],
      [1953,1981,'middle'],[1982,1991,'late']
    ];
    const active=panel.querySelector('.era-btn[aria-pressed="true"]');
    const numbers=active?.textContent.match(/\d{4}/g)?.map(Number);
    // Respect an intentionally selected short period if it still contains
    // the chosen year. The all-centuries view is unreadable at phone width.
    if(active?.dataset.era!=='all'&&numbers?.length>=2&&
       numbers[0]<=y&&y<=numbers[1])return;
    const target=available.find(([a,b])=>a<=y&&y<=b)?.[2]||'all';
    const button=panel.querySelector('.era-btn[data-era="'+target+'"]');
    if(button&&button!==active)button.click();
  }
  function setMode(next){
    if(!modeMap.has(next))return;
    if(!breakpoint.matches)return;
    if(next==='summary' && workspace.classList.contains('atlas-sidebar-open')){
      workspace.querySelector('.atlas-sidebar-close')?.click();
    }
    if(next==='summary'){
      // Summary is a universal year chooser; do not leave the slider bounded
      // to a narrow era selected for chart readability.
      const all=panel.querySelector('.era-btn[data-era="all"]');
      if(all&&all.getAttribute('aria-pressed')!=='true')all.click();
    }
    mode=next;
    panel.dataset.mobileMode=mode;
    refreshControls();
    if(mode==='timeline'){
      chooseContextEra();
      requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')));
    }
    if(mode==='summary')dashboard.scrollTop=0;
  }

  // "Все записи" on a summary accordion uses the EXISTING source-backed
  // inspector. The previous handler opens the historical details drawer.
  // Reveal that drawer's chart workspace before the original click bubbles.
  panel.addEventListener('click',event=>{
    if(!breakpoint.matches||panel.classList.contains('smuta-map-active'))return;
    if(event.target.closest('.atlas-year-role-details'))
      setMode('timeline');
  },true);

  // A subtle swipe gesture on the *year heading*, never over scrollable cards
  // or calendar controls. Left = next year, right = previous.
  const heading=dashboard.querySelector('.atlas-year-dashboard-heading');
  let start=null;
  if(heading){
    heading.addEventListener('pointerdown',event=>{
      if(!breakpoint.matches || event.pointerType!=='touch' ||
         event.target.closest('button,a,input,select'))return;
      start={id:event.pointerId,x:event.clientX,y:event.clientY};
    });
    heading.addEventListener('pointerup',event=>{
      if(!start||event.pointerId!==start.id)return;
      const dx=event.clientX-start.x,dy=event.clientY-start.y;
      start=null;
      if(Math.abs(dx)<65||Math.abs(dy)>35)return;
      const step=dx<0?1:-1;
      const next=Math.max(Number(slider.min),
        Math.min(Number(slider.max),Number(slider.value)+step));
      if(next===Number(slider.value))return;
      slider.value=String(next);
      slider.dispatchEvent(new Event('input',{bubbles:true}));
    });
    heading.addEventListener('pointercancel',()=>{start=null;});
  }

  window.addEventListener('atlas:route',event=>{
    if(event.detail?.view!=='timeline')return;
    if(breakpoint.matches){
      // The direct year route always starts with the readable summary;
      // switching back from another tab does not restore a hidden plot.
      mode='summary';panel.dataset.mobileMode='summary';refreshControls();
    }
  });
  if(breakpoint.addEventListener)
    breakpoint.addEventListener('change',synchronizeLayout);
  synchronizeLayout();
})();
