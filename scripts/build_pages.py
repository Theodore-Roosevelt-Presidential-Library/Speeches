"""Render the HTML pages from templates/ with the shared header and footer."""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAV = [("index.html", "Explore"), ("phrases.html", "Phrases"), ("words.html", "Words"), ("map.html", "Map"),
       ("themes.html", "Themes"), ("about.html", "About"), ("api.html", "API &amp; data")]

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{ogtitle}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:url" content="https://speeches.labs.trlibrary.com/{page}">
<meta property="og:site_name" content="Theodore Roosevelt Presidential Library">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@600;700&family=Lora:ital,wght@0,400;0,700;1,400&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/app.css">
{extra_head}</head>
<body>
<header class="bar">
  <a class="brand" href="index.html"><b>Speeches</b>Theodore Roosevelt Presidential Library</a>
  <nav>{nav}</nav>
</header>
"""
FOOT = """
<footer class="site">
  <div class="wrap">
    Texts come from editions printed in Roosevelt's lifetime and are shown as printed. Every speech links to the original document at the Theodore Roosevelt Center at Dickinson State University or the Library of Congress where one is known. Check the original before quoting.
    <a href="about.html">About the sources</a> &nbsp;|&nbsp; <a href="https://daybyday.labs.trlibrary.com/">Theodore Roosevelt Day by Day</a> &nbsp;|&nbsp; <a href="https://www.trlibrary.com/visit">Plan your visit to the Library in Medora</a>
  </div>
</footer>
<script src="assets/app.js"></script>
{script}
</body>
</html>
"""


def main():
    tdir = os.path.join(ROOT, "templates")
    for fn in sorted(os.listdir(tdir)):
        if not fn.endswith(".html"):
            continue
        src = open(os.path.join(tdir, fn), encoding="utf-8").read()
        meta = dict(re.findall(r"<!--\s*(\w+):\s*(.*?)\s*-->", src.split("\n\n", 1)[0]))
        body = src.split("<!--BODY-->", 1)[1]
        script = ""
        if "<!--SCRIPT-->" in body:
            body, script = body.split("<!--SCRIPT-->", 1)
        extra = ""
        if "<!--HEAD-->" in body:
            extra, body = body.split("<!--HEAD-->", 1)
        nav = "".join(f'<a href="{h}"{" aria-current=\"page\"" if h == fn or (fn == "speech.html" and h == "index.html") else ""}>{t}</a>' for h, t in NAV)
        html = HEAD.format(title=meta.get("title", "Theodore Roosevelt's Speeches") + " | Theodore Roosevelt Presidential Library",
                           ogtitle=meta.get("title", "Theodore Roosevelt's Speeches"), desc=meta.get("desc", ""), page="" if fn == "index.html" else fn,
                           nav=nav, extra_head=extra.strip() + "\n" if extra.strip() else "")
        html += body.strip() + "\n" + FOOT.format(script=script.strip())
        open(os.path.join(ROOT, fn), "w", encoding="utf-8").write(html)
        print("wrote", fn)


if __name__ == "__main__":
    main()
