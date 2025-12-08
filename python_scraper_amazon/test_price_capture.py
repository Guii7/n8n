"""
Teste rápido para verificar captura de preços
"""
import os
import re
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import json

load_dotenv()

def parse_price(price_text):
    if not price_text:
        return None
    try:
        price_clean = price_text.replace('R$', '').replace(' ', '').replace('\xa0', '').strip()
        price_clean = price_clean.replace('.', '').replace(',', '.')
        return float(price_clean)
    except:
        return None

# Carregar sessão
session_path = 'puppeteer_session/amazon_session.json'
with open(session_path, 'r') as f:
    session_data = json.load(f)

# URL de teste
test_url = "https://www.amazon.com.br/Apple-iPhone-15-128-GB/dp/B0CP6CVJSG"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )

    # Carregar cookies
    context.add_cookies(session_data['cookies'])

    page = context.new_page()
    page.goto(test_url, wait_until='domcontentloaded')
    time.sleep(3)

    print("="*60)
    print("TESTE DE CAPTURA DE PREÇOS")
    print("="*60)
    print(f"URL: {test_url}")
    print("")

    # Testar seletores de preço promocional
    selectors_promo = [
        'span.priceToPay span.a-offscreen',
        'span.reinventPricePriceToPayMargin span.a-offscreen',
        '#corePrice_feature_div span.a-offscreen',
        '#corePriceDisplay_desktop_feature_div span.a-offscreen',
        'span.a-price span.a-offscreen',  # Mais genérico
    ]

    print("PREÇO PROMOCIONAL:")

    # Tentar pegar via estrutura completa (whole + fraction)
    whole = page.query_selector('span.priceToPay span.a-price-whole')
    fraction = page.query_selector('span.priceToPay span.a-price-fraction')
    if whole and fraction:
        whole_text = whole.inner_text().replace(',', '').replace('.', '')
        fraction_text = fraction.inner_text()
        price_text = f"R$ {whole_text},{fraction_text}"
        price = parse_price(price_text)
        print(f"  ✅ Via whole+fraction: {price_text} = R${price}")
    else:
        # Fallback para offscreen
        for sel in selectors_promo:
            elem = page.query_selector(sel)
            if elem:
                text = elem.inner_text()
                if text.strip():
                    price = parse_price(text)
                    print(f"  ✅ {sel}")
                    print(f"      Texto: {text}")
                    print(f"      Valor: R${price}")
                    break
            print(f"  ❌ {sel} - não encontrado ou vazio")

    print("")

    # Testar seletores de preço original
    selectors_list = [
        'span.a-price.a-text-price[data-a-strike="true"] span.a-offscreen',
        '.basisPrice span.a-offscreen',
        'span.a-text-price span.a-offscreen',
    ]

    print("PREÇO ORIGINAL:")
    for sel in selectors_list:
        elem = page.query_selector(sel)
        if elem:
            text = elem.inner_text()
            price = parse_price(text)
            print(f"  ✅ {sel}")
            print(f"      Texto: {text}")
            print(f"      Valor: R${price}")
            break
        else:
            print(f"  ❌ {sel} - não encontrado")

    print("")

    # Parcelamento
    print("PARCELAMENTO:")
    installment = page.query_selector('#best-offer-string-cc')
    if installment:
        print(f"  ✅ {installment.inner_text()}")
    else:
        print("  ❌ Não encontrado")

    print("")

    # Frete
    print("FRETE:")
    shipping = page.query_selector('span[data-csa-c-delivery-price]')
    if shipping:
        price = shipping.get_attribute('data-csa-c-delivery-price')
        time_delivery = shipping.get_attribute('data-csa-c-delivery-time')
        print(f"  ✅ {price} - {time_delivery}")
    else:
        print("  ❌ Não encontrado")

    print("")

    # Promoções
    print("PROMOÇÕES:")
    promo = page.query_selector('span.promoPriceBlockMessage')
    if promo:
        divs = promo.query_selector_all('div[style*="padding"]')
        for i, div in enumerate(divs):
            badge = div.query_selector('label[id^="greenBadge"]')
            msg = div.query_selector('span[id^="promoMessage"]')
            text = ""
            if badge:
                text += badge.inner_text() + " "
            if msg:
                text += msg.inner_text()
            if text.strip():
                print(f"  ✅ Promo {i+1}: {text[:80]}...")
    else:
        print("  ❌ Não encontrado")

    browser.close()

print("")
print("="*60)
print("TESTE CONCLUÍDO")
print("="*60)
