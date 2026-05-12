from playwright.sync_api import sync_playwright

print("尝试启动浏览器，如果缺失会自动下载...")
try:
    with sync_playwright() as p:
        # 这就是API自动下载的关键一步
        browser = p.chromium.launch()
        print("浏览器启动成功！")
        browser.close()
except Exception as e:
    print(f"启动失败: {e}")