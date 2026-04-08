#!/usr/bin/env python3
import csv, logging, re, sys, time
from datetime import date
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

def today_ar():
    t=date.today(); return f"{t.day} {M2AR[t.month]} {t.year}"

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

def get_article_links(driver, url, cat_name=""):
    log.info(f"📰 Collecting from: {cat_name}")
    tday=today_ar(); arts=[]; seen=set()
    try:
        driver.get(url)
        WebDriverWait(driver,20).until(EC.presence_of_element_located((By.TAG_NAME,"body")))
        time.sleep(3)
    except Exception as e:
        log.warning(f"  ⚠️ Failed to load {cat_name}: {e.__class__.__name__}"); return arts
    try:
        last_h=driver.execute_script("return document.body.scrollHeight"); stale=0
        for _ in range(25):
            for a in driver.find_elements(By.CSS_SELECTOR,"a[href]"):
                try:
                    h=a.get_attribute("href")
                    if not h or h in seen: continue
                    dec=unquote(h)
                    if "/الأخبار/" not in dec: continue
                    if tday in (a.text or ""):
                        seen.add(h); arts.append({"url":h,"category":cat_name})
                except: continue
            driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
            time.sleep(2)
            nh=driver.execute_script("return document.body.scrollHeight")
            if nh==last_h:
                stale+=1
                if stale>=3: break
            else: stale=0
            last_h=nh
    except Exception as e:
        log.warning(f"  ⚠️ Scroll error in {cat_name}: {e.__class__.__name__}")
    log.info(f"  ✅ {len(arts)} links in {cat_name}"); return arts

def scrape_article(driver, url, category=""):
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
            # Date check
            try:
                dt=driver.find_element(By.CSS_SELECTOR,"time").text.strip()
                if dt and today_ar() not in dt:
                    log.info(f"  ⏭️ Not today: {title[:40]}…"); return None
            except: pass
            log.info(f"  ✅ [{final_cat}] {title[:50]}…")
            return {"title":title,"description":desc,"image_url":img,"category":final_cat}
        except InvalidSessionIdException:
            log.warning(f"  💀 Session dead at attempt {attempt+1}, need new driver")
            raise
        except Exception as e:
            log.warning(f"  ⚠️ Attempt {attempt+1}: {e.__class__.__name__}")
            if attempt<2: time.sleep(2)
    return None

def save_to_csv(data):
    fields=["title","description","image_url","category"]
    with open(OUTPUT,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields,quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in data:
            w.writerow({k:" ".join(re.sub(r"<[^>]+>","",str(r.get(k,""))).split()) for k in fields})
    log.info(f"💾 {len(data)} articles → {OUTPUT}")

def main():
    t0=time.time()
    log.info(f"🚀 winwin.com Scraper | Today: {date.today()} ({today_ar()})")
    driver=setup_driver(); links=[]; seen=set()
    try:
        for c in get_categories(driver):
            try:
                for l in get_article_links(driver,c["url"],c["name"]):
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
                a=scrape_article(driver,info["url"],info.get("category",""))
                if a and a["title"] not in seen_t: seen_t.add(a["title"]); results.append(a)
            except (InvalidSessionIdException, WebDriverException):
                log.warning(f"💀 Driver died, recreating…")
                try: driver.quit()
                except: pass
                driver=setup_driver()
                try:
                    a=scrape_article(driver,info["url"],info.get("category",""))
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
