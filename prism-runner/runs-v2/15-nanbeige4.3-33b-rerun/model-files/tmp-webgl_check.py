import asyncio, sys
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--use-angle=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"])
        pg = await b.new_page()
        await pg.goto("data:text/html,<script>const c=document.createElement('canvas');const gl=c.getContext('webgl2');document.title=gl?('WEBGL2:'+gl.getParameter(gl.VERSION)+'|'+(gl.getExtension('WEBGL_debug_renderer_info')?gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL):'n/a')):'NO_WEBGL2';</script>")
        print("title:", await pg.title())
        await b.close()
asyncio.run(main())
