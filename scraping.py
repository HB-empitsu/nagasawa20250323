import re
import unicodedata
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


def fetch_soup(url, parser="html5lib"):
    r = requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, parser)

    return soup


def fetch_hinanjo(url, ts_data):
    soup = fetch_soup(url)

    tag = soup.find(string=re.compile(r"^補足情報"))
    information = (
        unicodedata.normalize("NFKC", tag.parent.get_text(strip=True)).replace("。", "。  \n").strip() if tag else ""
    )

    data = []

    col_name = [
        "日付",
        "避難所名",
        "開設状況",
        "収容人数",
        "避難世帯数",
        "避難人数",
        "緯度",
        "経度",
        "所在地",
        "電話番号",
    ]

    for tr in soup.select("table.listViewTable > tbody > tr"):
        tds = tr.select("td")

        if len(tds) == 8:
            td = [i.get_text(strip=True) for i in tds]

            link = tds[3].select_one("a")

            text = link.get("onclick") or link.get("href")

            pattern = r"lat=([0-9.]+)&lng=([0-9.]+)"
            match = re.search(pattern, text)

            if match:
                lat = match.group(1)
                lng = match.group(2)

                td.append(lat)
                td.append(lng)
            else:
                print("No match found")

            data.append(td)

    if data:
        df = pd.DataFrame(
            data,
            columns=[
                "避難所名",
                "開設状況",
                "所在地",
                "地図",
                "電話番号",
                "収容人数",
                "避難世帯数",
                "避難人数",
                "緯度",
                "経度",
            ],
        )

        df = df.drop("地図", axis=1).astype({"収容人数": int, "緯度": float, "経度": float})

        df["避難世帯数"] = pd.to_numeric(df["避難世帯数"], errors="coerce").fillna(0).astype(int)
        df["避難人数"] = pd.to_numeric(df["避難人数"], errors="coerce").fillna(0).astype(int)

        df["日付"] = ts_date

        df = df.reindex(columns=col_name)

    else:
        df = pd.DataFrame(columns=col_name)

    return df, information


url = "https://city-imabari.my.salesforce-sites.com/K_PUB_VF_HinanjyoList"

soup = fetch_soup(url)

dfs = []
data = []

for tag in soup.select("div.volunteer > dl")[::-1]:
    dt = tag.select_one("dt").get_text(strip=True)
    date, title = [i.get_text(strip=True) for i in tag.select("dd > p")]

    title = title.replace("今治市 避難所情報 :", "")

    if "今治市長沢林野火災" in title:
        status = "".join(dt.split())

        href = tag.select_one("a").get("href")
        link = urljoin(url, href)

        ts_date = pd.to_datetime(date, errors="coerce")

        df, information = fetch_hinanjo(link, ts_date)

        d = {"title": title, "status": status, "date": ts_date, "link": link, "information": information}

        data.append(d)

        if not df.empty:
            dfs.append(df)

df_info = pd.DataFrame(data)
df_info.to_csv("info.csv", encoding="utf_8_sig", index=False)

df_data = pd.concat(dfs, ignore_index=True)
df_data.to_csv("data.csv", encoding="utf_8_sig", index=False)
