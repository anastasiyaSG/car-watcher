import requests
from bs4 import BeautifulSoup
import json
import os
import smtplib
from email.mime.text import MIMEText

NISSAN_URL = "https://www.omnicar.nissan.bg/catalog"
KIA_URL = "https://kia.bg/bg/used-cars"

SMTP_SERVER = "smtp.mailjet.com"
SMTP_PORT = 587

SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

EMAIL_FROM = "watcher@cars.com"
EMAIL_TO = os.getenv("EMAIL_TO").split(",")


def load_storage():
    with open("storage.json") as f:
        return json.load(f)


def save_storage(data):
    with open("storage.json", "w") as f:
        json.dump(data, f, indent=2)


def send_email(new_cars):

    if not new_cars:
        return

    body = "🚗 New car listings found:\n\n"

    for car in new_cars:
        body += f"{car['title']}\n"
        body += f"Price: {car['price']}\n"
        body += f"Link: {car['link']}\n\n"

    msg = MIMEText(body)
    msg["Subject"] = "🚗 New car listings detected"
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())


def parse_nissan():

    cars = []

    r = requests.get(NISSAN_URL, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("a")

    for a in items:

        href = a.get("href")

        if href and "/car/" in href:

            title = a.get_text(strip=True)

            price = "unknown"

            cars.append({
                "id": href,
                "title": title,
                "price": price,
                "link": "https://www.omnicar.nissan.bg" + href
            })

    return cars


def parse_kia():

    cars = []

    r = requests.get(KIA_URL, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("a")

    for a in items:

        href = a.get("href")

        if href and "/used-car" in href:

            title = a.get_text(strip=True)

            price = "unknown"

            cars.append({
                "id": href,
                "title": title,
                "price": price,
                "link": "https://kia.bg" + href
            })

    return cars


def main():

    storage = load_storage()

    new_cars = []

    nissan_cars = parse_nissan()
    kia_cars = parse_kia()

    for car in nissan_cars:
        if car["id"] not in storage["nissan"]:
            storage["nissan"].append(car["id"])
            new_cars.append(car)

    for car in kia_cars:
        if car["id"] not in storage["kia"]:
            storage["kia"].append(car["id"])
            new_cars.append(car)

    save_storage(storage)

    send_email(new_cars)


if __name__ == "__main__":
    main()