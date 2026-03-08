import asyncio
import json
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()


def load_storage():
    """Load existing storage.json"""
    try:
        with open("storage.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_scraped": None, "total_cars": 0, "nissan_count": 0, "kia_count": 0, "cars": []}


def save_storage(data):
    """Save storage.json"""
    with open("storage.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

NISSAN_URL = "https://www.omnicar.nissan.bg/catalog"
KIA_URL = "https://kia.bg/bg/used-cars"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_FROM = os.getenv("SMTP_USER")
EMAIL_TO = os.getenv("EMAIL_TO", "").split(",")


def send_email(new_cars):
    """Send email with only NEW cars (not previously seen)"""
    if not new_cars:
        print("✅ No new cars found - email not sent")
        return

    body = "🚗 NEW CAR LISTINGS FOUND\n"
    body += "=" * 70 + "\n\n"
    body += f"New cars found: {len(new_cars)}\n"
    body += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    nissan_cars = [c for c in new_cars if c.get("source") == "nissan"]
    kia_cars = [c for c in new_cars if c.get("source") == "kia"]

    if nissan_cars:
        body += f"\n📍 NEW NISSAN CARS ({len(nissan_cars)})\n"
        body += "=" * 70 + "\n"
        for i, car in enumerate(nissan_cars, 1):
            body += f"\n{i}. {car['title']}\n"
            price = car.get('price', 'N/A')
            body += f"   💰 Price: {price}\n"
            body += f"   🔗 Link: {car['link']}\n"

    if kia_cars:
        body += f"\n\n📍 NEW KIA CARS ({len(kia_cars)})\n"
        body += "=" * 70 + "\n"
        for i, car in enumerate(kia_cars, 1):
            body += f"\n{i}. {car['title']}\n"
            price = car.get('price', 'N/A')
            body += f"   💰 Price: {price}\n"
            body += f"   🔗 Link: {car['link']}\n"

    msg = MIMEText(body)
    msg["Subject"] = f"🚗 NEW CARS FOUND: {len(new_cars)} new listings"
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"✅ Email sent successfully to {EMAIL_TO}")
        print(f"   New cars sent: {len(new_cars)}")
        print(f"   Nissan: {len(nissan_cars)}")
        print(f"   Kia: {len(kia_cars)}")
    except Exception as e:
        print(f"❌ Email failed: {e}")


async def scrape_nissan(page):
    """Scrape all Nissan cars from all pages using Playwright"""
    cars = []
    
    try:
        print("🔍 Scraping Nissan...")
        page_num = 1
        base_url = NISSAN_URL
        
        while True:
            print(f"   📄 Page {page_num}...")
            await page.goto(base_url if page_num == 1 else f"{base_url}?page={page_num}", timeout=30000)
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(1)
            
            # Extract cars from current page - each car is in an <article> element
            car_articles = await page.query_selector_all("article")
            
            if not car_articles:
                print(f"   ✅ No more cars found on page {page_num}. Total: {len(cars)}")
                break
            
            page_cars = 0
            for article in car_articles:
                try:
                    # Get title from the h3 link
                    title_link = await article.query_selector("a.h3[href*='/catalog/']")
                    if not title_link:
                        title_link = await article.query_selector("a[href*='/catalog/']:not(.btn-primary)")
                    
                    if not title_link:
                        continue
                    
                    href = await title_link.get_attribute("href")
                    title = await title_link.text_content()
                    
                    if not href or not title.strip():
                        continue
                    
                    # Get prices (euro and BGN)
                    price_elements = await article.query_selector_all("div.price div.h3")
                    price = "N/A"
                    if price_elements:
                        price_texts = []
                        for price_elem in price_elements:
                            price_text = await price_elem.text_content()
                            if price_text:
                                price_texts.append(price_text.strip())
                        if price_texts:
                            price = " / ".join(price_texts)
                    
                    car_obj = {
                        "id": href,
                        "title": " ".join(title.strip().split()),  # Clean up extra whitespace
                        "price": price,
                        "link": "https://www.omnicar.nissan.bg" + href if not href.startswith("http") else href,
                        "source": "nissan",
                        "scraped_date": datetime.now().isoformat()
                    }
                    
                    # Check for duplicates by ID
                    if not any(c["id"] == car_obj["id"] for c in cars):
                        cars.append(car_obj)
                        page_cars += 1
                
                except Exception as item_err:
                    continue
            
            if page_cars == 0:
                print(f"   ✅ No new cars on page {page_num}. Total: {len(cars)}")
                break
            
            print(f"   ✓ Found {page_cars} cars on page {page_num}")
            page_num += 1
            
            if page_num > 20:  # Safety limit
                print(f"   ⚠️  Reached page limit (20). Total: {len(cars)}")
                break
        
        print(f"✅ Nissan complete: {len(cars)} cars")
        return cars
    
    except Exception as e:
        print(f"❌ Nissan scraping error: {e}")
        return cars


async def scrape_kia(page):
    """Scrape all Kia cars from all pages using Playwright"""
    cars = []
    
    try:
        print("🔍 Scraping Kia...")
        page_num = 1
        base_url = KIA_URL
        
        while True:
            print(f"   📄 Page {page_num}...")
            url = base_url if page_num == 1 else f"{base_url}?page={page_num}"
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(1)
            
            # Extract cars from current page using correct selectors
            car_items = await page.query_selector_all("li.products__item-large")
            
            if not car_items:
                print(f"   ✅ No more cars found on page {page_num}. Total: {len(cars)}")
                break
            
            page_cars = 0
            for item in car_items:
                try:
                    # Get title
                    title_elem = await item.query_selector("h3")
                    title = await title_elem.text_content() if title_elem else "N/A"
                    
                    # Get price
                    price_elem = await item.query_selector("strong")
                    price = await price_elem.text_content() if price_elem else "N/A"
                    
                    # Get link
                    link_elem = await item.query_selector("a[href*='/used-cars/']")
                    href = await link_elem.get_attribute("href") if link_elem else None
                    
                    if href and title.strip() != "N/A":
                        car_obj = {
                            "id": href,
                            "title": title.strip(),
                            "price": price.strip() if price != "N/A" else "N/A",
                            "link": "https://kia.bg" + href,
                            "source": "kia",
                            "scraped_date": datetime.now().isoformat()
                        }
                        
                        if car_obj not in cars:  # Avoid duplicates
                            cars.append(car_obj)
                            page_cars += 1
                except Exception as item_err:
                    print(f"      Warning: Could not extract car item: {item_err}")
                    continue
            
            if page_cars == 0:
                print(f"   ✅ No new cars on page {page_num}. Total: {len(cars)}")
                break
            
            print(f"   ✓ Found {page_cars} cars on page {page_num}")
            page_num += 1
            
            if page_num > 20:  # Safety limit
                print(f"   ⚠️  Reached page limit (20). Total: {len(cars)}")
                break
        
        print(f"✅ Kia complete: {len(cars)} cars")
        return cars
    
    except Exception as e:
        print(f"❌ Kia scraping error: {e}")
        return cars


async def main():
    print("🚀 Starting Playwright Car Scraper")
    print("=" * 70)
    
    # Check environment variables
    if not SMTP_USER or not SMTP_PASS:
        print("❌ ERROR: SMTP credentials not set in .env")
        return
    if not EMAIL_TO or EMAIL_TO == ['']:
        print("❌ ERROR: EMAIL_TO not set in .env")
        return
    
    print(f"✅ Configuration loaded:")
    print(f"   SMTP User: {SMTP_USER}")
    print(f"   Recipients: {EMAIL_TO}")
    print("=" * 70)
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        
        # Create context for scraping
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        nissan_page = await context.new_page()
        kia_page = await context.new_page()
        
        # Scrape both sites concurrently
        nissan_cars, kia_cars = await asyncio.gather(
            scrape_nissan(nissan_page),
            scrape_kia(kia_page)
        )
        
        await nissan_page.close()
        await kia_page.close()
        await browser.close()
    
    # Combine all cars
    all_cars = nissan_cars + kia_cars
    
    print("=" * 70)
    print(f"📊 Scraping Summary:")
    print(f"   Nissan: {len(nissan_cars)} cars")
    print(f"   Kia: {len(kia_cars)} cars")
    print(f"   Total scraped: {len(all_cars)} cars")
    print("=" * 70)
    
    # Load existing storage
    existing_storage = load_storage()
    existing_ids = {car["id"] for car in existing_storage.get("cars", [])}
    
    print(f"\n📊 Storage Comparison:")
    print(f"   Previously stored: {len(existing_ids)} cars")
    
    # Find new cars (not in existing storage)
    new_cars = [car for car in all_cars if car["id"] not in existing_ids]
    
    print(f"   New cars found: {len(new_cars)} cars")
    print(f"   Duplicates skipped: {len(all_cars) - len(new_cars)} cars")
    print("=" * 70)
    
    # Update storage with new cars
    if new_cars:
        updated_cars = existing_storage.get("cars", []) + new_cars
        updated_storage = {
            "last_scraped": datetime.now().isoformat(),
            "total_cars": len(updated_cars),
            "nissan_count": len([c for c in updated_cars if c.get("source") == "nissan"]),
            "kia_count": len([c for c in updated_cars if c.get("source") == "kia"]),
            "cars": updated_cars
        }
        save_storage(updated_storage)
        print(f"✅ Saved {len(new_cars)} NEW cars to storage.json")
        print(f"   Total cars in storage: {len(updated_cars)}")
        
        # Send email with new cars only
        print("\n📧 Sending email with NEW cars...")
        send_email(new_cars)
    else:
        print(f"⚠️  No new cars found - storage not updated, email not sent")
        print(f"   Next check will compare against {len(existing_ids)} stored cars")
    
    print("=" * 70)
    print("✅ Complete!")


if __name__ == "__main__":
    asyncio.run(main())
