#!/usr/bin/env node
/**
 * winwin.com Scraper (Node.js) — Extracts articles for a given date into CSV.
 * Usage: node scraper.js [--date YYYY-MM-DD]
 */

const puppeteer = require("puppeteer");
const fs = require("fs");
const path = require("path");

// ── Config ──────────────────────────────────────────────────────────────────
const BASE_URL = "https://winwin.com";
const OUTPUT = "winwin_articles.csv";
const MAX_RETRIES = 3;
const SCROLL_PAUSE = 2000;

// Arabic month mapping
const AR_MONTHS = {
  يناير: 1, فبراير: 2, مارس: 3, أبريل: 4,
  مايو: 5, يونيو: 6, يوليو: 7, أغسطس: 8,
  سبتمبر: 9, أكتوبر: 10, نوفمبر: 11, ديسمبر: 12,
};
const M2AR = Object.fromEntries(Object.entries(AR_MONTHS).map(([k, v]) => [v, k]));

// Arabic → English category mapping
const CATEGORY_MAP = {
  "كرة القدم": "Football", "كرة قدم": "Football",
  "الأخبار": "Football", "أخبار": "Football",
  "التنس": "Tennis", "تنس": "Tennis",
  "كرة السلة": "Basketball", "سلة": "Basketball",
  "رياضات ميكانيكية": "Motorsport",
  "الدوري الإسباني": "Football", "الدوري الإنجليزي": "Football",
  "الدوري الفرنسي": "Football", "الدوري الإيطالي": "Football",
  "الدوري الألماني": "Football", "الدوري السعودي": "Football",
  "الدوري المصري": "Football", "الدوري التونسي الممتاز": "Football",
  "الدوري الجزائري": "Football", "الدوري المغربي": "Football",
  "الدوري الأردني": "Football",
  "دوري أبطال أوروبا": "Football", "الدوري الأوروبي": "Football",
  "دوري أبطال آسيا للنخبة": "Football", "دوري أبطال آسيا2": "Football",
  "دوري أبطال أفريقيا": "Football",
  "دوري نجوم قطر": "Football", "كأس العالم": "Football",
  "كأس أمم أفريقيا": "Football",
  "كأس الأمم الإفريقية تحت 17 سنة": "Football",
  "الدوري الإسباني- الدرجة الثانية": "Football",
  "برشلونة": "Football", "ريال مدريد": "Football",
  "ليفربول": "Football", "بايرن ميونيخ": "Football", "بايرن ميونخ": "Football",
  "أرسنال": "Football", "مانشستر سيتي": "Football", "تشيلسي": "Football",
  "الهلال السعودي": "Football", "النصر السعودي": "Football",
  "الأهلي": "Football", "الزمالك": "Football",
  "الاتحاد السعودي": "Football", "محمد صلاح": "Football",
  "تونس": "Football", "المغرب": "Football", "مصر": "Football",
  "رومانيا": "Football", "إيران": "Football",
  "رياضات أخرى": "Other Sports",
};

// ── Helpers ──────────────────────────────────────────────────────────────────
function log(level, msg) {
  const ts = new Date().toISOString().replace("T", " ").slice(0, 19);
  console.log(`${ts} [${level}] ${msg}`);
}

function dateToAr(targetDate) {
  const d = targetDate || new Date();
  return `${d.getDate()} ${M2AR[d.getMonth() + 1]} ${d.getFullYear()}`;
}

function translateCategory(arCat) {
  if (!arCat) return "Football";
  arCat = arCat.trim();
  if (CATEGORY_MAP[arCat]) return CATEGORY_MAP[arCat];
  for (const [ar, en] of Object.entries(CATEGORY_MAP)) {
    if (arCat.includes(ar) || ar.includes(arCat)) return en;
  }
  if (["دوري", "كأس", "منتخب", "مباراة", "لاعب", "هدف"].some((k) => arCat.includes(k))) return "Football";
  if (["تنس", "راكيت"].some((k) => arCat.includes(k))) return "Tennis";
  if (arCat.includes("سلة")) return "Basketball";
  if (["فورمولا", "سيارات", "رالي"].some((k) => arCat.includes(k))) return "Motorsport";
  return "Football";
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function parseDate(str) {
  const m = str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) { console.error(`❌ Invalid date: ${str}. Use YYYY-MM-DD.`); process.exit(1); }
  return new Date(+m[1], +m[2] - 1, +m[3]);
}

function daysBetween(a, b) {
  return Math.round(Math.abs((a - b) / 86400000));
}

function escapeCsv(val) {
  const s = String(val || "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
  return `"${s.replace(/"/g, '""')}"`;
}

// ── Browser Setup ───────────────────────────────────────────────────────────
async function launchBrowser() {
  const browser = await puppeteer.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--window-size=1920,1080",
      "--disable-extensions",
      "--disable-software-rasterizer",
      "--disable-background-timer-throttling",
    ],
  });
  log("INFO", "✅ Chrome ready");
  return browser;
}

async function newPage(browser) {
  const page = await browser.newPage();
  await page.setUserAgent(
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
  );
  await page.setViewport({ width: 1920, height: 1080 });
  page.setDefaultTimeout(30000);
  page.setDefaultNavigationTimeout(30000);
  return page;
}

// ── Categories ──────────────────────────────────────────────────────────────
function getCategories() {
  const cats = [
    { name: "Football", url: `${BASE_URL}/news/homepage` },
    { name: "Football", url: `${BASE_URL}/كرة-القدم` },
    { name: "Tennis", url: `${BASE_URL}/تنس` },
    { name: "Basketball", url: `${BASE_URL}/كرة-السلة` },
    { name: "Motorsport", url: `${BASE_URL}/رياضات-ميكانيكية` },
  ];
  log("INFO", `📂 ${cats.length} categories`);
  return cats;
}

// ── Article Link Collection ─────────────────────────────────────────────────
async function getArticleLinks(page, url, catName, targetDate) {
  log("INFO", `📰 Collecting from: ${catName}`);
  const today = new Date();
  const td = targetDate || today;
  const tday = dateToAr(td);
  const daysAgo = daysBetween(today, td);
  const maxScrolls = Math.min(25 + daysAgo * 5, 200);
  log("INFO", `  📅 Target: ${tday} (${daysAgo} days ago, max ${maxScrolls} scrolls)`);

  const articles = [];
  const seen = new Set();

  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await sleep(3000);
  } catch (e) {
    log("WARN", `  ⚠️ Failed to load ${catName}: ${e.message.slice(0, 80)}`);
    return articles;
  }

  try {
    let lastH = await page.evaluate(() => document.body.scrollHeight);
    let stale = 0;
    let foundTarget = false;
    let passedTarget = false;

    for (let i = 0; i < maxScrolls; i++) {
      // Collect links from current page state
      const links = await page.evaluate((tday, newsPattern) => {
        const results = [];
        document.querySelectorAll("a[href]").forEach((a) => {
          const href = a.href;
          const text = a.textContent || "";
          if (href && decodeURIComponent(href).includes(newsPattern) && text.includes(tday)) {
            results.push({ url: href, text: text.slice(0, 200) });
          }
        });
        return results;
      }, tday, "/الأخبار/");

      for (const link of links) {
        if (!seen.has(link.url)) {
          seen.add(link.url);
          articles.push({ url: link.url, category: catName });
          foundTarget = true;
        }
      }

      // Check if we passed the target date
      if (foundTarget) {
        const hasOlder = await page.evaluate((tday, months) => {
          const allLinks = document.querySelectorAll("a[href]");
          const last10 = Array.from(allLinks).slice(-10);
          let olderCount = 0;
          for (const a of last10) {
            const t = a.textContent || "";
            if (!t.includes(tday) && months.some((m) => t.includes(m))) olderCount++;
          }
          return olderCount >= 3;
        }, tday, Object.keys(AR_MONTHS));
        if (hasOlder && articles.length > 0) {
          log("INFO", `  📍 Found ${articles.length} articles, scrolled past target date. Stopping.`);
          break;
        }
      }

      // Scroll down
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await sleep(SCROLL_PAUSE);

      const newH = await page.evaluate(() => document.body.scrollHeight);
      if (newH === lastH) {
        stale++;
        if (stale >= 3) break;
      } else {
        stale = 0;
      }
      lastH = newH;

      if (i > 0 && i % 10 === 0) {
        log("INFO", `  🔄 Scroll ${i}/${maxScrolls}, ${articles.length} links so far…`);
      }
    }
  } catch (e) {
    log("WARN", `  ⚠️ Scroll error in ${catName}: ${e.message.slice(0, 80)}`);
  }

  log("INFO", `  ✅ ${articles.length} links in ${catName}`);
  return articles;
}

// ── Single Article Scraping ─────────────────────────────────────────────────
async function scrapeArticle(page, url, category, targetDate) {
  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      await page.waitForSelector("h1", { timeout: 20000 });
      await sleep(1000);

      const data = await page.evaluate((baseUrl) => {
        // Title
        let title = "";
        const h1 = document.querySelector("h1");
        if (h1) title = h1.textContent.trim();
        if (!title) {
          const ogTitle = document.querySelector("meta[property='og:title']");
          title = ogTitle ? ogTitle.content.trim() : document.title.trim();
        }

        // Description
        let desc = "";
        const ogDesc = document.querySelector("meta[property='og:description']");
        if (ogDesc) desc = ogDesc.content.trim();
        if (!desc) {
          const metaDesc = document.querySelector("meta[name='description']");
          if (metaDesc) desc = metaDesc.content.trim();
        }
        if (!desc) {
          const ps = document.querySelectorAll("article p, [class*='content'] p");
          const texts = [];
          ps.forEach((p, i) => { if (i < 5 && p.textContent.trim().length > 20) texts.push(p.textContent.trim()); });
          desc = texts.join(" ");
        }

        // Image
        let img = "";
        const ogImg = document.querySelector("meta[property='og:image']");
        if (ogImg) img = ogImg.content.trim();
        if (!img) {
          const imgs = document.querySelectorAll("article img, picture img");
          for (const el of imgs) {
            const src = el.src || el.dataset.src || "";
            if (src && !src.startsWith("data:")) { img = src; break; }
          }
        }
        if (img && !img.startsWith("http")) img = new URL(img, baseUrl).href;

        // Category from page tags
        let pageCat = "";
        const tagLinks = document.querySelectorAll("[class*='tag'] a, [class*='category'] a, [class*='breadcrumb'] a");
        for (const bc of tagLinks) {
          const t = bc.textContent.trim();
          if (t && !["winwin", "الرئيسية", ""].includes(t) && t.length > 1) { pageCat = t; break; }
        }

        // Date
        let dt = "";
        const timeEl = document.querySelector("time");
        if (timeEl) dt = timeEl.textContent.trim();

        return { title, desc: desc.slice(0, 2000), img, pageCat, dt };
      }, BASE_URL);

      if (!data.title) return null;

      const rawCat = data.pageCat || category || "";
      const finalCat = translateCategory(rawCat);
      const articleDate = data.dt || dateToAr(targetDate);

      log("INFO", `  ✅ [${finalCat}] ${data.title.slice(0, 50)}…`);
      return {
        title: data.title,
        description: data.desc.replace(/<[^>]+>/g, "").trim(),
        image_url: data.img,
        date: articleDate,
        category: finalCat,
      };
    } catch (e) {
      log("WARN", `  ⚠️ Attempt ${attempt + 1}: ${e.constructor.name}`);
      if (attempt < MAX_RETRIES - 1) await sleep(2000);
    }
  }
  return null;
}

// ── CSV Output ──────────────────────────────────────────────────────────────
function saveToCsv(data) {
  const fields = ["title", "description", "image_url", "date", "category"];
  const header = fields.map((f) => escapeCsv(f)).join(",");
  const rows = data.map((r) => fields.map((f) => escapeCsv(r[f])).join(","));
  const csv = [header, ...rows].join("\n");
  fs.writeFileSync(OUTPUT, "\uFEFF" + csv, "utf-8"); // BOM for UTF-8
  log("INFO", `💾 ${data.length} articles → ${OUTPUT}`);
}

// ── Main ────────────────────────────────────────────────────────────────────
async function main() {
  // Parse --date argument
  const args = process.argv.slice(2);
  let targetDate = new Date();
  const dateIdx = args.indexOf("--date") !== -1 ? args.indexOf("--date") : args.indexOf("-d");
  if (dateIdx !== -1 && args[dateIdx + 1]) {
    targetDate = parseDate(args[dateIdx + 1]);
  }

  const t0 = Date.now();
  log("INFO", `🚀 winwin.com Scraper | Target date: ${targetDate.toISOString().slice(0, 10)} (${dateToAr(targetDate)})`);

  let browser = await launchBrowser();
  let page = await newPage(browser);
  const allLinks = [];
  const seenUrls = new Set();

  // Phase 1: Collect article links
  try {
    for (const cat of getCategories()) {
      try {
        const links = await getArticleLinks(page, cat.url, cat.name, targetDate);
        for (const link of links) {
          if (!seenUrls.has(link.url)) {
            seenUrls.add(link.url);
            allLinks.push(link);
          }
        }
      } catch (e) {
        log("WARN", `⚠️ Category ${cat.name} failed: ${e.message.slice(0, 60)}, restarting browser…`);
        try { await browser.close(); } catch {}
        browser = await launchBrowser();
        page = await newPage(browser);
      }
    }
  } finally {
    try { await browser.close(); } catch {}
  }

  log("INFO", `📊 ${allLinks.length} unique links`);

  // Phase 2: Scrape each article
  const results = [];
  const seenTitles = new Set();
  browser = await launchBrowser();
  page = await newPage(browser);

  try {
    for (let i = 0; i < allLinks.length; i++) {
      const info = allLinks[i];
      log("INFO", `[${i + 1}/${allLinks.length}]`);
      try {
        const article = await scrapeArticle(page, info.url, info.category, targetDate);
        if (article && !seenTitles.has(article.title)) {
          seenTitles.add(article.title);
          results.push(article);
        }
      } catch (e) {
        log("WARN", `💀 Browser issue, restarting: ${e.message.slice(0, 60)}`);
        try { await browser.close(); } catch {}
        browser = await launchBrowser();
        page = await newPage(browser);
        // Retry
        try {
          const article = await scrapeArticle(page, info.url, info.category, targetDate);
          if (article && !seenTitles.has(article.title)) {
            seenTitles.add(article.title);
            results.push(article);
          }
        } catch {}
      }
    }
  } finally {
    try { await browser.close(); } catch {}
  }

  saveToCsv(results);
  const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
  log("INFO", `🏁 Done in ${elapsed}s — ${results.length} articles`);
}

main().catch((e) => {
  console.error("Fatal error:", e);
  process.exit(1);
});
