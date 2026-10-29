import os
import re
import time
import threading
from collections import Counter
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

REGISTRATION = os.getenv("REGISTRATION", "FA23-BDS-002")
NEWSSOURCE = "The News International Pakistan"
DOMAIN = "thenews.com.pk"
ARTICLE_RE = re.compile(r"thenews\.com\.pk/(latest|print|tns|magazine|world|sports)/\d+")

app = Flask(__name__)
lock = threading.Lock()

STOP = set("""a an the and or but if of to in on at for with by from as is are was were be been it its this
that these those he she they we you i his her their our your not no so than then also has have had will
would can could said says say after before over into about more most other which who whom what when where
""".split())


def make_driver():
    opts = Options()
    opts.binary_location = "/usr/bin/google-chrome"
    for a in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
              "--disable-gpu", "--window-size=1366,768",
              "--disable-blink-features=AutomationControlled"):
        opts.add_argument(a)
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    drv = webdriver.Chrome(service=Service("/usr/local/bin/chromedriver"), options=opts)
    drv.set_page_load_timeout(40)
    ua = drv.execute_script("return navigator.userAgent").replace("HeadlessChrome", "Chrome")
    drv.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": ua})
    drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"})
    return drv


def links_from_page(drv):
    out = []
    for a in drv.find_elements(By.TAG_NAME, "a"):
        href = a.get_attribute("href") or ""
        if ARTICLE_RE.search(href) and href not in out:
            out.append(href)
    return out


def first_result(drv, keyword):
    q = quote_plus(keyword)
    for url in (f"https://www.{DOMAIN}/search?q={q}",
                f"https://www.{DOMAIN}/search/{q}"):
        try:
            drv.get(url)
            time.sleep(4)
            found = links_from_page(drv)
            if found:
                return found[0], ""
        except Exception:
            pass
    drv.get(f"https://html.duckduckgo.com/html/?q=site%3A{DOMAIN}+{q}")
    time.sleep(2)
    for r in drv.find_elements(By.CSS_SELECTOR, "div.result"):
        try:
            a = r.find_element(By.CSS_SELECTOR, "a.result__a")
        except Exception:
            continue
        href = a.get_attribute("href") or ""
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
        if DOMAIN in href:
            try:
                snip = r.find_element(By.CSS_SELECTOR, ".result__snippet").text
            except Exception:
                snip = ""
            return href, snip
    return None, ""


def article_text(drv, url):
    drv.get(url)
    time.sleep(3)
    paras = [p.text.strip() for p in drv.find_elements(By.TAG_NAME, "p")]
    return " ".join(p for p in paras if len(p) > 40)


def summarize(text, n=3):
    sents = re.split(r"(?<=[.!?])\s+", text)
    sents = [s for s in sents if len(s.split()) > 6]
    if len(sents) <= n:
        return " ".join(sents)
    words = [w for w in re.findall(r"[a-z']+", text.lower()) if w not in STOP]
    freq = Counter(words)
    scores = {}
    for i, s in enumerate(sents):
        toks = [w for w in re.findall(r"[a-z']+", s.lower()) if w not in STOP]
        if toks:
            scores[i] = sum(freq[w] for w in toks) / len(toks)
    top = sorted(sorted(scores, key=scores.get, reverse=True)[:n])
    return " ".join(sents[i] for i in top)


@app.route("/")
def home():
    return (f"<h1>Registration: {REGISTRATION}</h1>"
            f"<p>News source: {NEWSSOURCE}</p>"
            f"<p>Try <a href='/get?keyword=pakistan'>/get?keyword=pakistan</a></p>")


@app.route("/get")
def get():
    keyword = request.args.get("keyword", "").strip()
    resp = {"registration": REGISTRATION, "newssource": NEWSSOURCE,
            "keyword": keyword, "url": "", "summary": ""}
    if not keyword:
        resp["summary"] = "Missing 'keyword' query parameter."
        return jsonify(resp), 400
    with lock:
        drv = None
        try:
            drv = make_driver()
            url, snip = first_result(drv, keyword)
            if not url:
                resp["summary"] = "No result found."
                return jsonify(resp), 404
            resp["url"] = url
            text = article_text(drv, url)
            summary = summarize(text)
            blocked = "security service" in text.lower() or len(text) < 300
            if blocked or not summary:
                title = url.rstrip("/").split("/")[-1].split("-", 1)[-1].replace("-", " ").title()
                summary = f"{title}. {snip}".strip()
            resp["summary"] = summary
        except Exception as e:
            resp["summary"] = f"Error: {e}"
            return jsonify(resp), 500
        finally:
            if drv:
                drv.quit()
    return jsonify(resp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)
