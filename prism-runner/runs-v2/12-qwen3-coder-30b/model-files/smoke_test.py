import asyncio
import time
from playwright.async_api import async_playwright, Page
import os

# Smoke test for prism-runner.html

async def run_smoke_test():
    port = 8000
    server_process = None
    
    try:
        # Start HTTP server in background
        import subprocess
        server_process = subprocess.Popen(['python3', '-m', 'http.server', str(port)], cwd='/home/user/workspace/qwen3-coder-30b')
        
        await asyncio.sleep(1)  # Give server time to start
        
        async with async_playwright() as p:
            # Launch browser with software rendering for headless mode
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--use-angle=swiftshader',
                    '--enable-unsafe-swiftshader',
                    '--ignore-gpu-blocklist'
                ]
            )
            
            page = await browser.new_page()
            
            # Navigate to the game
            url = f'http://localhost:{port}/prism-runner.html'
            await page.goto(url)
            
            print("=== PRISM RUNNER SMOKE TEST ===")
            
            # Check initial state (title screen)
            title_visible = await page.is_visible('#title')
            print(f"Title screen visible: {title_visible}")
            
            # Take screenshot of title
            await page.screenshot(path='title.png', full_page=True)
            print("Screenshot taken: title.png")
            
            # Start the game with Enter key
            await page.keyboard.press('Enter')
            await asyncio.sleep(0.5)  # Wait for game to start
            
            # Check if game is playing
            state = await page.evaluate('window.__prism.state')
            print(f"Game state after starting: {state}")
            
            # Test gameplay for 10 seconds
            start_time = time.time()
            while time.time() - start_time < 10:
                await asyncio.sleep(0.1)
                
                # Check that score and distance are increasing
                score = await page.evaluate('window.__prism.score')
                distance = await page.evaluate('window.__prism.distance')
                speed = await page.evaluate('window.__prism.speed')
                
                print(f"Score: {score}, Distance: {distance}, Speed: {speed}")
                
                # Random controls
                if score > 0 and (score % 50) == 0:
                    await page.keyboard.press('ArrowLeft')
                elif score > 0 and (score % 70) == 0:
                    await page.keyboard.press('ArrowRight')
                elif score > 0 and (score % 90) == 0:
                    await page.keyboard.press(' ')
                
            # Pause the game
            await page.keyboard.press('p')
            await asyncio.sleep(1)
            
            # Check paused state
            paused_state = await page.evaluate('window.__prism.state')
            print(f"Game state after pause: {paused_state}")
            
            # Resume
            await page.keyboard.press('p')
            await asyncio.sleep(0.5)
            
            resumed_state = await page.evaluate('window.__prism.state')
            print(f"Game state after resume: {resumed_state}")
            
            # Let the player die by not steering
            start_time = time.time()
            while time.time() - start_time < 60 and await page.evaluate('window.__prism.state') == 'playing':
                await asyncio.sleep(1)
                
            # Check if game is dead
            final_state = await page.evaluate('window.__prism.state')
            print(f"Final game state: {final_state}")
            
            if final_state == 'dead':
                # Restart the game
                await page.keyboard.press('r')
                await asyncio.sleep(1)
                
                restarted_state = await page.evaluate('window.__prism.state')
                print(f"Game state after restart: {restarted_state}")
                
                # Take screenshot of game over
                await page.screenshot(path='game_over.png', full_page=True)
                print("Screenshot taken: game_over.png")
            
            # Collect console logs
            logs = []
            for log in page.console:
                logs.append(log.text)
                
            print(f"Console messages: {len(logs)} total")
            
            # Write report
            with open('smoke-report.txt', 'w') as f:
                f.write("=== PRISM RUNNER SMOKE TEST REPORT ===\n")
                f.write(f"Title visible: {title_visible}\n")
                f.write(f"Initial state: {state}\n")
                f.write(f"Paused state: {paused_state}\n")
                f.write(f"Resumed state: {resumed_state}\n")
                f.write(f"Final state: {final_state}\n")
                f.write(f"Console messages: {len(logs)} total\n")
                if logs:
                    f.write("Last few console messages:\n")
                    for msg in logs[-5:]:
                        f.write(f"  {msg}\n")
            
            print("=== TEST COMPLETED ===")
            
    except Exception as e:
        print(f"Test failed with error: {e}")
        
    finally:
        # Cleanup
        if server_process:
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()

# Run the test
asyncio.run(run_smoke_test())