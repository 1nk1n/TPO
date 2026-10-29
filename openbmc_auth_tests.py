import os
import re
import time
import base64
import json
import ssl
import urllib.error
import urllib.request

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BMC_URL = os.getenv("OPENBMC_URL", "https://127.0.0.1:2443")
BMC_API_URL = os.getenv("OPENBMC_API_URL", "https://127.0.0.1:2443")
BMC_USER = os.getenv("OPENBMC_USERNAME", "root")
BMC_PASSWORD = os.getenv("OPENBMC_PASSWORD", "0penBmc")


def make_driver():
    options = webdriver.ChromeOptions()
    options.accept_insecure_certs = True
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--window-size=1440,1000")
    if os.getenv("HEADLESS", "0") == "1":
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def first_visible(driver, locators, timeout=10):
    wait = WebDriverWait(driver, timeout)
    for locator in locators:
        try:
            return wait.until(EC.visibility_of_element_located(locator))
        except TimeoutException:
            continue
    raise AssertionError(f"Не найден видимый элемент: {locators}")


def set_basic_auth(driver, username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd(
        "Network.setExtraHTTPHeaders",
        {"headers": {"Authorization": f"Basic {token}"}},
    )


def login(driver, username, password):
    driver.get(BMC_URL)
    if not driver.find_elements(By.CSS_SELECTOR, "input[type='password']"):
        set_basic_auth(driver, username, password)
        driver.get(BMC_URL.rstrip("/") + "/redfish/v1/Systems")
        return "basic"
    user = first_visible(
        driver,
        [
            (By.CSS_SELECTOR, "input[name='username']"),
            (By.CSS_SELECTOR, "input#username"),
            (By.CSS_SELECTOR, "input[autocomplete='username']"),
            (By.CSS_SELECTOR, "input[placeholder*='ser' i]"),
            (By.CSS_SELECTOR, "input[type='text']"),
        ],
    )
    secret = first_visible(
        driver,
        [
            (By.CSS_SELECTOR, "input[name='password']"),
            (By.CSS_SELECTOR, "input#password"),
            (By.CSS_SELECTOR, "input[type='password']"),
        ],
    )
    user.clear()
    user.send_keys(username)
    secret.clear()
    secret.send_keys(password)
    button = first_visible(
        driver,
        [
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.CSS_SELECTOR, "input[type='submit']"),
            (By.XPATH, "//button[contains(translate(., 'LOGIN', 'login'), 'login') or contains(translate(., 'ВХОД', 'вход'), 'вход')]") ,
            (By.XPATH, "//button"),
        ],
    )
    button.click()
    return "form"


def page_text(driver):
    return driver.find_element(By.TAG_NAME, "body").text.lower()


def redfish_request(path, method="GET", payload=None, username=BMC_USER, password=BMC_PASSWORD):
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        BMC_API_URL.rstrip("/") + path,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Basic "
            + base64.b64encode(f"{username}:{password}".encode()).decode(),
        },
    )
    context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request, context=context, timeout=15) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"raw": raw}
        return error.code, data


def login_api(username, password):
    status, data = redfish_request(
        "/login", method="POST", payload={"username": username, "password": password}
    )
    return status, data


def wait_for_webui(driver):
    WebDriverWait(driver, 20).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, "input[type='password']")) == 0
        or bool(re.search(r"overview|dashboard|system information", page_text(d)))
    )


def click_text(driver, phrases, timeout=10):
    lowered = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    upper = "abcdefghijklmnopqrstuvwxyz"
    predicates = " or ".join(
        f"contains(translate(normalize-space(.), '{lowered}', '{upper}'), '{phrase.lower()}')"
        for phrase in phrases
    )
    locator = (By.XPATH, f"//*[self::button or self::a or @role='button'][{predicates}]")
    element = first_visible(driver, [locator], timeout=timeout)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    element.click()
    return element


def test_successful_authorization():
    driver = make_driver()
    try:
        mode = login(driver, BMC_USER, BMC_PASSWORD)
        wait_for_webui(driver)
        text = page_text(driver)
        assert not re.search(r"invalid|incorrect|unauthori[sz]ed|failed", text)
        if mode == "basic":
            assert "systems" in text or "odata" in text
        else:
            assert len(driver.find_elements(By.CSS_SELECTOR, "input[type='password']")) == 0
    finally:
        driver.quit()


@pytest.mark.webui
def test_webui_inventory_visible():
    """Проверяет, что после входа Web UI показывает сведения об инвентаре."""
    driver = make_driver()
    try:
        mode = login(driver, BMC_USER, BMC_PASSWORD)
        if mode == "basic":
            pytest.skip("В образе нет Web UI, доступен только Redfish API")
        wait_for_webui(driver)
        text = page_text(driver)
        assert re.search(r"inventory|system|processor|cpu|memory|ram", text), (
            "После входа не найдены сведения об инвентаре/системе"
        )
    finally:
        driver.quit()


@pytest.mark.webui
def test_webui_power_action():
    """Выполняет доступное действие питания через Web UI и проверяет ответ."""
    driver = make_driver()
    try:
        mode = login(driver, BMC_USER, BMC_PASSWORD)
        if mode == "basic":
            pytest.skip("В образе нет Web UI, доступен только Redfish API")
        wait_for_webui(driver)
        try:
            click_text(driver, ["server control", "power control", "power"])
        except AssertionError:
            pass
        before = page_text(driver)
        action = None
        for phrases, label in [
            (["power on", "turn on"], "power on"),
            (["power off", "turn off"], "power off"),
        ]:
            try:
                click_text(driver, phrases, timeout=3)
                action = label
                break
            except AssertionError:
                continue
        assert action is not None, "В Web UI не найдена кнопка Power On/Power Off"
        time.sleep(2)
        after = page_text(driver)
        assert re.search(r"success|complete|powered|power state|running|off|on", after), (
            f"После действия {action} не найдено подтверждение результата"
        )
        assert after != before or action in after
    finally:
        driver.quit()


def test_invalid_credentials():
    driver = make_driver()
    try:
        mode = login(driver, BMC_USER, "definitely-wrong-password")
        time.sleep(2)
        text = page_text(driver)
        login_form_visible = bool(driver.find_elements(By.CSS_SELECTOR, "input[type='password']"))
        error_visible = bool(
            re.search(r"invalid|incorrect|unauthori[sz]ed|failed|error|no authentication|401", text)
        )
        assert login_form_visible or error_visible, "После неверного пароля нет признака отказа в авторизации"
    finally:
        driver.quit()


def test_account_lockout():
    """Проверяет блокировку отдельного временного пользователя через Redfish."""
    username = "selenium_lockout"
    password = "SeleniumLockout_2026!"
    account_path = f"/redfish/v1/AccountService/Accounts/{username}"
    visual_driver = None
    service_status, service = redfish_request("/redfish/v1/AccountService")
    assert service_status == 200, f"Не удалось прочитать AccountService: HTTP {service_status}"
    original_policy = {
        key: service.get(key)
        for key in (
            "AccountLockoutThreshold",
            "AccountLockoutDuration",
            "AccountLockoutCounterResetAfter",
            "AccountLockoutCounterResetEnabled",
        )
        if key in service
    }
    try:
        
        threshold = int(service.get("AccountLockoutThreshold", 0) or 0)
        if threshold <= 0:
            patch = {"AccountLockoutThreshold": 3}
            if "AccountLockoutDuration" in service:
                patch["AccountLockoutDuration"] = 60
            if "AccountLockoutCounterResetAfter" in service:
                patch["AccountLockoutCounterResetAfter"] = 60
            if "AccountLockoutCounterResetEnabled" in service:
                patch["AccountLockoutCounterResetEnabled"] = True
            patch_status, patch_data = redfish_request("/redfish/v1/AccountService", "PATCH", patch)
            assert patch_status in (200, 204), (
                f"Не удалось включить policy блокировки: HTTP {patch_status}; ответ: {patch_data}"
            )
            threshold = 3

        
        redfish_request(account_path, "DELETE")
        create_status, create_data = redfish_request(
            "/redfish/v1/AccountService/Accounts",
            "POST",
            {
                "UserName": username,
                "Password": password,
                "RoleId": "Administrator",
                "Enabled": True,
                "AccountTypes": ["Redfish", "WebUI"],
            },
        )
        assert create_status in (200, 201, 202, 204), (
            f"Не удалось создать временного пользователя: HTTP {create_status}; ответ: {create_data}"
        )

        
        visual_driver = make_driver()
        for _ in range(threshold):
            attempt = _ + 1
            print(f"Попытка неверного входа {attempt}/{threshold}")
            mode = login(visual_driver, username, "definitely-wrong-password")
            if mode == "form":
                time.sleep(1)
            else:
                status, _ = login_api(username, "definitely-wrong-password")
                assert status in (401, 403), f"Неожиданный код при неверном пароле: HTTP {status}"
            time.sleep(0.5)

        account_status, account = redfish_request(account_path)
        assert account_status == 200, f"Не удалось прочитать временную учётную запись: HTTP {account_status}"
        assert account.get("Locked") is True, f"Пользователь не заблокирован: Locked={account.get('Locked')!r}"
    finally:
        if visual_driver is not None:
            visual_driver.quit()
        
        redfish_request(account_path, "DELETE")
        if original_policy:
            redfish_request("/redfish/v1/AccountService", "PATCH", original_policy)

