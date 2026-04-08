#!/usr/bin/env python3
import argparse, csv, logging, re, sys, time
from datetime import date, datetime
from urllib.parse import unquote, urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *
try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    import subprocess; subprocess.check_call([sys.executable,"-m","pip","install","webdriver-manager"])
    from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://winwin.com"
OUTPUT = "winwin_articles.csv"
AR_MONTHS = {"يناير":1,"فبراير":2,"مارس":3,"أبريل":4,"مايو":5,"يونيو":6,"يوليو":7,"أغسطس":8,"سبتمبر":9,"أكتوبر":10,"نوفمبر":11,"ديسمبر":12}
M2AR = {v:k for k,v in AR_MONTHS.items()}

CATEGORY_MAP = {
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
}

def translate_category(ar_cat):
    """Translate Arabic category to English sport name."""
    if not ar_cat: return "Football"
    ar_cat = ar_cat.strip()
    if ar_cat in CATEGORY_MAP: return CATEGORY_MAP[ar_cat]
    for ar, en in CATEGORY_MAP.items():
        if ar in ar_cat or ar_cat in ar: return en
    if any(k in ar_cat for k in ["دوري","كأس","منتخب","مباراة","لاعب","هدف"]): return "Football"
    if any(k in ar_cat for k in ["تنس","راكيت"]): return "Tennis"
    if any(k in ar_cat for k in ["سلة"]): return "Basketball"
    if any(k in ar_cat for k in ["فورمولا","سيارات","رالي"]): return "Motorsport"
    return "Football"  # Default since most content is football

logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def date_to_ar(target_date=None):
    t=target_date or date.today(); return f"{t.day} {M2AR[t.month]} {t.year}"

def setup_driver():
    o=Options()
    for a in ["--headless=new","--no-sandbox","--disable-dev-shm-usage","--disable-gpu",
              "--window-size=1920,1080","--disable-extensions","--disable-software-rasterizer",
              "--remote-debugging-pipe","--disable-background-timer-throttling"]:
        o.add_argument(a)
    o.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    try:
        d=webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=o)
    except Exception:
        d=webdriver.Chrome(options=o)
    d.set_page_load_timeout(30); d.implicitly_wait(5)
    log.info("✅ Chrome ready"); return d

def get_categories(driver):
    cats=[
        {"name":"Football","url":f"{BASE_URL}/news/homepage"},
        {"name":"Football","url":f"{BASE_URL}/كرة-القدم"},
        {"name":"Tennis","url":f"{BASE_URL}/تنس"},
        {"name":"Basketball","url":f"{BASE_URL}/كرة-السلة"},
        {"name":"Motorsport","url":f"{BASE_URL}/رياضات-ميكانيكية"},
    ]
    log.info(f"📂 {len(cats)} categories"); return cats

def get_article_links(driver, url, cat_name="", target_date=None):
    log.info(f"📰 Collecting from: {cat_name}")
    td = target_date or date.today()
    tday=date_to_ar(td); arts=[]; seen=set()
    # More scrolls needed for older dates (roughly 10 articles/scroll)
    days_ago = (date.today() - td).days
    max_scrolls = min(25 + days_ago * 5, 200)
    log.info(f"  📅 Target: {tday} ({days_ago} days ago, max {max_scrolls} scrolls)")
    try:
        driver.get(url)
        WebDriverWait(driver,20).until(EC.presence_of_element_located((By.TAG_NAME,"body")))
        time.sleep(3)
    except Exception as e:
        log.warning(f"  ⚠️ Failed to load {cat_name}: {e.__class__.__name__}"); return arts
    try:
        last_h=driver.execute_script("return document.body.scrollHeight"); stale=0
        found_target_date = False
        passed_target_date = False
        for scroll_i in range(max_scrolls):
            for a in driver.find_elements(By.CSS_SELECTOR,"a[href]"):
                try:
                    h=a.get_attribute("href")
                    if not h or h in seen: continue
                    dec=unquote(h)
                    if "/الأخبار/" not in dec: continue
                    card_text = a.text or ""
                    if tday in card_text:
                        seen.add(h); arts.append({"url":h,"category":cat_name})
                        found_target_date = True
                    # Check if we scrolled past the target date (older articles visible)
                    elif found_target_date:
                        # If we already found target date articles and now see different dates
                        for m_name, m_num in AR_MONTHS.items():
                            if m_name in card_text:
                                passed_target_date = True
                                break
                except: continue
            # Stop if we found articles and then scrolled past them
            if found_target_date and passed_target_date and len(arts) > 0:
                log.info(f"  📍 Found {len(arts)} articles, scrolled past target date. Stopping.")
                break
            driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
            time.sleep(2)
            nh=driver.execute_script("return document.body.scrollHeight")
            if nh==last_h:
                stale+=1
                if stale>=3: break
            else: stale=0
            last_h=nh
            if scroll_i % 10 == 0 and scroll_i > 0:
                log.info(f"  🔄 Scroll {scroll_i}/{max_scrolls}, {len(arts)} links so far…")
    except Exception as e:
        log.warning(f"  ⚠️ Scroll error in {cat_name}: {e.__class__.__name__}")
    log.info(f"  ✅ {len(arts)} links in {cat_name}"); return arts

def scrape_article(driver, url, category="", target_date=None):
    for attempt in range(3):
        try:
            driver.get(url)
            WebDriverWait(driver,20).until(EC.presence_of_element_located((By.CSS_SELECTOR,"h1")))
            time.sleep(1)
            # Title
            title=""
            try: title=driver.find_element(By.CSS_SELECTOR,"h1").text.strip()
            except:
                try: title=driver.find_element(By.CSS_SELECTOR,"meta[property='og:title']").get_attribute("content").strip()
                except: title=driver.title.strip()
            if not title: return None
            # Description
            desc=""
            for s in ["meta[property='og:description']","meta[name='description']"]:
                try: desc=driver.find_element(By.CSS_SELECTOR,s).get_attribute("content").strip(); break
                except: continue
            if not desc:
                try: desc=" ".join(p.text.strip() for p in driver.find_elements(By.CSS_SELECTOR,"article p, [class*='content'] p")[:5] if len(p.text.strip())>20)
                except: pass
            desc=re.sub(r"<[^>]+>","",desc).strip()[:2000]
            # Image
            img=""
            try: img=driver.find_element(By.CSS_SELECTOR,"meta[property='og:image']").get_attribute("content").strip()
            except:
                try:
                    for el in driver.find_elements(By.CSS_SELECTOR,"article img, picture img"):
                        src=el.get_attribute("src") or el.get_attribute("data-src") or ""
                        if src and not src.startswith("data:"): img=src; break
                except: pass
            if img and not img.startswith("http"): img=urljoin(BASE_URL,img)
            # Extract category from article page tags
            page_cat = ""
            try:
                for bc in driver.find_elements(By.CSS_SELECTOR,"[class*='tag'] a, [class*='category'] a, [class*='breadcrumb'] a"):
                    t=bc.text.strip()
                    if t and t not in ("winwin","الرئيسية","") and len(t)>1:
                        page_cat = t; break
            except: pass
            # Translate to English: prefer page tag, fallback to listing category
            raw_cat = page_cat or category or ""
            final_cat = translate_category(raw_cat)
            # Get date from article page
            dt = ""
            try:
                dt=driver.find_element(By.CSS_SELECTOR,"time").text.strip()
            except: pass
            # Get the date text
            article_date = dt if dt else date_to_ar(target_date)
            log.info(f"  ✅ [{final_cat}] {title[:50]}…")
            return {"title":title,"description":desc,"image_url":img,"date":article_date,"category":final_cat}
        except InvalidSessionIdException:
            log.warning(f"  💀 Session dead at attempt {attempt+1}, need new driver")
            raise
        except Exception as e:
            log.warning(f"  ⚠️ Attempt {attempt+1}: {e.__class__.__name__}")
            if attempt<2: time.sleep(2)
    return None

def save_to_csv(data):
    fields=["title","description","image_url","date","category"]
    with open(OUTPUT,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields,quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in data:
            w.writerow({k:" ".join(re.sub(r"<[^>]+>","",str(r.get(k,""))).split()) for k in fields})
    log.info(f"💾 {len(data)} articles → {OUTPUT}")

def parse_args():
    p=argparse.ArgumentParser(description="Scrape winwin.com articles for a specific date.")
    p.add_argument("--date","-d",type=str,default=None,
        help="Target date in YYYY-MM-DD format (default: today). Example: --date 2026-04-07")
    args=p.parse_args()
    if args.date:
        try: return datetime.strptime(args.date,"%Y-%m-%d").date()
        except ValueError:
            print(f"❌ Invalid date format: {args.date}. Use YYYY-MM-DD."); sys.exit(1)
    return date.today()

def main():
    target_date=parse_args()
    t0=time.time()
    log.info(f"🚀 winwin.com Scraper | Target date: {target_date} ({date_to_ar(target_date)})")
    driver=setup_driver(); links=[]; seen=set()
    try:
        for c in get_categories(driver):
            try:
                for l in get_article_links(driver,c["url"],c["name"],target_date):
                    if l["url"] not in seen: seen.add(l["url"]); links.append(l)
            except Exception as e:
                log.warning(f"⚠️ Category {c['name']} failed: {e.__class__.__name__}, recreating driver…")
                try: driver.quit()
                except: pass
                driver=setup_driver()
    finally:
        try: driver.quit()
        except: pass
    log.info(f"📊 {len(links)} unique links")
    results=[]; seen_t=set(); driver=setup_driver()
    try:
        for i,info in enumerate(links,1):
            log.info(f"[{i}/{len(links)}]")
            try:
                a=scrape_article(driver,info["url"],info.get("category",""),target_date)
                if a and a["title"] not in seen_t: seen_t.add(a["title"]); results.append(a)
            except (InvalidSessionIdException, WebDriverException):
                log.warning(f"💀 Driver died, recreating…")
                try: driver.quit()
                except: pass
                driver=setup_driver()
                try:
                    a=scrape_article(driver,info["url"],info.get("category",""),target_date)
                    if a and a["title"] not in seen_t: seen_t.add(a["title"]); results.append(a)
                except: pass
            except Exception as e:
                log.warning(f"⚠️ Skipping article: {e.__class__.__name__}")
    finally:
        try: driver.quit()
        except: pass
    save_to_csv(results)
    log.info(f"🏁 Done in {time.time()-t0:.1f}s — {len(results)} articles")

if __name__=="__main__":
    main()
