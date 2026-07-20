const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });
  await page.goto('http://100.92.127.1:3000/board', { waitUntil: 'networkidle0', timeout: 30000 });
  
  // Navigate to CRG Board or Main Board
  await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a, div')).filter(el => el.textContent.includes('CRG Board') || el.textContent.includes('Main Board'));
    if (links.length > 0) links[links.length - 1].click();
  });
  
  await new Promise(r => setTimeout(r, 2000));

  // Navigate to Workflow tab
  await page.evaluate(() => {
    const tabs = Array.from(document.querySelectorAll('a, button')).filter(el => el.textContent.toLowerCase().includes('workflow'));
    if (tabs.length > 0) tabs[0].click();
  });

  await new Promise(r => setTimeout(r, 2000));
  
  // Set to Flowchart and curved
  await page.evaluate(() => {
    const modeSelects = Array.from(document.querySelectorAll('button')).filter(el => el.textContent.includes('Flowchart') || el.textContent.includes('ASCII') || el.textContent.includes('Mindmap'));
    // Usually it's in a custom select, click the one that has mode text to open it
    // Wait, the custom select uses divs and buttons. It's too complex to drive the custom select reliably.
    // Instead I'll just screenshot what's visible. By default it's Flowchart.
  });

  await page.screenshot({ path: '/Users/carlosrivas/Dev/Kenbun/dashboard/flowchart_ss.png' });
  console.log('Flowchart screenshot saved');

  // Attempt to switch to ASCII using window variables or DOM clicks
  await page.evaluate(() => {
    // The CustomSelect toggle
    const buttons = Array.from(document.querySelectorAll('button'));
    const modeBtn = buttons.find(b => b.textContent.includes('Flowchart') && b.innerHTML.includes('ChevronDown'));
    if (modeBtn) modeBtn.click();
  });
  
  await new Promise(r => setTimeout(r, 500));
  
  await page.evaluate(() => {
    const options = Array.from(document.querySelectorAll('button'));
    const asciiOpt = options.find(b => b.textContent === 'ASCII Board');
    if (asciiOpt) asciiOpt.click();
  });
  
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: '/Users/carlosrivas/Dev/Kenbun/dashboard/ascii_ss.png' });
  console.log('ASCII screenshot saved');

  await browser.close();
})();
