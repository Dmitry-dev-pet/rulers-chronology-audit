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
  function setMode(next){
    if(!modeMap.has(next))return;
    if(!breakpoint.matches)return;
    if(next==='summary' && workspace.classList.contains('atlas-sidebar-open')){
      workspace.querySelector('.atlas-sidebar-close')?.click();
    }
    mode=next;
    panel.dataset.mobileMode=mode;
    refreshControls();
    // The desktop chart calculates horizontal width from clientWidth. When it
    // becomes visible again after summary mode, trigger a real resize.
    if(mode==='timeline')
      requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')));
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
