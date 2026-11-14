// OutreachPilot — LinkedIn post collector.
// Injected by the agent (Claude in Chrome, javascript_tool) into a LinkedIn content-search page:
//   https://www.linkedin.com/search/results/content/?keywords=<kw>&sortBy=%22date_posted%22
// It only READS the page. It never clicks Apply links or opens other sites.
//
// After injection:
//   await __scan(5)   -> scrolls / clicks "Load more" 5 times, then fills window.__res
//   __res.posts       -> number of posts scanned
//   __res.hits        -> posts with a NEW email      [{em:[...], txt}]
//   __res.lp          -> posts with a NEW apply link [{links:[...], txt}]
//   __res.np          -> posts with neither, plus poster name / degree / profile URL
//
// "Known" emails and links are kept in this browser's localStorage so a post is processed once:
//   __outreach_known  (comma-separated emails)   __outreach_links  (comma-separated URLs)

(() => {
  if (!location.hostname.endsWith('linkedin.com') || /login|checkpoint|authwall|uas/.test(location.pathname)) {
    return 'STOP ' + location.pathname; // signed out or security check: the agent must stop
  }

  const load = key => new Set((localStorage.getItem(key) || '').split(',').filter(Boolean));
  window.__KNOWN = new Set([...load('__outreach_known')].map(e => e.toLowerCase()));
  window.__KL = load('__outreach_links');

  // Apply-style links found in post text.
  window.__LRE = /https?:\/\/(lnkd\.in|forms\.gle|docs\.google\.com\/forms|[a-z0-9.-]*(careers|jobs|apply|greenhouse|lever|workable|keka|zohorecruit|darwinbox|naukri)[a-z0-9.-]*\.[a-z]{2,})\/[A-Za-z0-9_\/-]{3,60}/gi;
  // US-only contract posts are skipped outright.
  const US_ONLY = /\b(W2|C2C|USC|H1B|H-1B|US Citizens|USA-Based)\b/;
  const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
  const OPEN_TO_WORK = /open to work|opentowork|looking for (a )?(new )?(job|opportunit|role)|seeking (new )?opportunit|I am looking|I'm looking/i;

  window.__collect = () => {
    const text = (document.querySelector('main') || document.body).innerText;
    const posts = text.split('Feed post');
    const hits = [], lp = [];
    for (const p of posts) {
      if (US_ONLY.test(p)) continue;
      const em = [...new Set((p.match(EMAIL) || []).map(e => e.toLowerCase().replace(/\.$/, '')))]
        .filter(e => !__KNOWN.has(e));
      if (em.length) { hits.push({ em, txt: p.slice(0, 2500).replace(/\s+/g, ' ') }); continue; }
      const links = [...new Set(p.match(__LRE) || [])].filter(x => !__KL.has(x));
      if (links.length) lp.push({ links, txt: p.slice(0, 4000).replace(/\s+/g, ' ') });
    }
    return { posts: posts.length - 1, hits, lp };
  };

  // Posts with no email and no link: find the poster so the agent can send a connection request.
  window.__np = () => {
    const out = [];
    const heads = [...document.querySelector('main').querySelectorAll('span')]
      .filter(e => e.childElementCount === 0 && e.textContent.trim() === 'Feed post');
    for (const h of heads) {
      let c = h;
      for (let i = 0; i < 8 && c.parentElement; i++) { c = c.parentElement; if (c.innerText.length > 300) break; }
      const t = c.innerText;
      __LRE.lastIndex = 0;
      if (/@[A-Za-z0-9-]+\.[A-Za-z]{2,}/.test(t) || __LRE.test(t)) { __LRE.lastIndex = 0; continue; }
      __LRE.lastIndex = 0;
      const hm = t.match(/(?:^|\n)([^\n•]{3,60}?)\s*\n?\s*•\s*(1st|2nd|3rd\+?)/);
      if (!hm) continue;
      const name = hm[1].trim();
      const a = [...c.querySelectorAll('a[href*="/in/"]')].find(a => a.textContent.includes(name.split(' ')[0]));
      if (!a) continue;
      const profile = (a.href.match(/https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%-]+/) || [''])[0];
      if (!/hiring|opening|looking for|we are|we're/i.test(t) || OPEN_TO_WORK.test(t)) continue;
      out.push({ name, degree: hm[2], profile, txt: t.slice(0, 2500).replace(/\s+/g, ' ') });
    }
    return out;
  };

  window.__scan = async rounds => {
    for (let i = 0; i < rounds; i++) {
      window.scrollTo(0, document.body.scrollHeight);
      await new Promise(r => setTimeout(r, 2500));
      const more = [...document.querySelectorAll('button')].find(b => /load more|show more results/i.test(b.innerText));
      if (more) more.click();
      await new Promise(r => setTimeout(r, 1800));
    }
    window.__res = __collect();
    window.__res.np = __np();
    return 'done';
  };

  // Call after a run so the same emails/links are not processed again.
  window.__remember = () => {
    const save = (key, items) => {
      const set = load(key); items.forEach(x => set.add(x));
      localStorage.setItem(key, [...set].join(','));
    };
    save('__outreach_known', __res.hits.flatMap(h => h.em));
    save('__outreach_links', __res.lp.flatMap(x => x.links));
  };

  return 'ready';
})();
